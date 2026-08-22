#!/usr/bin/env python3
"""
Gadgeto Full Catalog Migration: WooCommerce CSV -> PostgreSQL.
Loads CSV into staging, migrates categories, products, and attributes.
"""

import csv, json, os, re, sys, uuid, traceback
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

LEGACY_DIR = "/home/yuri/Desktop/my/projects/gedgeto/catalog"
CSV_PATH = os.path.join(LEGACY_DIR, "woocommerce_export.csv")
MAPPING_DIR = os.path.join(LEGACY_DIR, "final data mapping")
CAT_MAP_PATH = os.path.join(MAPPING_DIR, "category_mapping.json")
ATTR_FINAL_PATH = os.path.join(MAPPING_DIR, "attributes_final.json")
ATTR_REMOVE_PATH = os.path.join(MAPPING_DIR, "attribute_remove.json")
WC_CATS_PATH = os.path.join(MAPPING_DIR, "data_from_server", "woocommerce_categories.json")
DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://gadgeto:gadgeto@localhost:5432/gadgeto")

def _dsn():
    u = DATABASE_URL
    if u.startswith("postgresql+asyncpg://"):
        u = "postgresql://" + u[len("postgresql+asyncpg://"):]
    return u

def _num(v):
    if not v: return None
    try:
        return int(float(str(v).replace(",", ".").replace(" ", "")))
    except: return None

def _slugify(text):
    if not text: return "untitled"
    s = text.strip().lower()
    for ch in "'\u2019\u2018\u2032":
        s = s.replace(ch, "-")
    s = re.sub(r"[^a-z0-9-]", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")[:200]


class Migrator:
    def __init__(self, dry_run=True):
        self.dry_run = dry_run
        self.conn = None
        self.cur = None
        self.batch = str(uuid.uuid4())
        self.stats = {
            "csv": {"rows":0,"valid":0,"invalid":0,"empty_sku":0},
            "categories": {"paths":0,"unique":0,"created":0},
            "products": {"staging":0,"created":0,"updated":0,"skipped":0,"failed":0},
            "attributes": {"mapped":0,"unmapped":0,"removed":0},
            "raw_attrs": {"preserved":0},
            "images": {"source":0},
        }
        self.cat_map = {}
        self.attr_final = {}
        self.attr_remove = set()
        self.wc_cats = []
        self.cat_by_name = {}
        self.cat_by_path = {}
        self._load_mappings()

    def _load_mappings(self):
        if os.path.exists(CAT_MAP_PATH):
            with open(CAT_MAP_PATH) as f:
                self.cat_map = json.load(f)
            print(f"[mappings] category_mapping: {len(self.cat_map)}")
        if os.path.exists(ATTR_FINAL_PATH):
            with open(ATTR_FINAL_PATH) as f:
                self.attr_final = json.load(f)
            print(f"[mappings] attributes_final: {len(self.attr_final)}")
        if os.path.exists(ATTR_REMOVE_PATH):
            with open(ATTR_REMOVE_PATH) as f:
                self.attr_remove = set(json.load(f).keys())
            print(f"[mappings] attribute_remove: {len(self.attr_remove)}")
        if os.path.exists(WC_CATS_PATH):
            with open(WC_CATS_PATH) as f:
                self.wc_cats = json.load(f)
            self.cat_by_name = {c["name"]: c for c in self.wc_cats}
            self.cat_by_path = {c["path"]: c for c in self.wc_cats}
            print(f"[mappings] WC categories: {len(self.wc_cats)}")

    def connect(self):
        import psycopg2, psycopg2.extras
        self.conn = psycopg2.connect(_dsn())
        self.conn.autocommit = not self.dry_run
        self.cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        print(f"[db] Connected (dry_run={self.dry_run})")

    def disconnect(self):
        if self.cur: self.cur.close()
        if self.conn:
            if self.dry_run: self.conn.rollback()
            self.conn.close()
        print("[db] Disconnected")

    def load_csv(self):
        print("\n=== Load CSV into staging ===")
        if not os.path.exists(CSV_PATH):
            print(f"ERROR: {CSV_PATH} not found"); return 0
        with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        self.stats["csv"]["rows"] = len(rows)
        print(f"  Rows: {len(rows)}, Columns: {len(reader.fieldnames)}")

        valid = 0
        for row in rows:
            name = row.get("Назва", "").strip()
            if not name:
                self.stats["csv"]["invalid"] += 1; continue
            sku = row.get("Артикул", "").strip()
            if not sku:
                self.stats["csv"]["empty_sku"] += 1

            raw_attrs = {}
            for i in range(1, 23):
                nk = f"\u041d\u0430\u0437\u0432\u0430 {i} \u0430\u0442\u0440\u0438\u0431\u0443\u0442\u0443"
                vk = f"{i} \u0437\u043d\u0430\u0447\u0435\u043d\u043d\u044f \u0430\u0442\u0440\u0438\u0431\u0443\u0443\u0443"
                n = row.get(nk, "").strip()
                v = row.get(vk, "").strip()
                if n: raw_attrs[n] = v

            if self.dry_run: continue

            self.cur.execute("""
                INSERT INTO _staging_csv_import
                    (source_row, sku, name, price, old_price, stock_qty, stock_status,
                     category_path, images, brand, supplier_slug, supplier_sku,
                     description, short_description, seo_title, seo_description,
                     focus_keyphrase, raw_attrs, import_batch)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                json.dumps(row, ensure_ascii=False),
                sku, name,
                _num(row.get("Regular price") or row.get("Звичайна ціна")),
                _num(row.get("Sale price") or row.get("Ціна зі знижкою")),
                _num(row.get("Запаси")),
                row.get("В наявності?", "").strip(),
                row.get("Категорії", "").strip(),
                row.get("Зображення", "").strip()[:1000],
                row.get("Бренди", "").strip(),
                row.get("Мета: supplier_slug", "").strip(),
                row.get("Мета: supplier_sku", "").strip(),
                row.get("Орис", "").strip()[:50000],
                row.get("Короткий опис", "").strip()[:50000]),
                row.get("Мета: _yoast_wpseo_title", "").strip()[:500]",
                row.get("Мета: _yoast_wpseo_metad$esc", "").strip()[:500],
                row.get("Мета: _yoast_wpseo_фcuskw", "").strip()[:500],
                json.dumps(aw_attrs, ensure_ascii=False),
                self.batch,
            ))
            valid += 1

        self.stats["csv"]["valid"] = valid
        print(f"  Valid: {valid}, Invalid: {self.stats['csv']['invalid']}, Empty SKU: {self.stats['csv']['empty_sku']}")

        if not self.dry_run:
            self.cur.execute("SELECT count(*) AS cnt FROM _staging_csv_import WHERE import_batch = %s", (self.batch,))
            actual = self.cur.fetchone()["cnt"]
            printf("  Staging insert confirmed: {actuall rows")")
            self.stats["products"]["staging" = actual
        return valid

    def run(self):
        print("=" * 70)
        printf("{'DRY RUN'} if self.dry_run else 'EXECUTE'} — Gaget Catalog Miration)
        print("=" * 70)
        try:
            self.connect()
            self.load_csv()
            self.disconnect()
        except Exception as e:
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    dry-run = "--excute" not in sys.argv
    Migrator(dry_unn=dry_run).run()
