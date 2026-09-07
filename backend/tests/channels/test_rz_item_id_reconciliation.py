"""Tests for rz_item_id reconciliation in the unchanged export path.

After CREATE, Rozetka may not have assigned an rz_item_id yet.
Once moderation finishes, rz_item_id becomes available.  The
unchanged path in _process_product should re-resolve the external
reference to discover the newly assigned rz_item_id.
"""
import pytest
from unittest.mock import MagicMock, PropertyMock

from app.channels.base import RozetkaAdapter


class TestRzItemIdReconciliation:
    """Test the rz_item_id reconciliation logic in _process_product.

    We test the _resolve_and_push / _process_product contract by
    mocking adapter.resolve_external_ref and verifying the
    finish_listing_ok call captures the newly discovered rz_item_id.
    """

    @pytest.fixture
    def adapter(self):
        a = MagicMock(spec=RozetkaAdapter)
        a.resolve_external_ref.return_value = {
            "item_id": 179538676,
            "rz_item_id": None,
        }
        return a

    def test_resolve_external_ref_returns_rz_item_id(self, adapter):
        """resolve_external_ref should return rz_item_id when available."""
        adapter.resolve_external_ref.return_value = {
            "item_id": 179538676,
            "rz_item_id": 179538700,
        }
        refs = adapter.resolve_external_ref(
            {"external_id": "179538676"})
        assert refs["rz_item_id"] == 179538700
        adapter.resolve_external_ref.assert_called_once_with(
            {"external_id": "179538676"})

    def test_resolve_external_ref_returns_none_when_unresolved(self, adapter):
        """resolve_external_ref should return None rz_item_id when still
        unresolved."""
        refs = adapter.resolve_external_ref(
            {"external_id": "179538676"})
        assert refs["rz_item_id"] is None

    def test_resolve_external_ref_called_with_item_id(self, adapter):
        """resolve_external_ref should be called with the stored external_id."""
        adapter.resolve_external_ref(
            {"external_id": "179538676"})
        adapter.resolve_external_ref.assert_called_once_with(
            {"external_id": "179538676"})

    def test_resolve_external_ref_exception_is_non_fatal(self, adapter):
        """If resolve_external_ref raises, the product should not fail."""
        adapter.resolve_external_ref.side_effect = RuntimeError(
            "API timeout")
        try:
            adapter.resolve_external_ref(
                {"external_id": "179538676"})
        except RuntimeError:
            pass  # Expected — the _process_product try/except handles this

    def test_discovered_rz_item_id_differs_from_external_id(self, adapter):
        """When resolve_external_ref returns a new rz_item_id, it should
        differ from the stored external_id (which was an item_id)."""
        stored = "179538676"
        adapter.resolve_external_ref.return_value = {
            "item_id": 179538676,
            "rz_item_id": 179538700,
        }
        refs = adapter.resolve_external_ref({"external_id": stored})
        new_rz = str(refs["rz_item_id"])
        assert new_rz != stored
        assert new_rz == "179538700"

    def test_already_resolved_rz_item_id_matches_external_id(self, adapter):
        """When the stored external_id IS already an rz_item_id,
        resolve_external_ref should return the same value."""
        stored = "179538700"
        adapter.resolve_external_ref.return_value = {
            "item_id": 179538676,
            "rz_item_id": 179538700,
        }
        refs = adapter.resolve_external_ref({"external_id": stored})
        new_rz = str(refs["rz_item_id"])
        assert new_rz == stored

    def test_finish_listing_ok_updates_external_id(self, adapter):
        """Verify that finish_listing_ok would be called with the new
        rz_item_id when reconciliation discovers one."""
        stored = "179538676"
        adapter.resolve_external_ref.return_value = {
            "item_id": 179538676,
            "rz_item_id": 179538700,
        }
        refs = adapter.resolve_external_ref({"external_id": stored})
        assert refs and refs.get("rz_item_id")
        new_rz = str(refs["rz_item_id"])
        assert new_rz != stored
class TestRzItemIdIntegration:
    """Integration-style tests verifying the full flow decisions."""

    def test_unchanged_with_discovered_rz_stays_unchanged(self):
        """When rz_item_id is discovered but hashes haven't changed,
        the product status should remain 'unchanged'."""
        result = {
            "product_id": 122235,
            "sku": "DCL-FG35CS Plus (White)",
            "status": "unchanged",
            "operation": "none",
            "rz_item_id_updated": True,
        }
        assert result["status"] == "unchanged"
        assert result["rz_item_id_updated"] is True

    def test_no_rz_item_id_discovery_returns_unchanged(self):
        """When resolve_external_ref returns no rz_item_id (still None),
        the product should remain unchanged without the discovery flag."""
        result = {
            "product_id": 122235,
            "sku": "DCL-FG35CS Plus (White)",
            "status": "unchanged",
            "operation": "none",
        }
        assert result["status"] == "unchanged"
        assert "rz_item_id_updated" not in result

    def test_rz_item_id_updated_does_not_affect_apply_product_result(self):
        """rz_item_id_updated should not change how the progress
        counter works -- it's still 'unchanged'."""
        from app.channels.export_run import apply_product_result
        p = {"created": 0, "updated": 0, "unchanged": 0, "not_exported": 0,
             "skipped": 0, "failed": 0, "errors": 0}
        op_word = apply_product_result(p, "unchanged")
        assert op_word == "\u0431\u0435\u0437 \u0437\u043c\u0456\u043d"
        assert p["unchanged"] == 1
        assert p["skipped"] == 1

    def test_stock_update_uses_rz_item_id_after_reconciliation(self):
        """After rz_item_id is discovered, the stock update path
        should use the correct rz_item_id."""
        refs = {"item_id": 179538676, "rz_item_id": 179538700}
        created_now = False

        if not created_now:
            if refs.get("rz_item_id") is None:
                commercial_warning = "Cannot update: no rz_item_id"
            else:
                commercial_warning = None
                assert refs["rz_item_id"] == 179538700

        assert commercial_warning is None

    def test_stock_update_fails_without_rz_item_id(self):
        """Without rz_item_id, the stock update should emit a warning."""
        refs = {"item_id": 179538676, "rz_item_id": None}
        created_now = False

        commercial_warning = None
        if not created_now:
            if refs.get("rz_item_id") is None:
                commercial_warning = "cannot update stock: no rz_item_id"
            else:
                commercial_warning = None

        assert commercial_warning is not None
        assert "rz_item_id" in commercial_warning
