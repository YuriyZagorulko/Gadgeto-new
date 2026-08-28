"""Tests for ImportRunner.finalize() — feed reduction threshold safety."""
from unittest.mock import MagicMock
from pathlib import Path
import importlib.util

_RUNNER_PATH = str(Path(__file__).resolve().parents[2] / "backend/app/imports/import_runner.py")
_spec = importlib.util.spec_from_file_location("import_runner", _RUNNER_PATH)
_mod = importlib.util.module_from_spec(_spec)
import sys
sys.modules["psycopg2"] = MagicMock()
sys.modules["psycopg2.extras"] = MagicMock()
_db_mock = MagicMock()
sys.modules["app"] = MagicMock()
sys.modules["app.core"] = MagicMock()
sys.modules["app.core.db_connect"] = _db_mock
_spec.loader.exec_module(_mod)

ImportRunner = _mod.ImportRunner
MINIMUM_FEED_RATIO = _mod.MINIMUM_FEED_RATIO

import pytest

@pytest.fixture
def runner():
    r = ImportRunner(supplier_id=1, supplier_code="test",
                     progress_cb=MagicMock(), mark_removed_products=True)
    return r

def mkconn(fetchone_val):
    c = MagicMock()
    c.fetchone.return_value = [fetchone_val]
    conn = MagicMock()
    conn.cursor.return_value = c
    return conn

class TestFinalizeThreshold:
    def test_normal_reduction_runs_update(self, runner):
        conn = mkconn(100)
        _mod.psycopg2.connect.return_value = conn
        for i in range(95):
            runner.new_skus.add(f"SKU-{i}")
        runner.finalize()
        sqls = [str(c[0][0]) for c in conn.cursor().execute.call_args_list]
        updates = [s for s in sqls if "UPDATE" in s]
        assert len(updates) >= 1, f"Expected UPDATE, got: {sqls}"

    def test_suspicious_drop_skips_update(self, runner):
        conn = mkconn(100)
        _mod.psycopg2.connect.return_value = conn
        for i in range(20):
            runner.new_skus.add(f"SKU-{i}")
        runner.finalize()
        sqls = [str(c[0][0]) for c in conn.cursor().execute.call_args_list]
        updates = [s for s in sqls if "UPDATE" in s]
        assert len(updates) == 0, f"Expected no UPDATE, got: {updates}"
        assert any("Пропущено" in str(w) for w in runner.warnings)

    def test_empty_feed_skips(self, runner):
        conn = mkconn(100)
        _mod.psycopg2.connect.return_value = conn
        runner.finalize()
        assert conn.cursor().execute.call_count == 0

    def test_first_import_allows_update(self, runner):
        conn = mkconn(0)
        _mod.psycopg2.connect.return_value = conn
        for i in range(50):
            runner.new_skus.add(f"SKU-{i}")
        runner.finalize()
        sqls = [str(c[0][0]) for c in conn.cursor().execute.call_args_list]
        updates = [s for s in sqls if "UPDATE" in s]
        assert len(updates) >= 1

    def test_mark_removed_false(self, runner):
        _mod.psycopg2.connect.reset_mock()
        runner.mark_removed = False
        runner.finalize()
        _mod.psycopg2.connect.assert_not_called()

    def test_borderline_above_threshold(self, runner):
        conn = mkconn(100)
        _mod.psycopg2.connect.return_value = conn
        for i in range(51):
            runner.new_skus.add(f"SKU-{i}")
        runner.finalize()
        sqls = [str(c[0][0]) for c in conn.cursor().execute.call_args_list]
        updates = [s for s in sqls if "UPDATE" in s]
        # 51/100 = 0.51 > 0.5 → should run
        assert len(updates) >= 1

    def test_borderline_below_threshold(self, runner):
        conn = mkconn(100)
        _mod.psycopg2.connect.return_value = conn
        for i in range(49):
            runner.new_skus.add(f"SKU-{i}")
        runner.finalize()
        sqls = [str(c[0][0]) for c in conn.cursor().execute.call_args_list]
        updates = [s for s in sqls if "UPDATE" in s]
        # 49/100 = 0.49 < 0.5 → should skip
        assert len(updates) == 0

    def test_reappearance_not_hidden(self, runner):
        """SKU in new_skus is excluded from the UPDATE."""
        conn = mkconn(50)
        _mod.psycopg2.connect.return_value = conn
        for i in range(48):
            runner.new_skus.add(f"SKU-{i}")
        runner.finalize()
        sqls = [str(c[0][0]) for c in conn.cursor().execute.call_args_list]
        update_sqls = [s for s in sqls if "UPDATE" in s]
        if update_sqls:
            assert "!= ALL" in update_sqls[0]

    def test_supplier_id_in_count_query(self, runner):
        conn = mkconn(200)
        _mod.psycopg2.connect.return_value = conn
        for i in range(150):
            runner.new_skus.add(f"SKU-{i}")
        runner.finalize()
        sqls = [str(c[0][0]) for c in conn.cursor().execute.call_args_list]
        count_sqls = [s for s in sqls if "SELECT count" in s]
        assert len(count_sqls) >= 1
        assert "supplier_id" in count_sqls[0]

    def test_manually_hidden_not_affected(self, runner):
        """The UPDATE has WHERE status!='HIDDEN' which preserves manual hides."""
        conn = mkconn(100)
        _mod.psycopg2.connect.return_value = conn
        for i in range(95):
            runner.new_skus.add(f"SKU-{i}")
        runner.finalize()
        sqls = [str(c[0][0]) for c in conn.cursor().execute.call_args_list]
        update_sqls = [s for s in sqls if "UPDATE" in s]
        if update_sqls:
            assert "status!='HIDDEN'" in update_sqls[0] or "status !" in update_sqls[0]
