"""Regression tests for category breadcrumb traversal (no infinite loops)."""
import sys
sys.path.insert(0, "backend")

import pytest
import psycopg2
import psycopg2.extras
from app.core.db_connect import DB


def _db():
    conn = psycopg2.connect(DB)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn, cur


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


def test_root_category():
    conn, cur = _db()
    try:
        cur.execute("SELECT id, parent_id FROM categories WHERE parent_id IS NULL AND is_active = true LIMIT 1")
        root = cur.fetchone()
        if not root:
            pytest.skip("No root category found")
        crumbs = _breadcrumbs_from(root["parent_id"], cur)
        assert len(crumbs) == 0
    finally:
        conn.close()


def test_child_category():
    conn, cur = _db()
    try:
        cur.execute("""
            SELECT id, parent_id FROM categories c1
            WHERE c1.parent_id IS NOT NULL
              AND EXISTS (SELECT 1 FROM categories c2 WHERE c2.id = c1.parent_id)
              AND c1.is_active = true
            LIMIT 1
        """)
        cat = cur.fetchone()
        if not cat:
            pytest.skip("No child category found")
        crumbs = _breadcrumbs_from(cat["parent_id"], cur)
        assert len(crumbs) >= 1
        assert crumbs[-1]["id"] == cat["parent_id"]
    finally:
        conn.close()


def test_multi_level_category():
    conn, cur = _db()
    try:
        cur.execute("""
            SELECT c3.id, c3.parent_id
            FROM categories c3
            JOIN categories c2 ON c2.id = c3.parent_id
            JOIN categories c1 ON c1.id = c2.parent_id
            WHERE c1.parent_id IS NULL
              AND c3.is_active = true AND c2.is_active = true AND c1.is_active = true
            LIMIT 1
        """)
        cat = cur.fetchone()
        if not cat:
            pytest.skip("No 3-level category found")
        crumbs = _breadcrumbs_from(cat["parent_id"], cur)
        assert len(crumbs) >= 2
    finally:
        conn.close()


def test_cycle_detection():
    conn, cur = _db()
    try:
        cur.execute(
            "INSERT INTO categories (name, slug, parent_id, is_active, sort_order, created_at, updated_at) "
            "VALUES ('T_CYC_A', 't-cycle-a', NULL, true, 9999, NOW(), NOW()) RETURNING id"
        )
        a_id = cur.fetchone()["id"]
        cur.execute(
            "INSERT INTO categories (name, slug, parent_id, is_active, sort_order, created_at, updated_at) "
            "VALUES ('T_CYC_B', 't-cycle-b', %s, true, 9999, NOW(), NOW()) RETURNING id",
            (a_id,)
        )
        b_id = cur.fetchone()["id"]
        cur.execute("UPDATE categories SET parent_id = %s WHERE id = %s", (b_id, a_id))
        pid = b_id
        visited = set()
        count = 0
        max_iter = 20
        while pid and pid not in visited and count < max_iter:
            visited.add(pid)
            count += 1
            cur.execute("SELECT id, parent_id FROM categories WHERE id = %s", (pid,))
            p = cur.fetchone()
            if p:
                pid = p["parent_id"]
            else:
                break
        assert count < max_iter, f"Cycle: exceeded {max_iter} iterations"
        assert pid in visited
        cur.execute("DELETE FROM categories WHERE id IN (%s, %s)", (a_id, b_id))
    finally:
        conn.close()


def test_product_no_infinite_loop():
    conn, cur = _db()
    try:
        cur.execute("""
            SELECT p.id FROM products p
            JOIN product_categories pc ON pc.product_id = p.id
            JOIN categories c ON c.id = pc.category_id
            WHERE c.parent_id IS NOT NULL AND c.is_active = true
              AND p.is_active = true LIMIT 1
        """)
        prod = cur.fetchone()
        if not prod:
            pytest.skip("No product in child category found")
        cur.execute("""
            SELECT c.id, c.parent_id FROM product_categories pc
            JOIN categories c ON c.id = pc.category_id
            WHERE pc.product_id = %s
        """, (prod["id"],))
        cats = cur.fetchall()
        assert len(cats) > 0
        crumbs = _breadcrumbs_from(cats[0]["parent_id"], cur)
        assert len(crumbs) >= 1
    finally:
        conn.close()
