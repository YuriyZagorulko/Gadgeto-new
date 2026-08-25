"""
Real database regression test for image deduplication in _upsert_images().

Scenario:
  Import #1: Product X -> image URL A
  Import #2: Product X -> image URL A
  Import #3: Product X -> image URL A
  Import #4: Product X -> image URL A + image URL B
  Import #5: Product X -> image URL B only (supplier replaced A->B)
  Import #6: Product X -> no images (empty list)
"""

import sys
sys.path.insert(0, "/app")

import psycopg2
import psycopg2.extras
from app.core.db_connect import DB
from app.imports.import_runner import ImportRunner


def main():
    TEST_SKU = "IMGTEST-DUP-001"
    SUPPLIER_ID = 1

    conn = psycopg2.connect(DB)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        cur.execute("DELETE FROM product_images WHERE product_id IN (SELECT id FROM products WHERE supplier_sku = %s)", (TEST_SKU,))
        cur.execute("DELETE FROM products WHERE supplier_sku = %s", (TEST_SKU,))
        conn.commit()

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
            (SUPPLIER_ID, TEST_SKU, TEST_SKU, "Image Test Product", "img-test-dup-001",
             "", "", None, 0, None, "in_stock", "", "", ""),
        )
        product_id = cur.fetchone()["id"]
        conn.commit()
        print(f"Product ID: {product_id}")

        runner = ImportRunner(supplier_id=SUPPLIER_ID, supplier_code="dclink")
        IMG_A = "https://example.com/test-image-a.jpg"
        IMG_B = "https://example.com/test-image-b.jpg"

        # STEP 1
        print("\n=== IMPORT 1: Image A ===")
        runner._upsert_images(cur, product_id, [IMG_A])
        cur.execute("SELECT count(*) as cnt FROM product_images WHERE product_id = %s", (product_id,))
        cnt1 = cur.fetchone()["cnt"]
        print(f"  Records: {cnt1}")
        assert cnt1 == 1, f"Expected 1, got {cnt1}"
        print("  PASS")

        # STEP 2
        print("\n=== IMPORT 2: Image A (again) ===")
        runner._upsert_images(cur, product_id, [IMG_A])
        cur.execute("SELECT count(*) as cnt FROM product_images WHERE product_id = %s", (product_id,))
        cnt2 = cur.fetchone()["cnt"]
        print(f"  Records: {cnt2}")
        assert cnt2 == 1, f"Expected 1, got {cnt2}"
        print("  PASS - no duplicate created")

        # STEP 3
        print("\n=== IMPORT 3: Image A (3rd time) ===")
        runner._upsert_images(cur, product_id, [IMG_A])
        cur.execute("SELECT count(*) as cnt FROM product_images WHERE product_id = %s", (product_id,))
        cnt3 = cur.fetchone()["cnt"]
        print(f"  Records: {cnt3}")
        assert cnt3 == 1, f"Expected 1, got {cnt3}"
        print("  PASS - idempotent after 3 identical imports")

        # STEP 4
        print("\n=== IMPORT 4: Image A + Image B ===")
        runner._upsert_images(cur, product_id, [IMG_A, IMG_B])
        cur.execute("SELECT count(*) as cnt FROM product_images WHERE product_id = %s", (product_id,))
        cnt4 = cur.fetchone()["cnt"]
        print(f"  Records: {cnt4}")
        assert cnt4 == 2, f"Expected 2, got {cnt4}"
        cur.execute("SELECT url, sort_order, is_primary FROM product_images WHERE product_id = %s ORDER BY sort_order", (product_id,))
        rows = cur.fetchall()
        for r in rows:
            print(f"    url={r['url'][:50]} sort={r['sort_order']} primary={r['is_primary']}")
        assert rows[0]["is_primary"] == True
        assert rows[1]["is_primary"] == False
        print("  PASS - A is primary, B is secondary")

        # STEP 5
        print("\n=== IMPORT 5: Image B only (supplier replaced A->B) ===")
        runner._upsert_images(cur, product_id, [IMG_B])
        cur.execute(
            "SELECT count(*) as cnt, array_agg(url ORDER BY sort_order) as urls FROM product_images WHERE product_id = %s",
            (product_id,),
        )
        row = cur.fetchone()
        cnt5 = row["cnt"]
        urls = row["urls"]
        print(f"  Total records: {cnt5}")
        for u in urls:
            print(f"    {u[:50]}")
        assert IMG_A not in urls, "IMG_A should be removed (supplier no longer provides it)"
        assert IMG_B in urls, "IMG_B should be re-inserted"
        print("  PASS - old supplier image removed when no longer in feed")

        # STEP 6
        print("\n=== IMPORT 6: No images (empty list) ===")
        runner._upsert_images(cur, product_id, [])
        cur.execute("SELECT count(*) as cnt FROM product_images WHERE product_id = %s", (product_id,))
        cnt6 = cur.fetchone()["cnt"]
        print(f"  Records: {cnt6}")
        assert cnt6 == cnt5, "Empty list should be no-op"
        print("  PASS - no change")

        print("\n" + "=" * 50)
        print("FINAL VERDICT: ALL 6 TESTS PASSED")
        print("=" * 50)
        print("  [OK] 3x identical imports  -> 1 record (no duplicates)")
        print("  [OK] Add distinct URL      -> 2 records")
        print("  [OK] Supplier URL change   -> old removed, new inserted")
        print("  [OK] Empty list            -> no-op")
        print("  [OK] sort_order & is_primary correct")

        # Cleanup
        cur.execute("DELETE FROM product_images WHERE product_id = %s", (product_id,))
        cur.execute("DELETE FROM products WHERE id = %s", (product_id,))
        conn.commit()
        print("\nCleanup done.")

    except Exception as e:
        conn.rollback()
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        try:
            cur.execute("DELETE FROM product_images WHERE product_id IN (SELECT id FROM products WHERE supplier_sku = %s)", (TEST_SKU,))
            cur.execute("DELETE FROM products WHERE supplier_sku = %s", (TEST_SKU,))
            conn.commit()
        except Exception:
            pass
        conn.close()


if __name__ == "__main__":
    main()
