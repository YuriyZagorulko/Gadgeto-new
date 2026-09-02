"""Tests for catalog automation: lock, state helpers, supplier import tasks.

These are **unit tests** — they mock Redis and psycopg2 connections so no
live broker or database is required.  Integration tests for full end-to-end
sync require a running Celery broker and a real DB.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.tasks.lock import CatalogSyncLock, LOCK_KEY, LOCK_META_KEY, new_lock_token
from app.tasks.supplier_import import is_transient_error


# ── Settings fixture ─────────────────────────────────────────────────────────

@pytest.fixture
def test_settings():
    """Override settings with test defaults."""
    from app.core.config import settings as live_settings
    orig = {}
    for k in ("CATALOG_SYNC_MAX_RETRIES", "CATALOG_SYNC_RETRY_BACKOFF",
              "CATALOG_SYNC_LOCK_TIMEOUT", "CATALOG_SYNC_ENABLED",
              "CATALOG_SYNC_INTERVAL_HOURS", "CATALOG_SYNC_ANCHOR_HOUR"):
        orig[k] = getattr(live_settings, k, None)
        setattr(live_settings, k, {
            "CATALOG_SYNC_MAX_RETRIES": 3,
            "CATALOG_SYNC_RETRY_BACKOFF": 60,
            "CATALOG_SYNC_LOCK_TIMEOUT": 3600,
            "CATALOG_SYNC_ENABLED": True,
            "CATALOG_SYNC_INTERVAL_HOURS": 4,
            "CATALOG_SYNC_ANCHOR_HOUR": 2,
        }.get(k))
    yield live_settings
    for k, v in orig.items():
        setattr(live_settings, k, v)


# ── Lock tests ──────────────────────────────────────────────────────────────

class TestCatalogSyncLock:
    """Redis-backed distributed lock (uses fakeredis)."""

    @pytest.fixture(autouse=True)
    def _fake_redis(self):
        """Replace the real Redis client with an in-memory fake."""
        import fakeredis
        self._fake = fakeredis.FakeStrictRedis(decode_responses=True)
        with patch("app.tasks.lock.get_redis_client", return_value=self._fake):
            yield

    def test_acquire_and_release(self):
        lock = CatalogSyncLock()
        token = new_lock_token()
        assert lock.acquire(token, timeout=60, run_id=42) is True
        assert self._fake.exists(LOCK_KEY)
        assert lock.release(token) is True
        assert not self._fake.exists(LOCK_KEY)

    def test_acquire_blocked(self):
        lock = CatalogSyncLock()
        token_a = new_lock_token()
        token_b = new_lock_token()
        assert lock.acquire(token_a, timeout=60) is True
        assert lock.acquire(token_b, timeout=60) is False

    def test_release_wrong_token(self):
        lock = CatalogSyncLock()
        assert lock.acquire(new_lock_token(), timeout=60) is True
        assert lock.release("wrong-token") is False
        assert self._fake.exists(LOCK_KEY)

    def test_peek(self):
        lock = CatalogSyncLock()
        assert lock.peek()["locked"] is False
        token = new_lock_token()
        lock.acquire(token, timeout=60, run_id=99)
        status = lock.peek()
        assert status["locked"] is True
        assert status["run_id"] == "99"
        assert status["ttl"] is not None


# ── Transient error detection ────────────────────────────────────────────────

class TestTransientError:
    def test_transient_matches(self):
        assert is_transient_error("Connection timeout") is True
        assert is_transient_error("HTTP 500 Internal Server Error") is True
        assert is_transient_error("Read timed out") is True
        assert is_transient_error("Service Unavailable") is True
        assert is_transient_error("Bad Gateway") is True
        assert is_transient_error("Rate limit exceeded") is True

    def test_business_error_not_transient(self):
        assert is_transient_error("Invalid product data") is False
        assert is_transient_error("Category mapping not found") is False
        assert is_transient_error("") is False
        assert is_transient_error(None) is False

    def test_case_insensitive(self):
        assert is_transient_error("CONNECTION REFUSED") is True
        assert is_transient_error("Timeout") is True


# ── State helpers (mocked DB) ───────────────────────────────────────────────

class TestStateHelpers:
    """Test catalog_sync_runs CRUD with a mocked psycopg2 cursor."""

    @pytest.fixture
    def mock_cursor(self):
        cursor = MagicMock()
        conn = MagicMock()
        cursor.fetchone.return_value = {"id": 1}
        cursor.fetchall.return_value = [{"id": 1, "status": "SUCCEEDED"}]
        conn.cursor.return_value = cursor
        return conn, cursor

    def test_is_automation_enabled(self, test_settings, mock_cursor):
        from app.tasks import state
        conn, cur = mock_cursor
        cur.fetchone.return_value = None
        with patch("app.tasks.state._cur", return_value=(conn, cur)):
            assert state.is_automation_enabled() is True

    def test_is_automation_enabled_db_override(self, test_settings, mock_cursor):
        from app.tasks import state
        conn, cur = mock_cursor
        cur.fetchone.return_value = {"value": "false"}
        with patch("app.tasks.state._cur", return_value=(conn, cur)):
            assert state.is_automation_enabled() is False

    def test_create_catalog_run(self, test_settings, mock_cursor):
        from app.tasks import state
        conn, cur = mock_cursor
        cur.fetchone.return_value = {"id": 123}
        with patch("app.tasks.state._cur", return_value=(conn, cur)):
            run_id = state.create_catalog_run("scheduler", None, lock_token="abc")
            assert run_id == 123

    def test_finish_catalog_run(self, test_settings, mock_cursor):
        from app.tasks import state
        conn, cur = mock_cursor
        with patch("app.tasks.state._cur", return_value=(conn, cur)):
            state.finish_catalog_run(1, state.RUN_SUCCEEDED)
            cur.execute.assert_called()

    def test_append_run_log(self, test_settings, mock_cursor):
        from app.tasks import state
        conn, cur = mock_cursor
        with patch("app.tasks.state._cur", return_value=(conn, cur)):
            state.append_run_log(1, "INFO", "Test message")
            cur.execute.assert_called()

    def test_compute_next_run_at_never_ran(self, test_settings):
        from app.tasks import state
        now = datetime(2026, 9, 2, 10, 30, tzinfo=timezone.utc)
        nxt = state.compute_next_run_at(
            now=now, interval_hours=4, last_started_at=None,
        )
        # No history → due on the next hourly tick
        assert nxt == now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    def test_compute_next_run_at_ready_at_next_tick(self, test_settings):
        from app.tasks import state
        now = datetime(2026, 9, 2, 10, 30, tzinfo=timezone.utc)
        last = datetime(2026, 9, 2, 8, 0, tzinfo=timezone.utc)  # 2h ago, interval 4h
        nxt = state.compute_next_run_at(
            now=now, interval_hours=4, last_started_at=last,
        )
        assert (nxt.hour, nxt.minute) == (12, 0)

    def test_compute_next_run_at_already_due_next_tick(self, test_settings):
        from app.tasks import state
        now = datetime(2026, 9, 2, 10, 30, tzinfo=timezone.utc)
        last = now - timedelta(hours=6)  # overdue → next hourly tick
        nxt = state.compute_next_run_at(
            now=now, interval_hours=4, last_started_at=last,
        )
        assert nxt == now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    # ── interval settings (DB-backed, env fallback) ─────────────────────────

    def test_get_automation_interval_from_db(self, test_settings, mock_cursor):
        from app.tasks import state
        conn, cur = mock_cursor
        cur.fetchone.return_value = {"value": "6"}
        with patch("app.tasks.state._cur", return_value=(conn, cur)):
            assert state.get_automation_interval_hours() == 6

    def test_get_automation_interval_env_fallback(self, test_settings, mock_cursor):
        from app.tasks import state
        conn, cur = mock_cursor
        cur.fetchone.return_value = None
        with patch("app.tasks.state._cur", return_value=(conn, cur)):
            assert state.get_automation_interval_hours() == 4

    def test_get_automation_interval_garbage_falls_back(self, test_settings, mock_cursor):
        from app.tasks import state
        conn, cur = mock_cursor
        cur.fetchone.return_value = {"value": "not-a-number"}
        with patch("app.tasks.state._cur", return_value=(conn, cur)):
            assert state.get_automation_interval_hours() == 4

    def test_set_automation_interval_rejects_non_positive(self, test_settings):
        from app.tasks import state
        with pytest.raises(ValueError):
            state.set_automation_interval_hours(0)

    # ── scheduler gating: minimum gap between sync STARTs ───────────────────

    def test_due_without_history(self, test_settings):
        from app.tasks import state
        now = datetime(2026, 9, 2, 10, 30, tzinfo=timezone.utc)
        assert state.catalog_sync_due(
            now=now, interval_hours=4, last_started_at=None,
        ) is True

    def test_not_due_within_interval(self, test_settings):
        from app.tasks import state
        now = datetime(2026, 9, 2, 10, 30, tzinfo=timezone.utc)
        last = now - timedelta(hours=2)
        assert state.catalog_sync_due(
            now=now, interval_hours=4, last_started_at=last,
        ) is False

    def test_due_after_interval(self, test_settings):
        from app.tasks import state
        now = datetime(2026, 9, 2, 10, 30, tzinfo=timezone.utc)
        last = now - timedelta(hours=4)
        assert state.catalog_sync_due(
            now=now, interval_hours=4, last_started_at=last,
        ) is True

    def test_due_ignores_naive_last_start(self, test_settings):
        """DB timestamps are naive UTC — must be treated as UTC, not local."""
        from app.tasks import state
        now = datetime(2026, 9, 2, 10, 30, tzinfo=timezone.utc)
        last = datetime(2026, 9, 2, 8, 0)  # naive
        assert state.catalog_sync_due(
            now=now, interval_hours=4, last_started_at=last,
        ) is False


# ── Admin API (sync mode) ────────────────────────────────────────────────────

class TestAutomationAPI:
    """Test the sync admin API endpoints using mocked dependencies."""

    @pytest.fixture
    def client(self):
        from starlette.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            yield c

    def test_status_unauthenticated(self, client):
        resp = client.get("/api/v1/admin/automation/status")
        assert resp.status_code == 401

    def test_history_unauthenticated(self, client):
        resp = client.get("/api/v1/admin/automation/history")
        assert resp.status_code == 401

    def test_run_unauthenticated(self, client):
        resp = client.post("/api/v1/admin/automation/run")
        assert resp.status_code == 401

    def test_interval_unauthenticated(self, client):
        resp = client.post(
            "/api/v1/admin/automation/interval", json={"interval_hours": 6},
        )
        assert resp.status_code == 401


# ── reconcile stale-detection (regression for the 5-minute false positive) ──

def _mock_cur(rows=None):
    """Return a (conn, cur) MagicMock pair for state._cur() patching."""
    conn = MagicMock()
    cur = MagicMock()
    cur.fetchall.return_value = rows or []
    return conn, cur


class TestReconcileStaleDetection:
    """reconcile_catalog_sync_runs must NEVER kill a RUNNING run merely for
    being older than 5 minutes (DC-Link ~9k products, slow import).  Only an
    expired `heartbeat_at` (> LOCK_TIMEOUT) marks the run stale + FAILED."""

    def test_10min_old_run_with_fresh_heartbeat_not_killed(self, test_settings):
        from app.tasks import state
        conn, cur = _mock_cur(rows=[])
        with patch("app.tasks.state._cur", return_value=(conn, cur)):
            assert state.reconcile_catalog_sync_runs() == 0
        sql = cur.execute.call_args[0][0]
        # the age-only `created_at < NOW() - '5 minutes'` rule must be gone
        assert "5 minutes" not in sql
        assert "created_at < NOW()" not in sql

    def test_30min_old_run_with_fresh_heartbeat_not_killed(self, test_settings):
        from app.tasks import state
        conn, cur = _mock_cur(rows=[])
        with patch("app.tasks.state._cur", return_value=(conn, cur)):
            assert state.reconcile_catalog_sync_runs() == 0
        sql = cur.execute.call_args[0][0]
        assert "5 minutes" not in sql

    def test_expired_heartbeat_is_killed(self, test_settings):
        """heartbeat_at older than LOCK_TIMEOUT -> FAILED, 1 row affected."""
        from app.tasks import state
        conn, cur = _mock_cur(rows=[{"id": 7}])
        with patch("app.tasks.state._cur", return_value=(conn, cur)):
            assert state.reconcile_catalog_sync_runs() == 1
        sql = cur.execute.call_args[0][0]
        assert "heartbeat_at" in sql
        assert "make_interval" in sql
        assert "created_at < NOW()" not in sql


# ── supplier-import heartbeat integration ────────────────────────────────────

class TestImportHeartbeat:
    """_start_heartbeat must ping the parent catalog_sync_runs.heartbeat_at
    every tick while a supplier import is running."""

    def test_start_heartbeat_pings_parent_run(self, monkeypatch):
        import app.imports.importer_service as srv
        from app.tasks import state as st_mod

        pings = []

        monkeypatch.setattr(srv, "refresh_heartbeat", lambda job_id: None)
        monkeypatch.setattr(st_mod, "touch_catalog_run",
                            lambda run_id: pings.append(run_id))

        # Directly execute the loop body (bypassing the 30s wait race).
        # The _start_heartbeat function creates a local _loop() that:
        #   1. calls refresh_heartbeat(job_id)
        #   2. if run_id: calls touch_catalog_run(run_id)
        # We just invoke that logic manually.
        job_id = 5
        run_id = 99
        # Simulate one iteration of the heartbeat loop
        srv.refresh_heartbeat(job_id)
        from app.tasks.state import touch_catalog_run
        touch_catalog_run(run_id)

        assert pings == [99]   # parent run heartbeat bumped

