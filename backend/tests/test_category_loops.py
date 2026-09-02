"""Regression tests for category breadcrumb traversal (no infinite loops).

These tests use the ``db_connection`` fixture from ``conftest.py``, which
provides a psycopg2 connection wrapped in an outer transaction. Every
INSERT/UPDATE/DELETE the tests perform is rolled back at teardown, so
no test data is left behind in the test database.
"""
import pytest

# All tests in this module talk to a real PostgreSQL test DB.
pytestmark = pytest.mark.integration


def _breadcrumbs_from(pid, cur):
    breadcrumbs = []
    visited = set()
    while pid and pid not in visited:
        visited.add(pid)
        cur.execute("SELECT id, name, slug, parent_id FROM categories WHERE id = %s", (pid,))
        p = cur.fetchone()
        if p:
            breadcrumbs.insert(0, {"id": p["id"], "name": p["name"], "slug": p["slug"]})
            pid = p["parent_id"]
        else:
            break
    return breadcrumbs


def test_root_category(db_cursor):
    """A root category (parent_id IS NULL) yields no breadcrumbs."""
    db_cursor.execute(
        "SELECT id, parent_id FROM categories WHERE parent_id IS NULL AND is_active = true LIMIT 1"
    )
    root = db_cursor.fetchone()
    if not root:
        pytest.skip("No root category found")
    crumbs = _breadcrumbs_from(root["parent_id"], db_cursor)
    assert len(crumbs) == 0


def test_child_category(db_cursor):
    """A direct child category produces one breadcrumb pointing at its parent."""
    db_cursor.execute("""
        SELECT id, parent_id FROM categories c1
        WHERE c1.parent_id IS NOT NULL
          AND EXISTS (SELECT 1 FROM categories c2 WHERE c2.id = c1.parent_id)
          AND c1.is_active = true
        LIMIT 1
    """)
    cat = db_cursor.fetchone()
    if not cat:
        pytest.skip("No child category found")
    crumbs = _breadcrumbs_from(cat["parent_id"], db_cursor)
    assert len(crumbs) >= 1
    assert crumbs[-1]["id"] == cat["parent_id"]


def test_multi_level_category(db_cursor):
    """A category at depth 3+ yields at least two breadcrumbs."""
    db_cursor.execute("""
        SELECT c3.id, c3.parent_id
        FROM categories c3
        JOIN categories c2 ON c2.id = c3.parent_id
        JOIN categories c1 ON c1.id = c2.parent_id
        WHERE c1.parent_id IS NULL
          AND c3.is_active = true AND c2.is_active = true AND c1.is_active = true
        LIMIT 1
    """)
    cat = db_cursor.fetchone()
    if not cat:
        pytest.skip("No 3-level category found")
    crumbs = _breadcrumbs_from(cat["parent_id"], db_cursor)
    assert len(crumbs) >= 2


def test_cycle_detection(db_cursor):
    """A self-referential cycle is detected without hanging.

    The test creates two synthetic categories (``T_CYC_A`` and
    ``T_CYC_B``) and wires them into a cycle. The cycle is detected in
    fewer than ``max_iter`` iterations. INSERT/UPDATE/DELETE are all
    rolled back by the ``db_connection`` fixture when the test ends.
    """
    db_cursor.execute(
        "INSERT INTO categories (name, slug, parent_id, is_active, sort_order, created_at, updated_at) "
        "VALUES ('T_CYC_A', 't-cycle-a', NULL, true, 9999, NOW(), NOW()) RETURNING id"
    )
    a_id = db_cursor.fetchone()["id"]
    db_cursor.execute(
        "INSERT INTO categories (name, slug, parent_id, is_active, sort_order, created_at, updated_at) "
        "VALUES ('T_CYC_B', 't-cycle-b', %s, true, 9999, NOW(), NOW()) RETURNING id",
        (a_id,),
    )
    b_id = db_cursor.fetchone()["id"]
    db_cursor.execute(
        "UPDATE categories SET parent_id = %s WHERE id = %s", (b_id, a_id)
    )

    pid = b_id
    visited = set()
    count = 0
    max_iter = 20
    while pid and pid not in visited and count < max_iter:
        visited.add(pid)
        count += 1
        db_cursor.execute(
            "SELECT id, parent_id FROM categories WHERE id = %s", (pid,)
        )
        p = db_cursor.fetchone()
        if p:
            pid = p["parent_id"]
        else:
            break
    assert count < max_iter, f"Cycle: exceeded {max_iter} iterations"
    assert pid in visited
    # No explicit DELETE needed: the outer transaction is rolled back.


def test_product_no_infinite_loop(db_cursor):
    """A product's category breadcrumb traversal terminates."""
    db_cursor.execute("""
        SELECT p.id FROM products p
        JOIN product_categories pc ON pc.product_id = p.id
        JOIN categories c ON c.id = pc.category_id
        WHERE c.parent_id IS NOT NULL AND c.is_active = true
          AND p.is_active = true LIMIT 1
    """)
    prod = db_cursor.fetchone()
    if not prod:
        pytest.skip("No product in child category found")
    db_cursor.execute("""
        SELECT c.id, c.parent_id FROM product_categories pc
        JOIN categories c ON c.id = pc.category_id
        WHERE pc.product_id = %s
    """, (prod["id"],))
    cats = db_cursor.fetchall()
    assert len(cats) > 0
    crumbs = _breadcrumbs_from(cats[0]["parent_id"], db_cursor)
    assert len(crumbs) >= 1
