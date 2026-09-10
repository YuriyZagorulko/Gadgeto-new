"""DB test: final-4 Brain mappings, idempotency, supplier isolation."""
import importlib.util
from pathlib import Path

import pytest

_TAX = str(Path(__file__).resolve().parents[1] / "app" / "imports" / "brain_taxonomy.py")


@pytest.fixture
def bt2():
    spec = importlib.util.spec_from_file_location("bt2", _TAX)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _snap(cur):
    cur.execute(
        "SELECT m.id, sc.supplier_id, sc.external_id, m.category_id"
        " FROM category_mappings m JOIN supplier_categories sc"
        " ON sc.id=m.supplier_category_id WHERE sc.supplier_id IN (1,2) ORDER BY m.id"
    )
    return [tuple(r.values()) for r in cur.fetchall()]


CATS = [
    {"categoryID": 1, "parentID": None, "realcat": 0, "name": "Root"},
    {"categoryID": 1366, "parentID": 1, "realcat": 0, "name": "Paper"},
    {"categoryID": 1402, "parentID": 1, "realcat": 0, "name": "Boxes"},
    {"categoryID": 1209, "parentID": 1, "realcat": 0, "name": "Media A"},
    {"categoryID": 1487, "parentID": 1, "realcat": 0, "name": "Media B"},
    {"categoryID": 9999, "parentID": 1, "realcat": 1366, "name": "Virt"},
]


@pytest.mark.integration
def test_final4_idempotent(bt2, db_cursor, test_settings):
    cur = db_cursor
    # Seed minimal supplier + catalog rows (rolled back at teardown).
    cur.execute(
        "INSERT INTO suppliers (id, code, name, enabled, created_at, updated_at)"
        " VALUES (1,'itlink','IT-Link',TRUE,NOW(),NOW()),"
        " (2,'dclink','DC-Link',TRUE,NOW(),NOW()),"
        " (3,'brain','BRAIN',TRUE,NOW(),NOW())"
        " ON CONFLICT (id) DO NOTHING"
    )
    cur.execute(
        "INSERT INTO categories (id, name, slug, parent_id, is_active,"
        " sort_order, created_at, updated_at) VALUES"
        " (4,'Comp','comp',NULL,TRUE,0,NOW(),NOW()),"
        " (40,'Per','per',4,TRUE,0,NOW(),NOW()),"
        " (60,'Cable','cable',40,TRUE,0,NOW(),NOW()),"
        " (126,'Photo','photo',40,TRUE,0,NOW(),NOW())"
        " ON CONFLICT (id) DO NOTHING"
    )
    before = _snap(cur)
    cur.execute("SELECT COUNT(*) FROM categories")
    n0 = cur.fetchone()["count"]
    tax = bt2.sync_brain_taxonomy(CATS, cur)
    assert tax["real"] == 5 and tax["virtual"] == 1
    t1 = bt2.ensure_final_mappings(cur)
    assert t1["1366"] == 126 and t1["1402"] == 60
    assert t1["1209"] == t1["1487"]
    mid = t1["1209"]
    cur.execute("SELECT parent_id FROM categories WHERE id=%s", (mid,))
    assert cur.fetchone()["parent_id"] == 40
    cur.execute("SELECT COUNT(*) FROM supplier_categories WHERE supplier_id=3")
    s1 = cur.fetchone()["count"]
    cur.execute(
        "SELECT COUNT(*) FROM category_mappings m"
        " JOIN supplier_categories sc ON sc.id=m.supplier_category_id"
        " WHERE sc.supplier_id=3"
    )
    m1 = cur.fetchone()["count"]
    t2 = bt2.ensure_final_mappings(cur)
    bt2.sync_brain_taxonomy(CATS, cur)
    assert t2 == t1
    cur.execute("SELECT COUNT(*) FROM supplier_categories WHERE supplier_id=3")
    assert cur.fetchone()["count"] == s1
    cur.execute(
        "SELECT COUNT(*) FROM category_mappings m"
        " JOIN supplier_categories sc ON sc.id=m.supplier_category_id"
        " WHERE sc.supplier_id=3"
    )
    assert cur.fetchone()["count"] == m1
    cur.execute("SELECT COUNT(*) FROM categories")
    assert cur.fetchone()["count"] == n0 + 1
    assert _snap(cur) == before
