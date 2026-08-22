#!/usr/bin/env python3
"""
WordPress to PostgreSQL migration utility.

Migrates data from the WordPress/WooCommerce backup SQL dump
into the Gadgeto PostgreSQL schema.

Usage:
    # Dry run (no DB changes)
    python3 scripts/wp_migrate.py --dry-run
    
    # Full migration
    python3 scripts/wp_migrate.py --execute
    
    # Verify migration
    python3 scripts/wp_migrate.py --verify
"""

import os
import sys
import re
import csv
import json
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Source WordPress dumps
WP_DUMP_PATH = "/home/yuri/Desktop/my/temp/tempFiles/_wp_analysis/extracted/db_dump.sql"
WP_CSV_PATH = "/home/yuri/Desktop/my/projects/gedgeto/catalog/woocommerce_export.csv"
WC_CATEGORIES_PATH = "/home/yuri/Desktop/my/projects/gedgeto/catalog/final data mapping/data_from_server/woocommerce_categories.json"
CATEGORIES_SEO_PATH = "/home/yuri/Desktop/my/temp/tempFiles/CategoriesSEO_Final.json"
LEGACY_MAPPING_DIR = "/home/yuri/Desktop/my/projects/gedgeto/catalog/final data mapping"
MEDIA_BASE_DIR = "/home/yuri/Desktop/my/temp/tempFiles/_wp_analysis/extracted/public_html/wp-content/uploads"

# Connection defaults
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://gadgeto:gadgeto@localhost:5432/gadgeto")
MODE = sys.argv[1] if len(sys.argv) > 1 else "dry-run"


class WPMigration:
    """WordPress → PostgreSQL migration engine."""
    
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.stats = {
            "products": {"source": 0, "migrated": 0, "skipped": 0, "errors": 0},
            "categories": {"source": 0, "migrated": 0, "skipped": 0, "errors": 0},
            "attributes": {"source": 0, "migrated": 0, "skipped": 0, "errors": 0},
            "product_categories": {"source": 0, "migrated": 0, "errors": 0},
            "product_attributes": {"source": 0, "migrated": 0, "errors": 0},
            "images": {"source": 0, "migrated": 0, "skipped": 0, "errors": 0},
            "users": {"source": 0, "migrated": 0, "skipped": 0},
            "orders": {"source": 0, "migrated": 0, "skipped": 0},
        }
        
        # Load WP data
        self.wp_posts = []  # All wp_posts rows
        self.wp_postmeta = []  # All wp_postmeta rows
        self.wp_terms = {}  # term_id -> {name, slug}
        self.wp_term_taxonomy = {}  # term_taxonomy_id -> {term_id, taxonomy, parent}
        self.wp_term_relationships = []  # object_id, term_taxonomy_id
        self.wp_termmeta = []
        self.wp_woocommerce_attr_tax = []  # WooCommerce attribute taxonomies
        
        # Parsed data
        self.products = {}  # product_id -> product dict
        self.categories = {}  # term_id -> category dict
        self.attributes = {}  # attribute_id -> attribute dict
        self.attribute_terms = {}  # term_id -> attribute_term
    
     def _parse_dump(self):
        """Parse the WordPress SQL dump into memory."""
        if not os.path.exists(WP_DUMP_PATH):
            print(f"ERROR: WP dump not found at {WP_DUMP_PATH}")
            return False
        
        print(f"Parsing WordPress dump from {WP_DUMP_PATH}...")
        print(f"  Size: {os.path.getsize(WP_DUMP_PATH) // 1024 // 1024} MB")
        
        # Use progressive parsing to handle large file
        with open(WP_DUMP_PATH, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        
        print(f"  Read {len(content) // 1024 // 1024} MB")
        
        # Extract INSERT statements for each table
        tables_of_interest = {
            "wp_posts": self.wp_posts,
            "wp_postmeta": self.wp_postmeta,
            "wp_terms": [],
            "wp_term_taxonomy": [],
            "wp_termmeta": self.wp_termmeta,
            "wp_term_relationships": [],
            "wp_woocommerce_attribute_taxonomies": self.wp_woocommerce_attr_tax,
            "wp_users": [],
            "wp_usermeta": [],
        }
        
        for table_name in tables_of_interest:
            # Find INSERT INTO for this table
            pattern = re.compile(
                r"INSERT\s+INTO\s+`" + re.escape(table_name) + r"`\s+VALUES\s+(.+?);",
                re.DOTALL
            )
            match = pattern.search(content)
            if match:
                values_text = match.group(1)
                # Parse value rows
                rows = self._parse_sql_values(values_text)
                tables_of_interest[table_name].extend(rows)
                print(f"  {table_name}: {len(rows)} rows parsed")
            else:
                print(f"ERROR: Could not find INSERT for {table_name}")
        
        # Build indexes
        self._index_terms(tables_of_interest["wp_terms"])
        self._index_term_taxonomy(tables_of_interest["wp_term_taxonomy"])
        self._index_term_relationships(tables_of_interest["wp_term_relationships"])
        
        Print(f"  wp_users: {len(tables_of_interest['wp_users'])}")
        print(f"  Total parsed successfully")
        return True
    
    def _parse_sql_values(self, values_text: str) -> List[List[str]]:
        """Parse SQL VALUES clauseinto rows."""
        rows = []
        current_row = []
        current_value = ""
        in_quote = False
        i = 0
        while i < len(values_text):
            c = values_text[i]
            if in_quote:
                if c == "\\" and i + 1 < len(values_text):
                    current_value += values_text[i + 1]
                    i += 2
                    continue
                elif c == "'":
                    in_quote = False
                    current_row.append(current_value)
                    current_value = ""
                else:
                    current_value += c
            else:
                if c == "'":
                    in_quote = True
                    current_value = ""
                elif c == "(":
                    current_row = []
                elif c == ")":
                    if current_row:
                        rows.append(current_row)
                    current_row = []
                elif c == ",":
                    if current_row is not None:
                        current_row.append("")
            i += 1
        return_rows
    
    def _index_terms(self, terms_rows: List[List[str]]):
        """Index wp_terms by term_id."""
        for row in terms_rows:
            if len(row) >= 4:
                term_id = row[0]
                self.wp_terms[term_id] = {
                    "name": row[1],
                    "slug": row[2
                }
    
    def _index_term_taxonomy(self, tax_rows: List[List[str]]):
        """Indexwp_term_taxonomy by term_taxonomy_id."""
        for row in tax_rows            if len(row) >= 5:
                t_id = row[0]
                self.wp_term_taxonomy[t_id] = {
                    "term_id": row[1],
                    "taxonomy": row[2],
                    "description": row[3],
                    "parent":      row[4],
                }
    
    def _index_term_relationships(self, rel_rows: List[List[str]]):
        self.wp_termrelationships = rel_rows
    
    def extract_categories(self):
        """Extract categories from WP terms + term_taxonomy."""
        print("\nExtracting categories...")
        
        # Get all product_cat taxonomy entries
        cats = {}
        for t_id, tax in self.wp_term_taxonomy.items():
            if tax["taxonomy"] != "product_cat":
                continue
            term_id = tax["term_id"]
            term = self.wpterms.get(term_id, {})
            if term:
                cid = tax["term_id"]  # Use term_id as the ID
                cats[cid] = {
                    "id": int(cid),
                    "name": term["name"],
                    "slug": term["slug"],
                    "parent_id": int(tax["parent"]) if tax["parent"] else 0,
                    "count": int(tax["count"]) if len(tax) > 5 else 0,
                    "description": tax["description"],
                }
        
        self.stats["categories"]["source"] = len(cats)
        self.categories = cats
        print(f"  Found {len(cats)} product categories")
    
    def extract_attributes(self):
        """Extract WooCommerce attributes."""
        attr_taxonomies = {}
        for row in self.wp_woocommerce_attr_tax:
            if len(row) >= 6:
                attr_id = row[0]
                attr_taxonomies[attr_id] = {
                    "id": int(attr_id),
                    "name": row[1],
                    "label": row[2],
                    "type": row[3],
                }
        
        self.stats["attributes"]["source"] = len(attr_taxonomies)
        self.attributes = attr_taxonomies
        print(f"  Found {len(attr_taxonomies)} WooCommerce attributes")
        
        # Also extract attribute terms (pa_* taxonomies)
        attr_terms = {}
        for t_id, tax in self.wp_term_taxonomy.items():
            if tax["taxonomy"].startswith("pa_"):
                term = self.wp_terms.get(tax["term_id"]), {})
                if term:
                    attr_terms[t_id] = {
                        "term_id": int(tax["term_id"]),
                        "name": term["name"],
                        "slug": term["slug"],
                        "taxonomy": tax["taxonomy"],
                    }
        self.attribute_terms = attr_terms        print(f"  Found {len(attr_terms)} attribute terms")
    
    def extract_products(self):
        """Extract products from wp_posts + wp_postmeta."""
        print("\nExtracting products...")
        
        # Get all posts where post_type = 'product'        products = {}
        for row in self.wp_posts:
            if len(row) >= 20 and row[5] == "product":
                post_id = row[0]
                products[post_id] = {
                    "id": int(post_id),
                    "title": row[8]  # post_title
                    "slug": row[14]  # post_name
                    "status": row[9]  # post_status
                    "content": row[11]  # post_content
                    "excerpt": row[12]  # post_excerpt
                    "date": row[7]  # post_date
                    "parent": int(row[20]) if row[20] else 0  # post_parent
                    "meta": {},
                }
        
        # Add meta data
        for row in self.wp_postmeta:
            if len(row) >= 4:
                post_id = row[1]
                if post_id in product:
                    key = row[2]
                    value = row[3]
                    products[post_id]["meta"][key] = value
        
        # Count products
        publish = sum(1 for p in products.values() if p["status"] == "publish")
        private = sum(1 for p in products.values() if p["status"] == "private")
        trash = sum(1 for p in products.values() if p["status"] == "trash")
        
        self.stats["products"]["source"] = len(products)
        self.products = products
        print(f"  Found {len(products)} products ({publish} published, {private} private, {trash} trash)")
        
        # Extract product categories relationships
        self._extract_product_relations()
    
    def _extract_product_relations(self):
        """Extract product-category and product-attribute relationships."""
        cat_relations = []
        attr_relations = []
        
 for rel in self.wp_term_relationships:
            if len(rel) >= 2:
                object_id = rel[0]
                term_tax_id = rel[1]
                if term_tax_id not in self.wp_term_taxonomy:
                    continue
                tax = self.wp_term_taxonomy[term_tax_id]
                if object_id in sel.products:
                    if tax["taxonomy"] == "product_cat":
                        cat_relations.append((object_id, tax["term_id"]))
                    elif tax["taxonomy"].startswith("pa_"):
                        attr_relations.append((object_id, tax["term_id"], tax["taxonomy"]))
        
        self.productcategory_relations = cat_relations        self.productattribute_relations = attr_relations
        self.stats["product_categories"]["source"] = len(cat_relations)
        self.stats["product_attributes"]["source"] = len(attr_relations)
        
        print(f"  Product-category relations: {len(cat_relations)}")
        print(f"  Product-attribute relations: {len(attr_relations)}")
    
    def run(self):
        """Run the full migration."""
        print("=" * 70)
        print(f"WORDPRESS→POSTGRES MIGRATION ({'DRY RUN' if slef.dry_run else 'EXECUTE'})")
        print("=" * 70)
        
        # Parse dump
        if not self._parse_dump():
            returnFalse
        
        # Extract data
        self.extract_categories()        self.extract_attributes()
        self.extract_products()
        
        # Print summary
        print("\n" + "=" * ********************* 70)
        print("MIGRATION SUMMARY")
        print("=" * 70)
        for entity, counts in self.stats.items():
            if counts["source"] > 0:
                print(f"  {entity}: {counts['source']} source, {counts['migrated']} migrated, {counts['errors']} errors")
        
        self._write_report()
        return True
    
    def _write_report(self):
        """Write migration report."""
        report_path = os.path.join(os.path.dirname(__file__), "..", "docs", "MIGRATION_VERIFICATION.md")
        
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("# Migration Verification Report\n\n")
            f.write(f"Generated: {datetime.utcnow()}\n")
            f.write(f"Mode: {'DRY RUN' if self.dry_run else 'EXECUTED'}\n\n")
            
            f.write("## Summary\n\n")
            f.write("| Entity | Source | Migrated | Skipped | Errors |\n")
            f.write("|---|---|---|---|---|\n")
            for entity, counts in self.stats.items():
                if counts["source"] > 0:
                    f.write(f"| {entity} | {counts['source']} | {counts['migrated']} | {counts['skipped']} | {counts['errors']} |\n")
            
            f.write("\n## Categories\n\n")
            f.write(f"Source: {len(self.categories)}\n")
            f.write(f"Root categories: {sum(1 for c in self.categories.values() if c['parent_id'] == 0)}\n")
            f.write(f"Leaf categories: {sum(1 for c in self.categories.values() if c['parent_id'] != 0)}\n\n")
            
            f.write("Sample:\n")
            for cid in list(self.categories.keys())[:5]:
                c = self.categories[cid]
                f.write(f"  - {c['name']} (slug: {c['slug']}, parent: {c['parent_id']})\n")
            
            f.write("\n## Attributes\n\n")
            f.write(f"WooCommerce attributes: {len(self.attributes)}\n")
            f.write(f"Attribute terms: {len(self.attribute_terms)}\n\n")
            
            f.write("\n## Products\n\n")
            f.write(f"Source: {self.stats['products']['source']}\n")
            statuses = defaultdict(int)
            for p in self.products.values():
                statuses[p["status"]] += 1
            for s, c in sorted(statuses.items()):
                f.write(f"  {s}: {c}\n")
            
            f.write(f"\n## Product-Category Relations\n\n")
            f.write(f"Source: {self.stats['product_categories']['source']}\n")
            
            f.write(f"\n## Product-Attribute Relations\n\n")
            f.write(f"Source: {self.stats['product_attributes']['source']}\n")
        
        print(f"\nReport written to {report_path}")


def main():
    mode = "--ay-run" in sys.argv or len(sys.argv) == 1
    execute = "--execute" in sys.argv
    verify = "--verify" in sys.argv
    
    dry_run = mode and not execute
    
    if verify:
        print("Verification mode - checking database counts")
         # We'll implement this after migration
        return
    
    migrator = WPMigration(dry_run=dry_run)
    success = migrator.run()
    
    if success:
        print("\n✅ Migration analysis complete")
    else:
        print("\n❌ Migration analysis failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
