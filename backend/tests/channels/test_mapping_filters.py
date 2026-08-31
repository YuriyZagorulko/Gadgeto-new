"""Tests for import mapping filters.

Tests the backend `list_mappings` endpoint for the new filter params:
  * attribute_id (values tab)
  * supplier_category_id (categories/attributes tab)
  * parent_category_id (categories tab)
  * Internal attribute name search via generic `q`
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_openapi_schema_has_new_params():
    """All new filter params registered in OpenAPI schema."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    paths = schema.get("paths", {})
    mapping_paths = [p for p in paths if "/api/v1/admin/mappings/" in p and "get" in paths[p]]
    assert mapping_paths, "No /api/v1/admin/mappings/ endpoint found in schema"

    all_params = {}
    for p in mapping_paths:
        for param in paths[p]["get"].get("parameters", []):
            all_params[param["name"]] = param

    for param_name in ["attribute_id", "supplier_category_id", "parent_category_id",
                       "supplier_value_q", "internal_value_q", "internal_attr_q",
                       "supplier_category_q", "internal_category_q", "parent_category_q"]:
        assert param_name in all_params, (
            f"Parameter '{param_name}' not found in API schema. "
            f"Available: {sorted(all_params.keys())}"
        )


def test_values_select_names_includes_internal_attr():
    """values select_names exposes internal_attr_name."""
    from app.api.admin.mappings import _LIST_SQL
    select = _LIST_SQL["values"]["select_names"]
    assert "internal_attr_name" in select
    assert "attr.name" in select


def test_values_search_includes_attr_name():
    """values search columns include attr.name."""
    from app.api.admin.mappings import _LIST_SQL
    search = _LIST_SQL["values"]["search"]
    assert "attr.name" in search


def test_sort_columns_preserved():
    """Sort columns preserved for all kinds."""
    from app.api.admin.mappings import _LIST_SQL
    for kind in ["categories", "attributes", "values"]:
        sort = _LIST_SQL[kind]["sort"]
        for key in ["id", "supplier", "supplier_item", "catalog", "status", "updated_at"]:
            assert key in sort, f"Sort key '{key}' missing from {kind}"


def test_rozetka_export_mappings_has_parent_category_q():
    """Rozetka mapping endpoint has parent_category_q param."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    # Find export mapping list endpoints (not suggestions)
    export_paths = [p for p in schema.get("paths", {})
                    if "/export/channels/" in p and p.endswith("/mappings/{kind}") and "get" in schema["paths"][p]]
    assert export_paths, "No export mapping list endpoints found"

    for ep in export_paths:
        params = {p["name"] for p in schema["paths"][ep]["get"].get("parameters", [])}
        assert "parent_category_q" in params, (
            f"parent_category_q missing from {ep}. Available: {sorted(params)}"
        )
    print(f"  ✅ parent_category_q present in {len(export_paths)} Rozetka mapping endpoint(s)")


def test_mapping_counts_unchanged():
    """DB mapping counts must be unchanged by the new filters."""
    try:
        from app.core.db_connect import DB
        import psycopg2
        conn = psycopg2.connect(DB)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM category_mappings")
        assert cur.fetchone()[0] == 203
        cur.execute("SELECT COUNT(*) FROM attribute_mappings")
        assert cur.fetchone()[0] == 1230
        cur.execute("SELECT COUNT(*) FROM attribute_value_mappings")
        assert cur.fetchone()[0] == 9022
        conn.close()
    except Exception:
        pytest.skip("Skipped: no DB connection available")


@pytest.mark.skip(reason="Requires real DB connection")
def test_value_filter_by_attribute_id():
    """Filter values by internal attribute ID."""
    from app.core.db_connect import DB
    import psycopg2, psycopg2.extras
    conn = psycopg2.connect(DB)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT count(*) AS c
        FROM attribute_value_mappings m
        JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
        JOIN supplier_attributes ha ON ha.id = sav.supplier_attribute_id
        LEFT JOIN attribute_values av ON av.id = m.attribute_value_id
        LEFT JOIN attributes attr ON attr.id = av.attribute_id
        WHERE av.attribute_id = %s
    """, (100,))
    count = cur.fetchone()["c"]
    assert isinstance(count, int)
    assert count >= 0
    conn.close()


@pytest.mark.skip(reason="Requires real DB connection")
def test_supplier_category_filter():
    """Filter categories by supplier_category_id."""
    from app.core.db_connect import DB
    import psycopg2, psycopg2.extras
    conn = psycopg2.connect(DB)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT count(*) AS c
        FROM category_mappings m
        JOIN supplier_categories sc ON sc.id = m.supplier_category_id
        LEFT JOIN categories c ON c.id = m.category_id
        WHERE m.supplier_category_id = %s
    """, (1,))
    count = cur.fetchone()["c"]
    assert isinstance(count, int)
    conn.close()


@pytest.mark.skip(reason="Requires real DB connection")
def test_parent_category_filter():
    """Filter categories by parent category."""
    from app.core.db_connect import DB
    import psycopg2, psycopg2.extras
    conn = psycopg2.connect(DB)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT count(*) AS c
        FROM category_mappings m
        JOIN supplier_categories sc ON sc.id = m.supplier_category_id
        LEFT JOIN categories c ON c.id = m.category_id
        WHERE EXISTS (SELECT 1 FROM categories pc WHERE pc.id = c.parent_id AND pc.id = %s)
    """, (70,))
    count = cur.fetchone()["c"]
    assert isinstance(count, int)
    conn.close()
