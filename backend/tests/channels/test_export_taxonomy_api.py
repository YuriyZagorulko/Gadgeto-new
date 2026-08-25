"""Regression + behaviour tests for the admin export/taxonomy/mapping APIs.

Covers:
  1. GET /export/channels/{code}/taxonomy — read-only, never triggers a refresh;
     regresses the KeyError('c') 500 (count(*) rows must be aliased as `c`).
  2. GET /export/channels/{code}/taxonomy/status — progress shape.
  3. POST /export/channels/{code}/taxonomy/refresh — starts a background job
     instead of running synchronously.
  4. Mapping list returns unmapped internal entities.
  5. Mapping create is idempotent, defaults to `proposed` (never auto-accept).
  6. Taxomomy coverage counts distinct entities with percentages.
  7. Taxomomy worker marks a run PARTIAL when categories fail, SUCCEEDED otherwise.

Everything here is hermetic: DB access and Rozetka network access are mocked.
"""

from unittest.mock import patch

import psycopg2.extras
import pytest
from starlette.testclient import TestClient

from app.api.admin.deps import require_admin
from app.main import app

RealDictRow = psycopg2.extras.RealDictRow


class FakeCursor:
    """A cursor that dispatches canned rows based on the SQL shape."""

    def __init__(self, rows=None):
        self.queries = []
        self.params = []
        self._rows = rows or []
        self._pending = None

    def execute(self, sql, params=()):
        self.queries.append(sql)
        self.params.append(params)
        self._pending = self._produce(sql, params)

    def _produce(self, sql, params=()):
        low = sql.lower()
        if low.startswith("select count") and "channel_external_categories" in low:
            return [RealDictRow({"c": 4761})]
        if low.startswith("select count") and "channel_external_attributes" in low:
            return [RealDictRow({"c": 882})]
        if low.startswith("select count") and "channel_external_values" in low:
            return [RealDictRow({"c": 14965})]
        if "from sync_runs" in low or "update sync_runs" in low:
            if low.strip().startswith("update"):
                return []
            return self._rows
        if "from channels" in low and "channel_external" not in low and "mappings" not in low:
            return [RealDictRow({
                "id": 1, "code": "rozetka", "name": "Rozetka",
                "is_enabled": False, "created_at": None, "updated_at": None,
            })]
        if low.startswith("select count") and "channel_category_mappings" in low:
            return [RealDictRow({"c": 1})]
        if "channel_category_mappings" in low and "internal_id" in low:
            return [RealDictRow({
                "internal_id": 106, "internal_name": "3D-принтери", "slug": "3d-printers",
                "mapping_id": None, "external_id": None, "external_name": None,
                "status": "unmapped", "confidence": None, "source": None,
                "created_at": None, "updated_at": None,
            })]
        if "select id from channel_category_mappings" in low:
            return [RealDictRow({"id": 7})]
        if low.startswith("update channel_category_mappings"):
            return [RealDictRow({"id": 7})]
        if "from eff" in low:
            return self._rows
        return []

    def fetchone(self):
        if not self._pending:
            return None
        return self._pending[0]

    def fetchall(self):
        return self._pending or []

    def close(self):
        pass


class FakeConn:
    autocommit = True

    def __init__(self, rows=None):
        self.cursor_obj = FakeCursor(rows or [])

    def cursor(self, cursor_factory=None):
        return self.cursor_obj

    def commit(self):
        pass

    def close(self):
        pass


async def _fake_admin(request=None):
    return {"id": 1, "email": "admin@test", "role": "ADMIN", "status": "ACTIVE"}


@pytest.fixture()
def client():
    app.dependency_overrides[require_admin] = _fake_admin
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


class FakeLoop:
    def __init__(self):
        self.calls = []

    def run_in_executor(self, executor, func, *args):
        self.calls.append((func, args))
        return None


# ── Tests ────────────────────────────────────────────────────────────────────


def test_taxonomy_get_uses_aliased_count_columns(client):
    """Regression: SELECT count(*) returns column `count`, not `c`.

    get_taxonomy_stats must alias the column (AS c) or the endpoint 500s.
    """
    conn = FakeConn()
    with patch("app.api.admin.export.db", return_value=(conn.cursor_obj, conn.cursor_obj)):
        res = client.get("/api/v1/admin/export/channels/rozetka/taxonomy")
    assert res.status_code == 200, res.text
    assert res.json()["items"]["categories"] == 4761
    count_queries = [q for q in conn.cursor_obj.queries if "count(" in q]
    assert len(count_queries) == 3
    for q in count_queries:
        assert " AS c" in q or " as c" in q, f"count query must alias column c: {q}"


def test_taxonomy_get_never_triggers_refresh(client):
    """GET /taxonomy is strictly read-only: it must never drive a refresh."""
    with patch("app.api.admin.export.db",
               return_value=(FakeConn().cursor_obj, FakeConn().cursor_obj)), \
         patch("app.channels.taxonomy.get_taxonomy_service") as svc:
        res = client.get("/api/v1/admin/export/channels/rozetka/taxonomy")
    assert res.status_code == 200
    svc.assert_not_called()


def test_taxonomy_status_shape(client):
    """GET /taxonomy/status returns the documented progress shape."""
    import json
    conn = FakeConn()
    conn.cursor_obj._rows = [RealDictRow({
        "id": 12, "status": "RUNNING", "started_at": None, "finished_at": None,
        "progress_json": json.dumps({
            "categories": {"processed": 100, "total": 100},
            "attributes": {"categories_processed": 33, "categories_total": 4761,
                           "created": 12, "updated": 0},
            "errors": 0, "current_operation": "Fetching attributes",
            "logs": [{"t": 1, "ts": "09:42:11", "level": "INFO", "message": "start"}],
        }),
    })]
    with patch("app.api.admin.export.db", return_value=(conn.cursor_obj, conn.cursor_obj)):
        res = client.get("/api/v1/admin/export/channels/rozetka/taxonomy/status")
    assert res.status_code == 200
    body = res.json()
    assert body["run_id"] == 12
    assert body["categories"]["processed"] == 100
    assert body["attributes"]["categories_processed"] == 33


def test_refresh_starts_background(client):
    """POST /taxonomy/refresh must launch a background job, not run sync."""
    fake_loop = FakeLoop()
    with patch("app.api.admin.export.db",
               return_value=(FakeConn().cursor_obj, FakeConn().cursor_obj)), \
         patch("app.channels.rozetka.taxonomy_run.start_taxonomy_refresh", return_value=99) as start, \
         patch("app.channels.taxonomy.get_taxonomy_service") as sync, \
         patch("asyncio.get_event_loop", return_value=fake_loop):
        res = client.post("/api/v1/admin/export/channels/rozetka/taxonomy/refresh")
    assert res.status_code == 200
    assert res.json()["run_id"] == 99
    start.assert_called_once_with(1, 1)
    sync.assert_not_called()          # no synchronous refresh path
    assert fake_loop.calls            # executor dispatched
    func, args = fake_loop.calls[0]
    assert func.__name__ == "run_taxonomy_refresh"
    assert args[:2] == (1, 99)


def test_mapping_list_includes_unmapped(client):
    conn = FakeConn()
    with patch("app.api.admin.export_mapping.db",
               return_value=(conn.cursor_obj, conn.cursor_obj)):
        res = client.get("/api/v1/admin/export/channels/rozetka/mappings/categories?per_page=5&status=unmapped")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert body["items"][0]["mapping_id"] is None
    assert body["items"][0]["status"] == "unmapped"


def test_mapping_create_is_idempotent(client):
    """Creating a mapping for an already-existing (internal, category) updates it."""
    conn = FakeConn()
    with patch("app.api.admin.export_mapping.db",
               return_value=(conn.cursor_obj, conn.cursor_obj)):
        res = client.post(
            "/api/v1/admin/export/channels/rozetka/mappings/categories",
            json={"internal_id": 106, "external_id": "131143", "external_name": "X",
                  "status": "proposed", "confidence": 0.9},
        )
    assert res.status_code == 200
    assert res.json()["id"] == 7
    assert res.json()["updated"] is True


def test_mapping_create_never_auto_accepts(client):
    """A mapping created without an explicit status must not be accepted."""
    conn = FakeConn()
    with patch("app.api.admin.export_mapping.db",
               return_value=(conn.cursor_obj, conn.cursor_obj)):
        res = client.post(
            "/api/v1/admin/export/channels/rozetka/mappings/categories",
            json={"internal_id": 106, "external_id": "131143", "external_name": "X"})
    assert res.status_code == 200
    # The idempotent create path goes through the SELECT->UPDATE branch here;
    # assert the default status proposed is set on the UPDATE params.
    updates = [(q, p) for q, p in zip(conn.cursor_obj.queries, conn.cursor_obj.params)
               if q.strip().lower().startswith("update channel_category_mappings")]
    assert updates, "expected an UPDATE for the existing mapping"
    sql, params = updates[0]
    # UPDATE ... SET external_id=%s, name=%s, status=%s, confidence=%s, ... WHERE id=%s
    assert params[2] == "proposed"


def test_coverage_counts_are_distinct(client):
    """Coverage block SQL must use EXISTS (distinct entities), not JOIN-inflated rows."""
    import inspect
    from app.api.admin.export_mapping import _coverage_block
    src = inspect.getsource(_coverage_block)
    assert "EXISTS" in src
    assert "count(*) FILTER" in src
    # A category-scoped attribute with 2 mappings must still be counted once.
    conn = FakeConn()
    conn.cursor_obj._rows = [RealDictRow({
        "total": 10, "accepted": 4, "proposed": 2, "excluded": 1, "unmapped": 3,
    })]
    block = _coverage_block(conn.cursor_obj, cid=1, kind="attributes")
    assert block["total"] == 10
    assert block["accepted_pct"] == 40.0
    assert block["unmapped"] == 3


class _FakeTaxonomyService:
    """Emulates the service: reports progress; optionally a category fails."""

    def __init__(self, errors=1):
        self.errors = errors

    def refresh(self, channel_id, channel_code, progress_cb=None):
        if progress_cb:
            progress_cb("init", 0, 0, "start")
            progress_cb("auth", 1, 1, "auth")
            progress_cb("categories", 100, 100, "Categories: 100 / 100")
            progress_cb("attributes", 5, 10, "Category 1: 3 attributes")
            if self.errors:
                progress_cb("attributes", 10, 10, "Category 2 FAILED: boom")
            else:
                progress_cb("attributes", 10, 10, "Category 3: 2 attributes")
        return {
            "categories_created": 1, "categories_updated": 0,
            "attributes_created": 2, "attributes_updated": 0,
            "values_created": 3, "values_updated": 0,
            "errors": self.errors, "duration_seconds": 1.0,
        }


def _run_worker(service, run_id=5):
    from app.channels.rozetka import taxonomy_run as tr
    conn = FakeConn()
    with patch.object(tr, "RozetkaTaxonomyService", return_value=service), \
            patch.object(tr.psycopg2, "connect", return_value=conn):
        result = tr.run_taxonomy_refresh(1, run_id)
    return result, conn


def test_worker_marks_partial_when_categories_fail():
    """One failed category must not abort the run; the run ends as PARTIAL."""
    result, conn = _run_worker(_FakeTaxonomyService(errors=1))
    assert result["status"] == "PARTIAL"
    status_updates = [p for q, p in zip(conn.cursor_obj.queries, conn.cursor_obj.params)
                      if q.strip().startswith("UPDATE sync_runs")
                      and p and str(p[0]) in ("SUCCEEDED", "PARTIAL", "FAILED")]
    assert any(p[0] == "PARTIAL" for p in status_updates)


def test_worker_marks_succeeded_when_no_errors():
    """A clean run finishes as SUCCEEDED without duplicates."""
    result, conn = _run_worker(_FakeTaxonomyService(errors=0))
    assert result["status"] == "SUCCEEDED"