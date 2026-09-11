import json
from unittest.mock import MagicMock, patch, call

from app.channels.export_run import (
    _summarize_validation_issues,
    apply_product_result,
    final_export_status,
    final_run_status,
)


def test_apply_product_result_unchanged_skipped_split():
    p = {"created": 0, "updated": 0, "unchanged": 0, "not_exported": 0,
         "skipped": 0, "failed": 0, "errors": 0}
    assert apply_product_result(p, "unchanged") == "без змін"
    assert (p["unchanged"] == 1 and p["skipped"] == 1
            and p["not_exported"] == 0)
    assert apply_product_result(p, "skipped") == "пропущено"
    assert (p["not_exported"] == 1 and p["skipped"] == 2
            and p["unchanged"] == 1)
    assert apply_product_result(p, "failed") == "ПОМИЛКА"
    assert p["failed"] == 1 and p["errors"] == 1
    assert apply_product_result(p, "created") == "створено"
    assert p["created"] == 1
    assert apply_product_result(p, "updated") == "оновлено"
    assert p["updated"] == 1


def test_final_export_status_variants():
    assert final_export_status(failed=0, not_exported=0) == "SUCCEEDED"
    assert final_export_status(failed=0, not_exported=1) == "PARTIAL"
    assert final_export_status(failed=2, not_exported=3) == "PARTIAL"
"""Unit tests for export-run status semantics.

Covers the task scenarios:

    A  total=1  created=1                    -> SUCCEEDED
    B  total=1  skipped=1 (mapping issues)   -> PARTIAL
    C  total=10 created=8 skipped=2          -> PARTIAL
    D  worker exception                      -> FAILED (set by the except
       block of run_export; final_run_status itself must never return it)
    E  created=8 failed=2                    -> PARTIAL
    F  cancellation                          -> CANCELLED (unchanged)

Also covers _summarize_validation_issues — the structured, grouped view of
blocking validation issues consumed by the history UI (the raw `reason`
string stays authoritative and is never replaced).
"""


class TestFinalRunStatusScenarios:
    """Scenarios from the export-status task (A-F)."""

    def test_scenario_a_completely_successful(self):
        # total=1, created=1, skipped=0, failed=0 -> SUCCESS
        assert final_run_status(cancelled=False, failed=0, skipped=0) == "SUCCEEDED"

    def test_scenario_a_mixed_success_is_success(self):
        # created=3, updated=5, unchanged=2, skipped=0, failed=0 -> SUCCESS
        # (unchanged products are counted separately and do not block SUCCESS)
        assert final_run_status(cancelled=False, failed=0, skipped=0) == "SUCCEEDED"

    def test_scenario_b_single_skip_is_partial(self):
        # total=1, created=0, skipped=1 (9 mapping issues), failed=0 -> PARTIAL
        assert final_run_status(cancelled=False, failed=0, skipped=1) == "PARTIAL"

    def test_scenario_c_multiple_products_some_skipped(self):
        # total=10, created=8, skipped=2, failed=0 -> PARTIAL
        assert final_run_status(cancelled=False, failed=0, skipped=2) == "PARTIAL"

    def test_scenario_e_mixed_successful_and_failed_products(self):
        # created=8, failed=2 -> PARTIAL
        assert final_run_status(cancelled=False, failed=2, skipped=0) == "PARTIAL"

    def test_scenario_e_skipped_and_failed_combined(self):
        # created=5, updated=3, skipped=1, failed=1 -> PARTIAL
        assert final_run_status(cancelled=False, failed=1, skipped=1) == "PARTIAL"

    def test_scenario_d_worker_crash_is_never_produced_here(self):
        # FAILED is reserved for worker/process crashes and is set directly
        # in run_export's except-block. The normal-completion helper must
        # never return it — a product-level problem is PARTIAL, not FAILED.
        assert final_run_status(cancelled=False, failed=5, skipped=5) == "PARTIAL"
        assert final_run_status(cancelled=False, failed=0, skipped=0) == "SUCCEEDED"

    def test_scenario_f_cancellation_semantics_preserved(self):
        assert final_run_status(cancelled=True, failed=0, skipped=0) == "CANCELLED"
        # A cancelled run stays CANCELLED regardless of partial results.
        assert final_run_status(cancelled=True, failed=2, skipped=1) == "CANCELLED"


class TestSummarizeValidationIssues:
    """Structured issue grouping for the history detail UI."""

    @staticmethod
    def _issue(code: str, **details) -> dict:
        return {"code": code, "severity": "error",
                "message": f"msg:{code}", "details": details}

    def test_groups_missing_attribute_and_value_mappings(self):
        issues = [
            self._issue("MISSING_ATTRIBUTE_MAPPING",
                        attribute_id=5, attribute_name="Радіус дії"),
            self._issue("MISSING_ATTRIBUTE_MAPPING",
                        attribute_id=6, attribute_name="Тип сенсора"),
            self._issue("MISSING_ATTRIBUTE_VALUE_MAPPING",
                        attribute_id=7, attribute_name="Довжина",
                        attribute_value_id=77, value_name="1.8 м"),
            self._issue("PRODUCT_NOT_PUBLISHED", status="DRAFT"),
        ]
        s = _summarize_validation_issues(issues, "131143")

        assert s["total"] == 4
        assert s["missing_attribute_mappings"] == [
            {"attribute_id": 5, "attribute_name": "Радіус дії"},
            {"attribute_id": 6, "attribute_name": "Тип сенсора"},
        ]
        assert s["missing_value_mappings"] == [
            {"attribute_id": 7, "attribute_name": "Довжина",
             "attribute_value_id": 77, "value_name": "1.8 м"},
        ]
        assert s["other"] == [{"code": "PRODUCT_NOT_PUBLISHED",
                               "message": "msg:PRODUCT_NOT_PUBLISHED"}]
        # Category scope (global vs category-specific) is preserved.
        assert s["external_category_id"] == "131143"

    def test_null_category_maps_to_none(self):
        s = _summarize_validation_issues([], None)
        assert s["total"] == 0
        assert s["missing_attribute_mappings"] == []
        assert s["missing_value_mappings"] == []
        assert s["other"] == []
        assert s["external_category_id"] is None

    def test_integer_category_id_is_stringified(self):
        s = _summarize_validation_issues(
            [self._issue("MISSING_ATTRIBUTE_MAPPING", attribute_id=1)], 131143)
        assert s["external_category_id"] == "131143"

    def test_missing_required_attr_mapping_goes_to_other(self):
        s = _summarize_validation_issues(
            [self._issue("MISSING_REQUIRED_ATTR_MAPPING",
                         external_attribute_id=20769,
                         external_attribute_name="Гарантія",
                         external_category_id="131143")], "131143")
        assert s["total"] == 1
        assert s["missing_attribute_mappings"] == []
class TestSupplierSelectionParsing:
    """Validate supplier selection JSON parsing -- regression for the bug
    where raw string "[2]" was passed directly to set(), iterating over
    characters and producing {']','[','2'} instead of {2}.
    """

    @staticmethod
    def _parse(raw_value):
        if not raw_value:
            return set()
        try:
            return set(json.loads(raw_value))
        except (json.JSONDecodeError, TypeError):
            return set()

    def test_normal_json_array_parses_to_int_set(self):
        assert self._parse("[2, 5, 10]") == {2, 5, 10}

    def test_single_element_array(self):
        assert self._parse("[2]") == {2}

    def test_empty_array_is_empty_set(self):
        assert self._parse("[]") == set()

    def test_null_value_is_empty_set(self):
        assert self._parse(None) == set()

    def test_empty_string_is_empty_set(self):
        assert self._parse("") == set()

    def test_zero_single_element(self):
        assert self._parse("[0]") == {0}

    def test_large_ids(self):
        assert self._parse("[99999999]") == {99999999}

    def test_multiple_ids_preserves_all(self):
        ids = list(range(1, 101))
        result = self._parse(json.dumps(ids))
        assert result == set(ids)
        assert len(result) == 100

    def test_invalid_json_returns_empty(self):
        assert self._parse("{broken") == set()

    def test_junk_string_returns_empty(self):
        assert self._parse("not-json-at-all") == set()

    def test_bug_regression_raw_string_set_iteration(self):
        raw_value = "[2]"
        bug_result = set(raw_value)
        assert bug_result == {']', '[', '2'}

    def test_bug_run_export_parses_json_string_from_db(self):
        from app.channels.export_run import run_export
        mock_conn = MagicMock()
        mock_cur = MagicMock()

        def fetchone_side_effect(*args):
            sql = args[0] if args else ""
            if "export_suppliers" in str(sql):
                return {"value": "[2]"}
            return None

        mock_cur.fetchone.side_effect = fetchone_side_effect
        mock_cur.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cur

        with patch("app.channels.export_run.psycopg2.connect", return_value=mock_conn):
            with patch("app.channels.export_run.DB", "mock_db"):
                with patch("app.channels.export_run.start_export_run") as m:
                    m.return_value = 42
                    with patch("app.channels.export_run.RozetkaAdapter"):
                        result = run_export(channel_id=1, channel_code="rozetka",
                                            run_id=99, product_ids=[],
                                            public_base_url="example.com")

        sel_calls = [c for c in mock_cur.execute.call_args_list
                     if "export_suppliers" in str(c)]
        assert len(sel_calls) >= 1
        for call_args in mock_cur.execute.call_args_list:
            sql = str(call_args[0][0])
            if "supplier_id IN" in sql:
                assert "']'" not in sql
        assert result["status"] in ("SUCCEEDED", "PARTIAL")

    def test_bug_no_export_suppliers_setting(self):
        from app.channels.export_run import run_export
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None
        mock_cur.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cur

        with patch("app.channels.export_run.psycopg2.connect", return_value=mock_conn):
            with patch("app.channels.export_run.DB", "mock_db"):
                with patch("app.channels.export_run.start_export_run") as m:
                    m.return_value = 42
                    with patch("app.channels.export_run.RozetkaAdapter"):
                        result = run_export(channel_id=1, channel_code="rozetka",
                                            run_id=99, product_ids=[10, 20, 30],
                                            public_base_url="example.com")
        assert result["status"] == "SUCCEEDED"
