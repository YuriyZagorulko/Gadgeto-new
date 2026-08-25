"""
Product persistence layer for supplier importers.

Takes NormalizedProduct objects from IT-Link or DC-Link importers and
persists them to PostgreSQL (categories, attributes, values, products,
images). This replaces the old CSV->WooCommerce bridge.

Progress is reported via the job callback so the Admin UI can poll it.
"""

import json
import re
from datetime import datetime
from typing import Callable, List, Optional, Tuple

import psycopg2
import psycopg2.extras

from app.core.db_connect import DB

ProgressFn = Callable[[str, int, int, int, int, int, int, str], None]


def _slugify(text: str) -> str:
    _T = str.maketrans({
        '\u0430': 'a', '\u0431': 'b', '\u0432': 'v', '\u0433': 'h', '\u0491': 'g',
        '\u0434': 'd', '\u0435': 'e', '\u0454': 'ie', '\u0436': 'zh', '\u0437': 'z',
        '\u0438': 'y', '\u0456': 'i', '\u0457': 'i', '\u0439': 'i', '\u043a': 'k',
        '\u043b': 'l', '\u043c': 'm', '\u043d': 'n', '\u043e': 'o', '\u043f': 'p',
        '\u0440': 'r', '\u0441': 's', '\u0442': 't', '\u0443': 'u', '\u0444': 'f',
        '\u0445': 'kh', '\u0446': 'ts', '\u0447': 'ch', '\u0448': 'sh', '\u0449': 'shch',
        '\u044c': '', '\u044e': 'iu', '\u044f': 'ia', "'": '', '\u2019': '',
        '\u044b': 'y', '\u044d': 'e', '\u044a': '', '\u0451': 'e',
    })
    s = text.strip().lower().translate(_T)
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s[:120] or 'product'


def _unique_slug(cur, base: str, table: str, column: str = 'slug') -> str:
    slug = base
    i = 2
    while True:
        cur.execute(f'SELECT 1 FROM {table} WHERE {column} = %s', (slug,))
        if not cur.fetchone():
            return slug
        slug = f'{base}-{i}'
        i += 1


class ImportRunner:
    """
    Orchestrates persistence of a parsed supplier feed into PostgreSQL.
    """

    def __init__(self, supplier_id: int, supplier_code: str,
                 progress_cb=None, mark_removed_products: bool = True,
                 image_storage_mode: str = "supplier_url"):
        self.supplier_id = supplier_id
        self.supplier_code = supplier_code
        self.progress_cb = progress_cb
        self.mark_removed = mark_removed_products
        self.image_storage_mode = image_storage_mode  # "supplier_url" or "local"
        self.total = 0
        self.processed = 0
        self.created = 0
        self.updated = 0
        self.skipped = 0
        self.failed = 0
        self.new_skus: set = set()
        self.warnings: list = []
        self.errors: list = []

    def _progress(self, stage: str, message: str = ''):
        if self.progress_cb:
            self.progress_cb(stage, self.total, self.processed,
                             self.created, self.updated, self.skipped,
                             self.failed, message)

    def initialize(self):
        self._progress('initializing', '\u0406\u043d\u0456\u0446\u0456\u0430\u043b\u0456\u0437\u0430\u0446\u0456\u044f \u0456\u043c\u043f\u043e\u0440\u0442\u0443')

    def finalize(self):
        if not self.mark_removed:
            self._progress('finalizing', '\u0417\u0430\u0432\u0435\u0440\u0448\u0435\u043d\u043d\u044f')
            return
        conn = psycopg2.connect(DB)
        cur = conn.cursor()
        hidden = 0
        try:
            skus = list(self.new_skus)
            if not skus:
                return
            self._progress('finalizing', '\u041f\u0440\u0438\u0445\u043e\u0432\u0443\u0432\u0430\u043d\u043d\u044f \u0442\u043e\u0432\u0430\u0440\u0456\u0432, \u0432\u0456\u0434\u0441\u0443\u0442\u043d\u0456\u0445 \u0443 \u0444\u0456\u0434\u0456')
            cur.execute(
                """UPDATE products SET status='HIDDEN', is_visible=FALSE, is_active=FALSE,
                           updated_at=NOW()
                   WHERE supplier_id=%s AND status!='HIDDEN'
                     AND supplier_sku IS NOT NULL AND supplier_sku!=''
                     AND supplier_sku != ALL(%s::text[])""",
                (self.supplier_id, skus),
            )
            hidden = cur.rowcount
            conn.commit()
        finally:
            conn.close()
        if hidden:
            self.warnings.append(f"{hidden} \u0442\u043e\u0432\u0430\u0440\u0456\u0432 \u043f\u0440\u0438\u0445\u043e\u0432\u0430\u043d\u043e, \u0432\u0456\u0434\u0441\u0443\u0442\u043d\u0456 \u0443 \u0444\u0456\u0434\u0456")
        self._progress('finalizing', f'{hidden} \u0442\u043e\u0432\u0430\u0440\u0456\u0432 \u043f\u0440\u0438\u0445\u043e\u0432\u0430\u043d\u043e')

    def create_category(self, name: str):
        conn = psycopg2.connect(DB)
        cur = conn.cursor()
        try:
            cur.execute('SELECT id FROM categories WHERE name = %s', (name,))
            row = cur.fetchone()
            if row:
                return row[0]
            slug = _unique_slug(cur, _slugify(name), 'categories')
            cur.execute(
                """INSERT INTO categories (name, slug, is_active, sort_order,
                                          created_at, updated_at)
                   VALUES (%s, %s, TRUE, 0, NOW(), NOW())
                   ON CONFLICT (slug) DO NOTHING RETURNING id""",
                (name, slug),
            )
            row = cur.fetchone()
            if row:
                conn.commit()
                return row[0]
            cur.execute('SELECT id FROM categories WHERE slug = %s', (slug,))
            row = cur.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def create_attribute(self, name: str):
        conn = psycopg2.connect(DB)
        cur = conn.cursor()
        try:
            cur.execute('SELECT id FROM attributes WHERE name = %s', (name,))
            row = cur.fetchone()
            if row:
                return row[0]
            slug = _unique_slug(cur, _slugify(name), 'attributes')
            cur.execute(
                """INSERT INTO attributes (name, slug, is_global, is_filterable,
                                          sort_order, created_at, updated_at)
                   VALUES (%s, %s, TRUE, FALSE, 0, NOW(), NOW())
                   ON CONFLICT (slug) DO NOTHING RETURNING id""",
                (name, slug),
            )
            row = cur.fetchone()
            if row:
                conn.commit()
                return row[0]
            cur.execute('SELECT id FROM attributes WHERE slug = %s', (slug,))
            row = cur.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def create_attribute_value(self, attr_id: int, value: str):
        conn = psycopg2.connect(DB)
        cur = conn.cursor()
        try:
            cur.execute(
                'SELECT id FROM attribute_values WHERE attribute_id=%s AND value=%s',
                (attr_id, value),
            )
            row = cur.fetchone()
            if row:
                return row[0]
            slug = _unique_slug(cur, _slugify(value), 'attribute_values')
            cur.execute(
                """INSERT INTO attribute_values (attribute_id, value, slug, sort,
                                                is_active, created_at, updated_at)
                   VALUES (%s, %s, %s, 0, TRUE, NOW(), NOW()) RETURNING id""",
                (attr_id, value, slug),
            )
            row = cur.fetchone()
            if row:
                conn.commit()
                return row[0]
            return None
        finally:
            conn.close()

    def persist_product(self, prod):
        """Persist one NormalizedProduct. Returns ('created'|'updated'|'error', id)."""
        conn = psycopg2.connect(DB)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            # Validate product name — guard against attribute name leaking into product name
            prod_name = (prod.name or "").strip()
            if not prod_name:
                self.warnings.append(f"Empty product name for SKU {prod.sku or prod.supplier_sku} — skipping")
                self.skipped += 1
                return ('skipped', 0)
            if len(prod_name) < 3:
                self.warnings.append(f"Unusually short product name '{prod_name}' for SKU {prod.sku or prod.supplier_sku}")

            # Resolve category path
            category_ids = []
            if prod.category_path:
                for part in ([c.strip() for c in prod.category_path.split('>')]):
                    cid = self.create_category(part)
                    if cid:
                        category_ids.append(cid)

            # Resolve brand
            brand_id = None
            if prod.brand:
                cur.execute('SELECT id FROM brands WHERE name = %s', (prod.brand,))
                row = cur.fetchone()
                if row:
                    brand_id = row['id']

            slug = _unique_slug(cur, _slugify(prod.name or 'product'), 'products')

            existing_id = None
            if prod.supplier_sku:
                cur.execute(
                    'SELECT id FROM products WHERE supplier_id=%s AND supplier_sku=%s',
                    (self.supplier_id, prod.supplier_sku),
                )
                row = cur.fetchone()
                if row:
                    existing_id = row['id']

            stock_status = 'in_stock' if prod.in_stock else 'out_of_stock'
            short_desc = getattr(prod, 'short_description', '') or ''

            if existing_id:
                self._update_product(cur, prod, existing_id, slug, brand_id,
                                     stock_status, short_desc, category_ids)
                conn.commit()
                self.updated += 1
                self.new_skus.add(prod.supplier_sku)
                return ('updated', existing_id)

            return self._insert_product(cur, prod, slug, brand_id, stock_status,
                                        short_desc, category_ids, conn)
        except Exception as e:
            conn.rollback()
            self.failed += 1
            self.errors.append(f'{prod.sku or prod.supplier_sku}: {e}')
            return ('error', 0)
        finally:
            conn.close()

    def _update_product(self, cur, prod, existing_id, slug, brand_id,
                        stock_status, short_desc, category_ids):
        cur.execute(
            """UPDATE products SET name=%s, slug=%s, description=%s,
                      short_description=%s, price=%s, old_price=%s,
                      stock_status=%s, is_active=TRUE, is_visible=TRUE,
                      status='PUBLISHED', brand_id=%s,
                      seo_title=%s, seo_description=%s, focus_keyphrase=%s,
                      imported_at=NOW(), updated_at=NOW()
               WHERE id=%s""",
            (prod.name, slug, prod.description, short_desc,
             prod.price, prod.old_price, stock_status,
             brand_id, prod.seo_title, prod.seo_description,
             prod.focus_keyphrase, existing_id),
        )
        if category_ids:
            cur.execute('DELETE FROM product_categories WHERE product_id=%s', (existing_id,))
            for cid in category_ids:
                cur.execute(
                    'INSERT INTO product_categories (product_id, category_id) VALUES (%s,%s) ON CONFLICT DO NOTHING',
                    (existing_id, cid),
                )
        self._upsert_attributes(cur, existing_id, prod.attributes)
        self._upsert_images(cur, existing_id, prod.images)

    def _insert_product(self, cur, prod, slug, brand_id, stock_status,
                        short_desc, category_ids, conn):
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
            (self.supplier_id, prod.supplier_sku, prod.sku or '', prod.name, slug,
             prod.description, short_desc, brand_id,
             prod.price, prod.old_price, stock_status,
             prod.seo_title, prod.seo_description, prod.focus_keyphrase),
        )
        row = cur.fetchone()
        new_id = row['id']
        for cid in category_ids:
            cur.execute(
                'INSERT INTO product_categories (product_id, category_id) VALUES (%s,%s) ON CONFLICT DO NOTHING',
                (new_id, cid),
            )
        self._upsert_attributes(cur, new_id, prod.attributes)
        self._upsert_images(cur, new_id, prod.images)
        conn.commit()
        self.created += 1
        self.new_skus.add(prod.supplier_sku)
        return ('created', new_id)

    def _upsert_attributes(self, cur, product_id, attributes):
        if not attributes:
            return
        cur.execute('DELETE FROM product_attributes WHERE product_id=%s', (product_id,))
        for attr_name, attr_value in attributes:
            a_id = self.create_attribute(attr_name)
            if a_id:
                self.create_attribute_value(a_id, attr_value)
                cur.execute(
                    """INSERT INTO product_attributes
                       (product_id, attribute_id, value_text, created_at, updated_at)
                       VALUES (%s,%s,%s,NOW(),NOW())""",
                    (product_id, a_id, attr_value),
                )

    def _upsert_images(self, cur, product_id, images):
        if not images:
            return

        # Collect URLs to import (strip whitespace, filter empty)
        urls_to_import = []
        for img_url in images:
            if img_url and img_url.strip():
                urls_to_import.append(img_url.strip())

        if not urls_to_import:
            return

        # Step 1: For each URL in the feed, check if it already exists.
        #   - If existing + suppressed → keep suppressed (update sort_order)
        #   - If existing + active     → keep active (update sort_order)
        #   - If new                   → INSERT with is_supplier_image=TRUE
        for i, url in enumerate(urls_to_import):
            media_id = None
            if self.image_storage_mode == "local" and (url.startswith("http://") or url.startswith("https://")):
                from app.imports.image_helper import download_supplier_image
                result = download_supplier_image(url, cur)
                if result:
                    url = result["url"]
                    media_id = result["media_id"]
                else:
                    self.warnings.append(f"Не вдалося завантажити зображення: {url}")
                    # Fall back to storing the supplier URL so the product
                    # still has an image reference

            # Check if this URL already exists for this product
            cur.execute(
                "SELECT id, is_suppressed FROM product_images WHERE product_id = %s AND url = %s",
                (product_id, url),
            )
            existing = cur.fetchone()

            if existing:
                existing_id = existing["id"] if isinstance(existing, dict) else existing[0]
                existing_suppressed = existing["is_suppressed"] if isinstance(existing, dict) else existing[1]
                # Always update sort_order and primary flag
                cur.execute(
                    "UPDATE product_images SET sort_order = %s, is_primary = %s WHERE id = %s",
                    (i, i == 0, existing_id),
                )
                if existing_suppressed:
                    pass  # Keep suppressed — admin's choice takes precedence
                else:
                    pass  # Keep active
            else:
                cur.execute(
                    """INSERT INTO product_images (product_id, url, media_id, is_primary,
                                                   sort_order, is_supplier_image, is_suppressed,
                                                   created_at, updated_at)
                       VALUES (%s,%s,%s,%s,%s,TRUE,FALSE,NOW(),NOW())""",
                    (product_id, url, media_id, i == 0, i),
                )

        # Step 2: Remove supplier images that are NO LONGER in the feed.
        # This only affects supplier-originated images (is_supplier_image=TRUE).
        # Suppressed images that the supplier no longer provides are also deleted.
        # Manual images (is_supplier_image=FALSE) are NEVER touched by the importer.
        cur.execute(
            "DELETE FROM product_images WHERE product_id = %s AND is_supplier_image = TRUE AND NOT (url = ANY(%s))",
            (product_id, urls_to_import),
        )
