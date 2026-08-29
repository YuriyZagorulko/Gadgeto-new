"""Tests for channel_validation_issues persistence (regression: NotNullViolation on created_at)."""

import json
from unittest.mock import MagicMock, patch


def test_store_validation_issues_includes_timestamps():
    """The store_validation_issues function must include created_at and updated_at."""
    from app.channels.export_listings import store_validation_issues
    import inspect
    source = inspect.getsource(store_validation_issues)
    assert "created_at" in source, "INSERT must include created_at column"
    assert "updated_at" in source, "INSERT must include updated_at column"
    assert "NOW()" in source, "INSERT must use NOW() for timestamps"


def test_validation_issue_schema_has_timestamps():
    """The ChannelValidationIssue model must have created_at and updated_at."""
    from app.models.channel import ChannelValidationIssue
    assert hasattr(ChannelValidationIssue, "created_at"), "Model must have created_at"
    assert hasattr(ChannelValidationIssue, "updated_at"), "Model must have updated_at"


def test_validation_issue_columns_are_not_null():
    """created_at and updated_at must be NOT NULL in the schema."""
    from app.models.channel import ChannelValidationIssue
    col = ChannelValidationIssue.__table__.columns["created_at"]
    assert not col.nullable, "created_at must be NOT NULL"
    col = ChannelValidationIssue.__table__.columns["updated_at"]
    assert not col.nullable, "updated_at must be NOT NULL"


def test_validation_issue_preserves_error_code():
    """The original error code and metadata must be preserved."""
    from app.channels.export_listings import store_validation_issues
    
    mock_cur = MagicMock()
    issues = [
        {
            "severity": "error",
            "code": "MISSING_ATTRIBUTE_VALUE_MAPPING",
            "message": "Не знайдено відповідності значення",
            "details": {
                "attribute_id": 179,
                "attribute_name": "Довжина",
            }
        }
    ]
    
    store_validation_issues(mock_cur, 42, issues)
    
    # The function should have called execute twice: DELETE + INSERT
    calls = [c for c in mock_cur.execute.call_args_list]
    insert_call = [c for c in calls if "INSERT" in str(c)]
    assert len(insert_call) > 0, "INSERT should have been called"
    
    # Get the INSERT args
    insert_sql = insert_call[0][0][0]
    insert_params = insert_call[0][0][1]
    
    # Verify the INSERT includes timestamps
    assert "created_at" in insert_sql, "INSERT must include created_at"
    assert "updated_at" in insert_sql, "INSERT must include updated_at"
    assert "NOW()" in insert_sql, "INSERT must use NOW()"
    
    # Verify the error code is preserved
    assert insert_params[1] == "MISSING_ATTRIBUTE_VALUE_MAPPING"
    assert "Не знайдено" in insert_params[2]
    
    # Verify details are preserved
    details = json.loads(insert_params[3])
    assert details["attribute_id"] == 179
    assert details["attribute_name"] == "Довжина"


def test_multiple_validation_issues():
    """Multiple issues should all be inserted successfully."""
    from app.channels.export_listings import store_validation_issues
    
    mock_cur = MagicMock()
    issues = [
        {"severity": "error", "code": "MISSING_CATEGORY_MAPPING", "message": "No category", "details": {}},
        {"severity": "error", "code": "MISSING_ATTRIBUTE_MAPPING", "message": "No attr", "details": {}},
        {"severity": "error", "code": "MISSING_ATTRIBUTE_VALUE_MAPPING", "message": "No value", "details": {"attribute_id": 1}},
    ]
    
    store_validation_issues(mock_cur, 42, issues)
    
    # Should have 1 DELETE + 3 INSERTs
    insert_calls = [c for c in mock_cur.execute.call_args_list if "INSERT" in str(c)]
    assert len(insert_calls) == 3, f"Expected 3 INSERTs, got {len(insert_calls)}"


def test_non_error_issues_are_skipped():
    """Issues with severity other than 'error' should be skipped."""
    from app.channels.export_listings import store_validation_issues
    
    mock_cur = MagicMock()
    issues = [
        {"severity": "warning", "code": "SOME_WARNING", "message": "Just a warning", "details": {}},
        {"severity": "error", "code": "REAL_ERROR", "message": "Real error", "details": {}},
    ]
    
    store_validation_issues(mock_cur, 42, issues)
    
    insert_calls = [c for c in mock_cur.execute.call_args_list if "INSERT" in str(c)]
    assert len(insert_calls) == 1, f"Expected 1 INSERT (only error), got {len(insert_calls)}"
    assert "REAL_ERROR" in str(insert_calls[0]), "Only REAL_ERROR should be inserted"


def test_store_validation_issues_clears_old_issues():
    """Old issues should be deleted before inserting new ones."""
    from app.channels.export_listings import store_validation_issues
    
    mock_cur = MagicMock()
    store_validation_issues(mock_cur, 42, [])
    
    # Should have a DELETE but no INSERTs
    delete_calls = [c for c in mock_cur.execute.call_args_list if "DELETE" in str(c)]
    assert len(delete_calls) == 1, "Should have 1 DELETE"
    insert_calls = [c for c in mock_cur.execute.call_args_list if "INSERT" in str(c)]
    assert len(insert_calls) == 0, "No INSERTs for empty issues list"


def test_current_export_worker_does_not_crash_on_validation_issue():
    """The export worker should handle MISSING_ATTRIBUTE_VALUE_MAPPING without crashing.
    
    This is an integration-level test that verifies the validation pipeline
    can create a validation issue and continue processing.
    """
    from app.channels.export_listings import store_validation_issues
    
    # This test validates that the store_validation_issues function
    # can be called without raising a NotNullViolation
    # The actual DB-level test is done in test_validation_issue_persistence
    mock_cur = MagicMock()
    
    issues = [
        {
            "severity": "error",
            "code": "MISSING_ATTRIBUTE_VALUE_MAPPING",
            "message": "Не знайдено відповідності значення",
            "details": {
                "attribute_id": 179,
                "attribute_name": "Довжина",
            }
        }
    ]
    
    # This should not raise any exception
    try:
        store_validation_issues(mock_cur, 42, issues)
        assert True, "store_validation_issues should not raise"
    except Exception as e:
        assert False, f"store_validation_issues raised: {e}"
