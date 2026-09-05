#!/usr/bin/env python3
"""Brand Backfill Script - recovers brand_id for products."""

import argparse
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))

from app.imports.brand_resolver import (
    get_products_needing_brand_backfill,
    backfill_brand_for_product,
    resolve_supplier_brand,
)


def run_dry_run(limit: int = None, supplier: str = None):
    """Preview changes without making them."""
    print("=" * 70)
    print("BRAND BACKFILL - DRY RUN")
    print("=" * 70)
    print()

    products = get_products_needing_brand_backfill(limit=limit or 10000)
    if supplier:
        products = [p for p in products if p['supplier_code'] == supplier]

    if not products:
        print("No products found needing brand backfill.")
        return

    print(f"Products to process: {len(products)}\n")

    stats = {
        'total': len(products), 'resolved': 0, 'not_found': 0,
        'by_supplier': defaultdict(lambda: {'total': 0, 'resolved': 0}),
        'brands_to_add': defaultdict(int),
        'no_brand_patterns': [],
    }

    for product in products:
        supplier_code = product['supplier_code']
        stats['by_supplier'][supplier_code]['total'] += 1

        resolved = resolve_supplier_brand(
            supplier_code=supplier_code,
            product_name=product['name'],
        )

        if resolved:
            stats['resolved'] += 1
            stats['by_supplier'][supplier_code]['resolved'] += 1
            stats['brands_to_add'][resolved.name] += 1
        else:
            stats['not_found'] += 1
            if len(stats['no_brand_patterns']) < 10:
                stats['no_brand_patterns'].append(product['name'][:60])

    print("RESULTS SUMMARY")
    print("-" * 70)
    print(f"Total products:   {stats['total']}")
    print(f"Can resolve:      {stats['resolved']} ({stats['resolved']/stats['total']*100:.1f}%)")
    print(f"Cannot resolve:   {stats['not_found']}\n")

    print("BY SUPPLIER")
    print("-" * 70)
    for sup, s in sorted(stats['by_supplier'].items()):
        pct = s['resolved'] / s['total'] * 100 if s['total'] else 0
        print(f"  {sup:12} {s['resolved']:6}/{s['total']:6} ({pct:5.1f}%)")

    print("\nTOP BRANDS TO ADD")
    print("-" * 70)
    for brand, count in sorted(stats['brands_to_add'].items(), key=lambda x: -x[1])[:15]:
        print(f"  {brand:20} {count:6}")

    print("\nPRODUCTS WITHOUT DETECTABLE BRAND (sample)")
    print("-" * 70)
    for name in stats['no_brand_patterns']:
        print(f"  {name}")

    print("\n" + "=" * 70)
    print("This was a DRY RUN. No changes were made.")
    print("=" * 70)


def run_execute(limit: int = None, supplier: str = None, batch_size: int = 100):
    """Execute the backfill changes."""
    print("=" * 70)
    print("BRAND BACKFILL - EXECUTING")
    print("=" * 70)
    print()

    products = get_products_needing_brand_backfill(limit=limit or 100000)
    if supplier:
        products = [p for p in products if p['supplier_code'] == supplier]

    if not products:
        print("No products found.")
        return

    print(f"Products to process: {len(products)}\n")

    stats = {
        'total': len(products), 'resolved': 0, 'not_found': 0,
        'by_supplier': defaultdict(lambda: {'total': 0, 'resolved': 0}),
    }

    for i, product in enumerate(products, 1):
        supplier_code = product['supplier_code']
        stats['by_supplier'][supplier_code]['total'] += 1

        result = backfill_brand_for_product(product['product_id'], dry_run=False)
        if result['status'] == 'resolved':
            stats['resolved'] += 1
            stats['by_supplier'][supplier_code]['resolved'] += 1
        else:
            stats['not_found'] += 1

        if i % batch_size == 0:
            print(f"Processed {i}/{len(products)}...")

    print("\nFINAL RESULTS")
    print("-" * 70)
    print(f"Total products:     {stats['total']}")
    print(f"Brand resolved:     {stats['resolved']}")
    print(f"Cannot resolve:     {stats['not_found']}")

    print("\nBY SUPPLIER")
    print("-" * 70)
    for sup, s in sorted(stats['by_supplier'].items()):
        print(f"  {sup:12} {s['resolved']:6} resolved, {s['total'] - s['resolved']:6} not found")

    print("\n" + "=" * 70)
    print("BACKFILL COMPLETE")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description='Backfill brand_id for products')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes')
    parser.add_argument('--execute', action='store_true', help='Apply changes')
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--supplier', type=str, default=None)

    args = parser.parse_args()

    if args.dry_run:
        run_dry_run(limit=args.limit, supplier=args.supplier)
    elif args.execute:
        run_execute(limit=args.limit, supplier=args.supplier)
    else:
        parser.print_help()
        print("\nPlease specify --dry-run or --execute")


if __name__ == '__main__':
    main()
