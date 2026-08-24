#!/usr/bin/env python3
"""
Import legacy normalization mappings (JSON -> database).

Source files (supplier-agnostic global maps prepared previously):
    attributes_final.json             {raw_attr: internal_attr}
    attribute_remove.json             {raw_attr: true}                      (excluded)
    attribute_value_mapping_final.json {internal_attr: {raw_value: internal_value}}
    attribute_value_to_remove.json     {internal_attr: [raw_value, ...]}     (excluded)
    category_mapping.json             {raw_category: internal_category}

Behaviour:
- The JSON files contain NO supplier information. Every rule is therefore
  imported once PER system supplier (itlink, dclink), making the mapping layer
  supplier-specific while preserving every prepared rule.
- Precedence mirrors app.imports.attribute_processor.process_attribute():
  removal lists WIN over regular mappings.
- Idempotent: dictionary rows are found by natural keys, mapping rows are
  upserted through the unique indexes added by migration 013. Re-running only
  updates in place — never duplicates.
- Records whose internal target does not exist in the catalog are stored with
  a NULL target (status stays "Маппінг") and listed in the unresolved report,
  so they can be linked manually in the admin UI. Nothing is discarded.

Usage:
    python import_legacy_mappings.py            # dry run (transaction rollback)
    python import_legacy_mappings.py --apply    # real import
"""
import argparse
import json
import os
import sys
from datetime import datetime

import psycopg2
import psycopg2.extras

DEFAULT_DSN = "dbname=gadgeto user=gadgeto password=gadgeto host=localhost port=5432"
MAPPING_DIR = "/home/yuri/Desktop/my/projects/gedgeto/catalog/final data mapping"
SYSTEM_SUPPLIERS = ["itlink", "dclink"]  # must match backend/app/imports/registry.py

# ---------------------------------------------------------------- helpers

_T = str.maketrans({
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'h', 'ґ': 'g', 'д': 'd', 'е': 'e',
    'є': 'ie', 'ж': 'zh', 'з': 'z', 'и': 'y', 'і': 'i', 'ї': 'i', 'й': 'i',
    'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
    'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch',
    'ш': 'sh', 'щ': 'shch', 'ь': '', 'ю': 'iu', 'я': 'ia', "'": '', '’': '',
    'ы': 'y', 'э': 'e', 'ъ': '', 'ё': 'e',
})


def slugify(text: str) -> str:
    s = str(text).strip().lower().translate(_T)
    s = "".join(ch if ch.isalnum() else "-" for ch in s)
    s = "-".join(p for p in s.split("-") if p)
    return s[:120] or "value"


def load_json(base, name):
    with open(os.path.join(base, name), encoding="utf-8") as f:
        return json.load(f)


class Importer:
    def __init__(self, cur):
        self.cur = cur
        self.stats = {}
        self.unresolved = {"categories": {}, "attributes": {}, "values": {}}
        self._cat_cache = {}
        self._attr_cache = {}

    def bump(self, key, n=1):
        self.stats[key] = self.stats.get(key, 0) + n

    # ---- internal catalog lookups -----------------------------------------
    def internal_category_id(self, name):
        if name not in self._cat_cache:
            self.cur.execute("SELECT id FROM categories WHERE name = %s", (name,))
            row = self.cur.fetchone()
            self._cat_cache[name] = row[0] if row else None
        return self._cat_cache[name]

    def internal_attribute_id(self, name):
        if name not in self._attr_cache:
            self.cur.execute("SELECT id FROM attributes WHERE name = %s", (name,))
            row = self.cur.fetchone()
            self._attr_cache[name] = row[0] if row else None
        return self._attr_cache[name]

    def internal_value_id(self, attr_id, value):
        """Find or create the internal attribute value; None when attr unknown."""
        if attr_id is None:
            return None
        self.cur.execute(
            "SELECT id FROM attribute_values WHERE attribute_id = %s AND value = %s",
            (attr_id, value),
        )
        row = self.cur.fetchone()
        if row:
            return row[0]
        base = slugify(value)
        slug, i = base, 2
        while True:
            self.cur.execute("SELECT 1 FROM attribute_values WHERE slug = %s", (slug,))
            if not self.cur.fetchone():
                break
            slug, i = f"{base}-{i}", i + 1
        self.cur.execute(
            """INSERT INTO attribute_values (attribute_id, value, slug, sort, is_active,
                                            created_at, updated_at)
               VALUES (%s, %s, %s, 0, TRUE, NOW(), NOW())
               ON CONFLICT (attribute_id, value) DO UPDATE SET updated_at = NOW()
               RETURNING id""",
            (attr_id, value, slug),
        )
        self.bump("internal_values_created")
        return self.cur.fetchone()[0]

    # ---- supplier dictionary upserts --------------------------------------
    def supplier_id(self, code):
        self.cur.execute("SELECT id FROM suppliers WHERE code = %s", (code,))
        row = self.cur.fetchone()
        return row[0] if row else None

    def _find_or_create(self, sql_find, args_find, sql_insert, args_insert):
        self.cur.execute(sql_find, args_find)
        row = self.cur.fetchone()
        if row:
            return row[0], False
        self.cur.execute(sql_insert, args_insert)
        return self.cur.fetchone()[0], True

    def sc(self, sid, name):
        return self._find_or_create(
            "SELECT id FROM supplier_categories WHERE supplier_id=%s AND supplier_name=%s",
            (sid, name),
            """INSERT INTO supplier_categories (supplier_id, supplier_name, is_removed,
                                                created_at, updated_at)
               VALUES (%s, %s, FALSE, NOW(), NOW()) RETURNING id""",
            (sid, name))

    def sa(self, sid, name):
        return self._find_or_create(
            "SELECT id FROM supplier_attributes WHERE supplier_id=%s AND supplier_name=%s",
            (sid, name),
            """INSERT INTO supplier_attributes (supplier_id, supplier_name, is_removed,
                                                created_at, updated_at)
               VALUES (%s, %s, FALSE, NOW(), NOW()) RETURNING id""",
            (sid, name))

    def sav(self, said, value):
        return self._find_or_create(
            """SELECT id FROM supplier_attribute_values
               WHERE supplier_attribute_id=%s AND supplier_value=%s""",
            (said, value),
            """INSERT INTO supplier_attribute_values (supplier_attribute_id, supplier_value,
                                                      is_removed, created_at, updated_at)
               VALUES (%s, %s, FALSE, NOW(), NOW()) RETURNING id""",
            (said, value))

    # ---- mapping upserts (idempotent via migration-013 unique indexes) ----
    def map_category(self, supplier_category_id, category_id, is_active):
        self.cur.execute(
            """INSERT INTO category_mappings (supplier_category_id, category_id, is_active,
                                              created_at, updated_at)
               VALUES (%s, %s, %s, NOW(), NOW())
               ON CONFLICT (supplier_category_id) DO UPDATE
                   SET category_id = EXCLUDED.category_id,
                       is_active   = EXCLUDED.is_active,
                       updated_at  = NOW()
               RETURNING (xmax = 0) AS inserted""",
            (supplier_category_id, category_id, is_active),
        )
        return self.cur.fetchone()[0]

    def map_attribute(self, supplier_attribute_id, attribute_id, is_active):
        self.cur.execute(
            """INSERT INTO attribute_mappings (supplier_attribute_id, attribute_id, is_active,
                                               created_at, updated_at)
               VALUES (%s, %s, %s, NOW(), NOW())
               ON CONFLICT (supplier_attribute_id) DO UPDATE
                   SET attribute_id = EXCLUDED.attribute_id,
                       is_active    = EXCLUDED.is_active,
                       updated_at   = NOW()
               RETURNING (xmax = 0) AS inserted""",
            (supplier_attribute_id, attribute_id, is_active),
        )
        return self.cur.fetchone()[0]

    def map_value(self, sav_id, attribute_value_id, is_active):
        self.cur.execute(
            """INSERT INTO attribute_value_mappings (supplier_attribute_value_id,
                                                     attribute_value_id, is_active,
                                                     created_at, updated_at)
               VALUES (%s, %s, %s, NOW(), NOW())
               ON CONFLICT (supplier_attribute_value_id) DO UPDATE
                   SET attribute_value_id = EXCLUDED.attribute_value_id,
                       is_active          = EXCLUDED.is_active,
                       updated_at         = NOW()
               RETURNING (xmax = 0) AS inserted""",
            (sav_id, attribute_value_id, is_active),
        )
        return self.cur.fetchone()[0]

    # ---- import phases -----------------------------------------------------
    def import_categories(self, sid, code, cm):
        for raw, internal in cm.items():
            sc_id, created = self.sc(sid, raw)
            target = self.internal_category_id(internal)
            if target is None:
                self.unresolved["categories"].setdefault(internal, []).append(f"{code}:{raw}")
            inserted = self.map_category(sc_id, target, True)
            self.bump("categories_inserted" if inserted else "categories_updated")

    def import_attributes_mapped(self, sid, code, af, removed):
        for raw, internal in af.items():
            if raw in removed:      # removal wins (pipeline step 1)
                continue
            sa_id, _ = self.sa(sid, raw)
            target = self.internal_attribute_id(internal)
            if target is None:
                self.unresolved["attributes"].setdefault(internal, []).append(f"{code}:{raw}")
            inserted = self.map_attribute(sa_id, target, True)
            self.bump("attributes_inserted" if inserted else "attributes_updated")

    def import_attributes_removed(self, sid, code, removed):
        for raw in removed:
            sa_id, _ = self.sa(sid, raw)
            inserted = self.map_attribute(sa_id, None, False)   # «Не імпортувати»
            self.bump("attributes_excluded_inserted" if inserted else "attributes_excluded_updated")

    def _holder_attr(self, sid, internal_name):
        return self.sa(sid, internal_name)[0]

    def import_values_mapped(self, sid, code, avm):
        for internal_attr, pairs in avm.items():
            holder = self._holder_attr(sid, internal_attr)
            parent = self.internal_attribute_id(internal_attr)
            if parent is None:
                self.unresolved["values"].setdefault(internal_attr, []).append(
                    f"{code}: внутрішній атрибут відсутній у каталозі")
            for raw_v, internal_v in pairs.items():
                sav_id, _ = self.sav(holder, raw_v)
                target = self.internal_value_id(parent, internal_v)
                inserted = self.map_value(sav_id, target, True)
                self.bump("values_inserted" if inserted else "values_updated")

    def import_values_removed(self, sid, code, avr):
        for internal_attr, raw_values in avr.items():
            holder = self._holder_attr(sid, internal_attr)
            for raw_v in raw_values:
                sav_id, _ = self.sav(holder, raw_v)
                inserted = self.map_value(sav_id, None, False)  # «Не імпортувати»
                self.bump("values_excluded_inserted" if inserted else "values_excluded_updated")


def main():
    ap = argparse.ArgumentParser(description="Import legacy mapping JSONs into the database.")
    ap.add_argument("--apply", action="store_true",
                    help="really write to the database (default: dry run, rollback)")
    ap.add_argument("--dsn", default=os.environ.get("DATABASE_DSN", DEFAULT_DSN))
    ap.add_argument("--mapping-dir", default=MAPPING_DIR)
    args = ap.parse_args()

    mdir = args.mapping_dir

    af = load_json(mdir, "attributes_final.json")
    ar = load_json(mdir, "attribute_remove.json")
    avm = load_json(mdir, "attribute_value_mapping_final.json")
    avr = load_json(mdir, "attribute_value_to_remove.json")
    cm = load_json(mdir, "category_mapping.json")

    conn = psycopg2.connect(args.dsn)
    imp = Importer(conn.cursor())

    for code in SYSTEM_SUPPLIERS:
        sid = imp.supplier_id(code)
        if sid is None:
            print(f"!! Постачальника «{code}» не знайдено в БД (migration 012) — пропуск")
            continue
        print(f"→ {code} (id={sid})")
        imp.import_categories(sid, code, cm)
        imp.import_attributes_mapped(sid, code, af, set(ar))
        imp.import_attributes_removed(sid, code, set(ar))
        imp.import_values_mapped(sid, code, avm)
        imp.import_values_removed(sid, code, avr)

    if args.apply:
        conn.commit()
        mode = "APPLIED"
    else:
        conn.rollback()
        mode = "DRY RUN (rolled back)"
    conn.close()

    print("\n===== SUMMARY =====")
    for k in sorted(imp.stats):
        print(f"{k}: {imp.stats[k]}")
    print("mode:", mode)

    unresolved_total = sum(len(v) for v in imp.unresolved.values())
    print(f"unresolved groups (targets missing in catalog): {unresolved_total}")
    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "import_report_unresolved.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "mode": mode,
            "stats": imp.stats,
            "unresolved_counts": {k: len(v) for k, v in imp.unresolved.items()},
            "unresolved": imp.unresolved,
        }, f, ensure_ascii=False, indent=2)
    print("unresolved report:", report_path)


if __name__ == "__main__":
    sys.exit(main())



