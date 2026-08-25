"""
Regression tests for admin product image operations.

Tests that ``ed_images()`` correctly handles:
- Supplier images: removed from active list → suppressed (not deleted)
- Manual images: removed → deleted
- Re-import: suppressed images stay suppressed
"""

import sys
sys.path.insert(0, "/app")

import asyncio
import psycopg2
import psycopg2.extras
from app.core.db_connect import DB
from app.api.admin.product_editor import ed_images
from app.imports.import_runner import ImportRunner


def _ensure_product(cur, supplier_id: int, sku: str, name: str) -> int:
    cur.execute(
        """INSERT INTO products
           (supplier_id, supplier_sku, sku, name, slug,
            description, short_description, brand_id,
            price, old_price, currency, stock_status, stock_qty,
            is_active, is_visible,
            status, seo_title, seo_description, focus_keyphrase,
            imported_at, created_at, updated_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'UAH',%s,0,TRUE,TRUE,
                   'PUBLISHED',%s,%s,%s,NOW(),NOW(),NOW())
           RETURNING id""",
        (supplier_id, sku, sku, name, f"test-admin-img-{sku}",
         "", "", None, 0, None, "in_stock", "", "", ""),
    )
    row = cur.fetchone()
    return row["id"] if isinstance(row, dict) else row[0]


def _count_images(cur, product_id: int) -> int:
    cur.execute("SELECT count(*) FROM product_images WHERE product_id=%s", (product_id,))
    row = cur.fetchone()
    return row["count"] if isinstance(row, dict) else row[0]


def _count_active(cur, pid):
    cur.execute("SELECT count(*) FROM product_images WHERE product_id=%s AND is_suppressed=FALSE", (pid,))
    r = cur.fetchone()
    return r["count"] if isinstance(r, dict) else r[0]


def _count_suppressed(cur, pid):
    cur.execute("SELECT count(*) FROM product_images WHERE product_id=%s AND is_suppressed=TRUE", (pid,))
    r = cur.fetchone()
    return r["count"] if isinstance(r, dict) else r[0]


def _test_product_setup(cur, test_sku, supplier_id, images):
    cur.execute(
        "DELETE FROM product_images WHERE product_id IN (SELECT id FROM products WHERE supplier_sku = %s)",
        (test_sku,),
    )
    cur.execute("DELETE FROM products WHERE supplier_sku = %s", (test_sku,))
    cur.connection.commit()
    pid = _ensure_product(cur, supplier_id, test_sku, "Admin Image Test")
    runner = ImportRunner(supplier_id=supplier_id, supplier_code="itlink")
    runner._upsert_images(cur, pid, images)
    cur.connection.commit()
    return pid


def _test_cleanup(cur, test_sku):
    try:
        cur.execute(
            "DELETE FROM product_images WHERE product_id IN (SELECT id FROM products WHERE supplier_sku = %s)",
            (test_sku,),
        )
        cur.execute("DELETE FROM products WHERE supplier_sku = %s", (test_sku,))
        cur.connection.commit()
    except Exception:
        pass


def test_admin_remove_all_images():
    """
    Given a product with supplier images,
    When the admin removes ALL images and saves,
    Then all images should be suppressed (not deleted).
    """
    conn = psycopg2.connect(DB)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    TEST_SKU = "ADMIN-IMG-DEL-ALL-001"
    SUPPLIER_ID = 1
    IMG_A = "https://example.com/test-img-a.jpg"
    IMG_B = "https://example.com/test-img-b.jpg"

    try:
        product_id = _test_product_setup(cur, TEST_SKU, SUPPLIER_ID, [IMG_A, IMG_B])

        cnt_before = _count_images(cur, product_id)
        assert cnt_before == 2, f"Expected 2 images before, got {cnt_before}"

        payload = {"images": []}
        asyncio.run(ed_images(product_id, payload, None))
        conn.commit()

        # Supplier images should be suppressed, not deleted
        assert _count_images(cur, product_id) == 2, "Images should remain in DB as suppressed"
        assert _count_active(cur, product_id) == 0, "No active images"
        assert _count_suppressed(cur, product_id) == 2, "All are suppressed"
        print("  PASS: Removing ALL images suppressed them")

    finally:
        _test_cleanup(cur, TEST_SKU)
        conn.close()


def test_admin_remove_some_images():
    """
    Given a product with multiple supplier images,
    When the admin removes SOME images,
    Then removed images become suppressed, kept images remain active.
    """
    conn = psycopg2.connect(DB)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    TEST_SKU = "ADMIN-IMG-DEL-SOME-001"
    SUPPLIER_ID = 1
    IMG_A = "https://example.com/test-img-a.jpg"
    IMG_B = "https://example.com/test-img-b.jpg"
    IMG_C = "https://example.com/test-img-c.jpg"

    try:
        product_id = _test_product_setup(cur, TEST_SKU, SUPPLIER_ID, [IMG_A, IMG_B, IMG_C])

        cnt_before = _count_images(cur, product_id)
        assert cnt_before == 3, f"Expected 3 images, got {cnt_before}"

        # Keep only IMG_A and IMG_C (remove IMG_B)
        payload = {
            "images": [
                {"url": IMG_A, "is_primary": True},
                {"url": IMG_C, "is_primary": False},
            ]
        }
        asyncio.run(ed_images(product_id, payload, None))
        conn.commit()

        # All 3 images should still exist: A+C active, B suppressed
        assert _count_images(cur, product_id) == 3
        assert _count_active(cur, product_id) == 2, "A and C should be active"
        assert _count_suppressed(cur, product_id) == 1, "B should be suppressed"

        # Verify B is suppressed
        cur.execute(
            "SELECT is_suppressed FROM product_images WHERE product_id=%s AND url=%s",
            (product_id, IMG_B),
        )
        row = cur.fetchone()
        assert row is not None and row["is_suppressed"] is True, "IMG_B should be suppressed"

        print("  PASS: Removed image suppressed, kept images active")

    finally:
        _test_cleanup(cur, TEST_SKU)
        conn.close()


def test_manual_images_preserved():
    """
    Given a product with supplier and manually added images,
    When admin removes a supplier image,
    Then manually added images should remain, supplier image suppressed.
    """
    conn = psycopg2.connect(DB)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    TEST_SKU = "ADMIN-IMG-MANUAL-001"
    SUPPLIER_ID = 1
    SUPPLIER_IMG = "https://supplier.com/product.jpg"
    MANUAL_IMG = "/media/uploads/manual-image.jpg"

    try:
        product_id = _test_product_setup(cur, TEST_SKU, SUPPLIER_ID, [SUPPLIER_IMG])

        # Add a manual image (simulating admin upload)
        cur.execute(
            "INSERT INTO product_images (product_id, url, sort_order, is_primary, is_supplier_image, is_suppressed) "
            "VALUES (%s,%s,1,FALSE,FALSE,FALSE)",
            (product_id, MANUAL_IMG),
        )
        conn.commit()

        assert _count_images(cur, product_id) == 2

        # Admin: keep only manual, remove supplier
        payload = {"images": [{"url": MANUAL_IMG, "is_primary": True}]}
        asyncio.run(ed_images(product_id, payload, None))
        conn.commit()

        # Supplier image should be suppressed, manual should be active
        assert _count_images(cur, product_id) == 2
        assert _count_active(cur, product_id) == 1, "Manual should be active"
        assert _count_suppressed(cur, product_id) == 1, "Supplier should be suppressed"

        cur.execute(
            "SELECT is_suppressed FROM product_images WHERE product_id=%s AND url=%s",
            (product_id, MANUAL_IMG),
        )
        assert cur.fetchone()["is_suppressed"] is False

        print("  PASS: Manual image preserved, supplier suppressed")

    finally:
        _test_cleanup(cur, TEST_SKU)
        conn.close()


def test_importer_respects_suppressed():
    """
    When a supplier image is suppressed and the importer re-imports,
    the suppressed image stays suppressed (not reactivated).
    """
    conn = psycopg2.connect(DB)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    TEST_SKU = "ADMIN-IMG-REIMPORT-001"
    SUPPLIER_ID = 1
    IMG_A = "https://example.com/reimport-test-a.jpg"
    IMG_B = "https://example.com/reimport-test-b.jpg"

    try:
        product_id = _test_product_setup(cur, TEST_SKU, SUPPLIER_ID, [IMG_A, IMG_B])

        # Admin: keep only B (A becomes suppressed)
        payload = {"images": [{"url": IMG_B, "is_primary": True}]}
        asyncio.run(ed_images(product_id, payload, None))
        conn.commit()

        assert _count_active(cur, product_id) == 1
        assert _count_suppressed(cur, product_id) == 1

        # Re-import: supplier still provides both A and B
        runner = ImportRunner(supplier_id=SUPPLIER_ID, supplier_code="itlink")
        runner._upsert_images(cur, product_id, [IMG_A, IMG_B])
        conn.commit()

        # A should stay suppressed (importer respects suppressed state)
        assert _count_suppressed(cur, product_id) == 1, "A stays suppressed"
        assert _count_active(cur, product_id) == 1, "B stays active"

        cur.execute(
            "SELECT is_suppressed FROM product_images WHERE product_id=%s AND url=%s",
            (product_id, IMG_A),
        )
        assert cur.fetchone()["is_suppressed"] is True

        print("  PASS: Importer respects suppressed state")

    finally:
        _test_cleanup(cur, TEST_SKU)
        conn.close()
