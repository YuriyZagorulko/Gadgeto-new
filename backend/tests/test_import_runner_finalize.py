"""Tests for ImportRunner.finalize() — feed reduction threshold safety.

This module used to install ``MagicMock`` entries into ``sys.modules``
at import time. That polluted the global module table for the rest of
the pytest session and broke every test that imported ``app.*`` or
relied on a real ``psycopg2`` (e.g. ``ModuleNotFoundError: No module
named 'app.models'; 'app' is not a package``,
``TypeError: catching classes that do not inherit from BaseException
is not allowed``).

The mocks are now installed **only** while we load an isolated copy
of ``app.imports.import_runner`` and are restored before any other
test runs. Loading is lazy — it happens in the ``runner`` fixture,
not at module-import time — so importing this test file is safe
during pytest collection.
"""
from unittest.mock import MagicMock
from pathlib import Path
import importlib.util
import sys
import pytest

_RUNNER_PATH = str(
    Path(__file__).resolve().parents[2]
    / "backend/app/imports/import_runner.py"
)

# Module names we temporarily mock while loading the isolated runner.
# These keys are saved/restored around ``exec_module`` so other test
# modules (and the rest of the application code) keep their real
# imports.
_MOCKED_MODULES = (
    "psycopg2",
    "psycopg2.extras",
    "app",
    "app.core",
    "app.core.db_connect",
)


def _load_isolated_runner():
    """Load ``app.imports.import_runner`` with mocked DB dependencies.

    Returns ``(mod, ImportRunner, MINIMUM_FEED_RATIO)``.

    Uses a unique spec name (``_test_import_runner_finalize_runner``)
    so the loaded module does NOT overwrite ``app.imports.import_runner``
    in ``sys.modules``. That way the real application runner, if
    subsequently imported by another test, stays untouched.

    All ``sys.modules`` mutations are scoped to a ``try/finally`` that
    restores the previous value of every key (deletes the key if it
    did not exist before).
    """
    saved = {name: sys.modules.get(name) for name in _MOCKED_MODULES}
    try:
        # Install mocks
        sys.modules["psycopg2"] = MagicMock()
        sys.modules["psycopg2.extras"] = MagicMock()
        sys.modules["app"] = MagicMock()
        sys.modules["app.core"] = MagicMock()
        sys.modules["app.core.db_connect"] = MagicMock()

        spec = importlib.util.spec_from_file_location(
            "_test_import_runner_finalize_runner", _RUNNER_PATH
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod, mod.ImportRunner, mod.MINIMUM_FEED_RATIO
    finally:
        # Restore every key we touched (or remove it if it was absent).
        for name in _MOCKED_MODULES:
            prior = saved.get(name)
            if prior is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = prior


@pytest.fixture
def runner():
    """Yield an ``ImportRunner`` instance whose dependencies are mocked.

    The mock environment exists only for the lifetime of this
    fixture. The ``_load_isolated_runner`` helper guarantees
    ``sys.modules`` is restored even if ``exec_module`` raises.

    Tests access the loaded mocked module via the yielded
    ``ImportRunner`` instance: ``runner._mod.psycopg2.connect...``.
    The attribute is set on the freshly-created instance, scoped per
    test invocation, so it does not leak across tests.
    """
    _mod, ImportRunner, _ = _load_isolated_runner()
    r = ImportRunner(
        supplier_id=1,
        supplier_code="test",
        progress_cb=MagicMock(),
        mark_removed_products=True,
    )
    # Attach the mocked module to the instance so tests can do
    # ``runner._mod.psycopg2.connect.return_value = conn``.
    r._mod = _mod  # type: ignore[attr-defined]
    yield r

def mkconn(fetchone_val):
    c = MagicMock()
    c.fetchone.return_value = [fetchone_val]
    conn = MagicMock()
    conn.cursor.return_value = c
    return conn

class TestFinalizeThreshold:
    def test_normal_reduction_runs_update(self, runner):
        conn = mkconn(100)
        runner._mod.psycopg2.connect.return_value = conn
        for i in range(95):
            runner.new_skus.add(f"SKU-{i}")
        runner.finalize()
        sqls = [str(c[0][0]) for c in conn.cursor().execute.call_args_list]
        updates = [s for s in sqls if "UPDATE" in s]
        assert len(updates) >= 1, f"Expected UPDATE, got: {sqls}"

    def test_suspicious_drop_skips_update(self, runner):
        conn = mkconn(100)
        runner._mod.psycopg2.connect.return_value = conn
        for i in range(20):
            runner.new_skus.add(f"SKU-{i}")
        runner.finalize()
        sqls = [str(c[0][0]) for c in conn.cursor().execute.call_args_list]
        updates = [s for s in sqls if "UPDATE" in s]
        assert len(updates) == 0, f"Expected no UPDATE, got: {updates}"
        assert any("Пропущено" in str(w) for w in runner.warnings)

    def test_empty_feed_skips(self, runner):
        conn = mkconn(100)
        runner._mod.psycopg2.connect.return_value = conn
        runner.finalize()
        assert conn.cursor().execute.call_count == 0

    def test_first_import_allows_update(self, runner):
        conn = mkconn(0)
        runner._mod.psycopg2.connect.return_value = conn
        for i in range(50):
            runner.new_skus.add(f"SKU-{i}")
        runner.finalize()
        sqls = [str(c[0][0]) for c in conn.cursor().execute.call_args_list]
        updates = [s for s in sqls if "UPDATE" in s]
        assert len(updates) >= 1

    def test_mark_removed_false(self, runner):
        runner._mod.psycopg2.connect.reset_mock()
        runner.mark_removed = False
        runner.finalize()
        runner._mod.psycopg2.connect.assert_not_called()

    def test_borderline_above_threshold(self, runner):
        conn = mkconn(100)
        runner._mod.psycopg2.connect.return_value = conn
        for i in range(51):
            runner.new_skus.add(f"SKU-{i}")
        runner.finalize()
        sqls = [str(c[0][0]) for c in conn.cursor().execute.call_args_list]
        updates = [s for s in sqls if "UPDATE" in s]
        # 51/100 = 0.51 > 0.5 → should run
        assert len(updates) >= 1

    def test_borderline_below_threshold(self, runner):
        conn = mkconn(100)
        runner._mod.psycopg2.connect.return_value = conn
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
        runner._mod.psycopg2.connect.return_value = conn
        for i in range(48):
            runner.new_skus.add(f"SKU-{i}")
        runner.finalize()
        sqls = [str(c[0][0]) for c in conn.cursor().execute.call_args_list]
        update_sqls = [s for s in sqls if "UPDATE" in s]
        if update_sqls:
            assert "!= ALL" in update_sqls[0]

    def test_supplier_id_in_count_query(self, runner):
        conn = mkconn(200)
        runner._mod.psycopg2.connect.return_value = conn
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
        runner._mod.psycopg2.connect.return_value = conn
        for i in range(95):
            runner.new_skus.add(f"SKU-{i}")
        runner.finalize()
        sqls = [str(c[0][0]) for c in conn.cursor().execute.call_args_list]
        update_sqls = [s for s in sqls if "UPDATE" in s]
        if update_sqls:
            assert "status!='HIDDEN'" in update_sqls[0] or "status !" in update_sqls[0]
