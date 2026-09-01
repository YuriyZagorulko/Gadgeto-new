"""Tests for the admin attributes list endpoint (filters, sorting, pagination).

Covers the params added for the attributes admin page:
  * parent_category_id — filter attributes by category subtree
  * sort_by / sort_order — server-side column sorting
"""

import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException
from unittest.mock import MagicMock, patch

from app.main import app

client = TestClient(app)


def test_openapi_schema_registers_new_params():
    """GET /attributes registers parent_category_ids, sort_by, sort_order."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    paths = schema.get("paths", {})

    ep = "/api/v1/admin/attributes"
    assert ep in paths and "get" in paths[ep], f"GET {ep} not found in schema"
    params = {p["name"] for p in paths[ep]["get"].get("parameters", [])}
    for name in ["parent_category_ids", "sort_by", "sort_order"]:
        assert name in params, f"Parameter '{name}' missing from {ep}. Available: {sorted(params)}"


def test_sort_columns_whitelist():
    """All sortable columns of the attributes page are whitelisted."""
    from app.api.admin.attributes import SORT_COLUMNS
    for key in ["name", "type", "values_count", "products_count", "categories_count"]:
        assert key in SORT_COLUMNS, f"Sort key '{key}' missing"


def test_invalid_sort_by_rejected():
    """Unknown sort columns are rejected with 400 before running any query."""
    from app.api.admin.attributes import list_attributes

    conn = MagicMock()
    cur = conn.cursor.return_value
    with patch("app.api.admin.attributes.admin_cursor", return_value=(conn, cur)), \
            pytest.raises(HTTPException) as exc:
        list_attributes(page=1, per_page=20, search=None, q=None,
                        parent_category_ids=None, sort_by="nope; DROP TABLE attributes",
                        sort_order="asc", user={})
    assert exc.value.status_code == 400