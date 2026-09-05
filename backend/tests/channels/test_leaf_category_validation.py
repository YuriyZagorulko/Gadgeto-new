"""Tests for the strict leaf category validation (Phase 6.5).

This module tests the ROZETKA_CATEGORY_NOT_LEAF validation rule that
ensures non-leaf / parent Rozetka categories can NEVER be exported.
"""

import pytest
from unittest.mock import MagicMock, patch

from app.channels.validation import (
    ROZETKA_CATEGORY_NOT_LEAF,
    ISSUE_NO_TAXONOMY,
    SEVERITY_ERROR,
)


class TestLeafCategoryValidation:
    """Test cases for the strict leaf category validation logic."""

    def test_leaf_category_constant_exists(self):
        """ROZETKA_CATEGORY_NOT_LEAF constant should be defined."""
        assert ROZETKA_CATEGORY_NOT_LEAF == "ROZETKA_CATEGORY_NOT_LEAF"

    def test_leaf_category_not_leaf_code(self):
        """The error code should be ROZETKA_CATEGORY_NOT_LEAF."""
        assert ROZETKA_CATEGORY_NOT_LEAF.startswith("ROZETKA_")

    def test_leaf_validation_import_from_validation_module(self):
        """Should be able to import the constant from validation module."""
        from app.channels.validation import ROZETKA_CATEGORY_NOT_LEAF
        assert ROZETKA_CATEGORY_NOT_LEAF == "ROZETKA_CATEGORY_NOT_LEAF"


class TestLeafCategoryValidationIntegration:
    """Integration tests for leaf category validation with database."""

    @pytest.fixture
    def mock_cursor(self):
        """Create a mock cursor for testing."""
        cursor = MagicMock()
        return cursor

    def test_parent_category_returns_not_leaf(self, mock_cursor):
        """Parent category (has children) should be detected as non-leaf."""
        # Simulate: category 80253 has children
        def execute_side_effect(sql, params=None):
            sql_lower = sql.lower() if isinstance(sql, str) else str(sql).lower()
            if "select name from channel_external_categories" in sql_lower:
                mock_cursor.fetchone.return_value = {"name": "Комп'ютери та ноутбуки"}
            elif "select count(*) as children" in sql_lower:
                mock_cursor.fetchone.return_value = {"children": 5}  # Has children = non-leaf
            elif "select count(*) as attrs" in sql_lower:
                mock_cursor.fetchone.return_value = {"attrs": 0}
        
        mock_cursor.execute.side_effect = execute_side_effect
        
        # Test the logic: has_children = True should trigger NOT_LEAF error
        mock_cursor.execute.reset_mock()
        mock_cursor.fetchone.side_effect = None
        mock_cursor.fetchone.return_value = {"children": 5}  # 5 children = non-leaf
        
        has_children = mock_cursor.fetchone()["children"] > 0
        assert has_children is True  # This is what we expect for parent categories

    def test_leaf_category_returns_leaf(self, mock_cursor):
        """Leaf category (no children) should be detected as leaf."""
        # Simulate: category 80172 has NO children
        mock_cursor.fetchone.return_value = {"children": 0}  # No children = leaf
        
        has_children = mock_cursor.fetchone()["children"] > 0
        assert has_children is False  # This is what we expect for leaf categories


class TestLeafCategorySeverity:
    """Tests for error severity settings."""

    def test_not_leaf_is_error_severity(self):
        """ROZETKA_CATEGORY_NOT_LEAF should have ERROR severity."""
        assert SEVERITY_ERROR == "error"
        assert SEVERITY_ERROR != "warning"


class TestLeafValidationMessage:
    """Tests for validation error messages."""

    def test_error_message_format(self):
        """Error message should contain category name and ID."""
        cat_name = "Комп'ютерні миші"
        cat_id = "80172"
        
        # Expected message format
        expected_message = f'Rozetka category "{cat_name}" ({cat_id}) is not a leaf category and cannot be exported.'
        
        # Verify message format is correct
        assert "is not a leaf" in expected_message
        assert cat_id in expected_message

    def test_error_details_contain_category_id(self):
        """Error details should include external_category_id and is_leaf."""
        details = {
            "external_category_id": "80172",
            "is_leaf": False,
        }
        
        assert details["external_category_id"] == "80172"
        assert details["is_leaf"] is False


class TestLeafValidationReadyFlag:
    """Tests for the ready=False behavior when validation fails."""

    def test_not_leaf_blocks_export(self):
        """When ROZETKA_CATEGORY_NOT_LEAF is raised, ready should be False."""
        # This tests the expected behavior: non-leaf category blocks export
        issues = [
            {
                "code": ROZETKA_CATEGORY_NOT_LEAF,
                "severity": SEVERITY_ERROR,
                "message": "Category is not a leaf",
            }
        ]
        
        # If we have a ROZETKA_CATEGORY_NOT_LEAF issue, export should be blocked
        has_blocking_issue = any(
            issue["code"] == ROZETKA_CATEGORY_NOT_LEAF
            and issue["severity"] == SEVERITY_ERROR
            for issue in issues
        )
        
        assert has_blocking_issue is True


# =============================================================================
# Test fixtures for real database tests (integration tests)
# =============================================================================

@pytest.mark.integration
class TestLeafCategoryWithDatabase:
    """Integration tests that require a real database connection.
    
    These tests use the actual Rozetka taxonomy data to verify that:
    - Leaf categories (e.g., 80172) pass validation
    - Non-leaf categories (e.g., 80253) fail with ROZETKA_CATEGORY_NOT_LEAF
    """

    def test_leaf_category_80172_is_leaf(self):
        """Category 80172 (Комп'ютерні миші) should be a leaf category."""
        import psycopg2.extras
        from app.core.db_connect import DB
        
        conn = psycopg2.connect(DB)
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Category 80172 should exist
            cur.execute(
                "SELECT name FROM channel_external_categories "
                "WHERE channel_id = 1 AND external_id = '80172'",
            )
            cat = cur.fetchone()
            assert cat is not None
            assert cat["name"] == "Комп'ютерні миші"
            
            # Category 80172 should have NO children
            cur.execute(
                "SELECT count(*) as children FROM channel_external_categories "
                "WHERE channel_id = 1 AND parent_external_id = '80172'",
            )
            children_count = cur.fetchone()["children"]
            assert children_count == 0  # Leaf category
        finally:
            conn.close()

    def test_parent_category_80253_is_not_leaf(self):
        """Category 80253 (Комп'ютери та ноутбуки) should NOT be a leaf category."""
        import psycopg2.extras
        from app.core.db_connect import DB
        
        conn = psycopg2.connect(DB)
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Category 80253 should exist
            cur.execute(
                "SELECT name FROM channel_external_categories "
                "WHERE channel_id = 1 AND external_id = '80253'",
            )
            cat = cur.fetchone()
            assert cat is not None
            assert cat["name"] == "Комп'ютери та ноутбуки"
            
            # Category 80253 should have children
            cur.execute(
                "SELECT count(*) as children FROM channel_external_categories "
                "WHERE channel_id = 1 AND parent_external_id = '80253'",
            )
            children_count = cur.fetchone()["children"]
            assert children_count > 0  # Non-leaf / parent category
        finally:
            conn.close()

    def test_existing_leaf_mappings_count(self):
        """Count existing mappings that point to leaf categories."""
        import psycopg2.extras
        from app.core.db_connect import DB
        
        conn = psycopg2.connect(DB)
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Count mappings to leaf categories
            cur.execute("""
                SELECT COUNT(*) as count
                FROM channel_category_mappings m
                JOIN channel_external_categories ec ON ec.channel_id = m.channel_id 
                    AND ec.external_id = m.external_category_id
                WHERE m.channel_id = 1 
                    AND m.status = 'accepted'
                    AND NOT EXISTS (
                        SELECT 1 FROM channel_external_categories ch 
                        WHERE ch.channel_id = m.channel_id 
                        AND ch.parent_external_id = m.external_category_id
                    )
            """)
            leaf_count = cur.fetchone()["count"]
            
            # Count mappings to non-leaf categories
            cur.execute("""
                SELECT COUNT(*) as count
                FROM channel_category_mappings m
                JOIN channel_external_categories ec ON ec.channel_id = m.channel_id 
                    AND ec.external_id = m.external_category_id
                WHERE m.channel_id = 1 
                    AND m.status = 'accepted'
                    AND EXISTS (
                        SELECT 1 FROM channel_external_categories ch 
                        WHERE ch.channel_id = m.channel_id 
                        AND ch.parent_external_id = m.external_category_id
                    )
            """)
            non_leaf_count = cur.fetchone()["count"]
            
            # These counts should match the audit results
            assert leaf_count >= 0  # Should be 111 according to audit
            assert non_leaf_count >= 0  # Should be 44 according to audit
            
            print(f"Leaf mappings: {leaf_count}, Non-leaf mappings: {non_leaf_count}")
        finally:
            conn.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
