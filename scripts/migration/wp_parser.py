#!/usr/bin/env python3
"""
WordPress SQL dump parser.
Parses the HestiaCP MariaDB dump into structured data.
"""
import json, os, sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from scripts.migration.sql_parser import extract_all_rows, split_row_values

DUMP_PATH = "/home/yuri/Desktop/my/temp/tempFiles/_wp_analysis/extracted/db_dump.sql"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__))


class WPParser:
    def __init__(self, dump_path=None):
        self.dump_path = dump_path or DUMP_PATH
        self.content = ""
        self.products = {}
        self.categories = {}
        self.attributes = {}
        self.attribute_terms = {}
        self.cat_relations = []
        self.attr_relations = []
    
    def load(self):
        if not os.path.exists(self.dump_path):
            print(f"ERROR: {self.dump_path} not found")
            return False
        size = os.path.getsize(self.dump_path) // 1024 // 1024
        print(f"Reading dump ({size} MB)...")
        with open(self.dump_path, "r", encoding="utf-8", errors="replace") as f:
            self.content = f.read()
        print(f"  Done ({len(self.content)} chars)")
        return True
def parse_products(self):
        print("Parsing products...")
        rows = extract_all_rows(self.content, "wp_posts")
        for row_text in rows:
            vals = split_row_values(row_text)
            if len(vals) >= 22 and vals[5] == "product":
                pid = vals[0]
                self.products[pid] = {
                    "id": pid,
                    "title": vals[8],
                    "slug": vals[14],
                    "status": vals[9],
                    "content": vals[11],
                    "excerpt": vals[12],
                    "meta": {},
                }
        
        meta_rows = extract_all_rows(self.content, "wp_postmeta")
        for row_text in meta_rows:
            vals = split_row_values(row_text)
            if len(vals) >= 4 and vals[1] in self.products:
                self.products[vals[1]]["meta"][vals[2]] = vals[3]
        
        print(f"  Found {len(self.products)} products")
        
        rel_rows = extract_all_rows(self.content, "wp_term_relationships")
        for row_text in rel_rows:
            vals = split_row_values(row_text)
            if len(vals) >= 2 and vals[0] in self.products:
                self.cat_relations.append((vals[0], vals[1]))
    
    def parse_attributes(self):
        print("Parsing attributes...")
        rows = extract_all_rows(self.content, "wp_woocommerce_attribute_taxonomies")
        for row_text in rows:
            vals = split_row_values(row_text)
            if len(vals) >= 4:
                self.attributes[vals[0]] = {"name": vals[1], "label": vals[2], "type": vals[3]}\n        print(f"  WooCommerce attrs: {len(selfattributes)}")
        
        tax_rows = extarct_all_rows(self.content, "wp_term_taxonomy")        
        term_rows = extarct_all_rows(self.content, "wp_terms")        
        term_map = {}        
        for row_text in term_rows:            
            vals = split_row_values(row_text)
            if len(vals) >= 3:
                term_map[vals[0]] = {"name": vals[1], "slug": vals[2]}
    
    def parse_categories(self):
        print("Parsing categories...")
        rows = extract_all_rows(self.content, "wp_term_taxonomy")
        cat_tax = {}
        for row_text in rows:
            vals = split_row_values(row_text)
            if len(vals) >= 5 and vals[2] == "product_cat":
                cat_tax[vals[1]] = {"parent": vals[4], "count": vals[5] if len(vals) > 5 else "0"}
        
        term_rows = extract_all_rows(self.content, "wp_terms")
        term_names = {}
        for row_text in term_rows:
            vals = split_row_values(row_text)
            if len(vals) >= 3:
                term_names[vals[0]] = {"name": vals[1], "slug": vals[2]}
        
        for tid, tax in cat_tax.items():
            name = term_names.get(tid, {})
            if name:
                self.categories[tid] = {
                    "id": int(tid),
                    "name": name["name"],
                    "slug": name["slug"],
                    "parent": int(tax["parent"]),
                    "count": int(tax["count"]),
                }
        print(f"  Found {len(self.categories)} categories")