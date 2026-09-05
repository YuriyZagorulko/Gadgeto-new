#!/usr/bin/env python3
"""Brand Backfill Script - optimized batch version."""

import sys
from pathlib import Path
from collections import defaultdict
import time

sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))

from app.imports.brand_resolver import (
    get_products_needing_brand_backfill,
    resolve_supplier_brand,
)
from app.core.db_connect import admin_cursor


def main():
    print("=" * 70)
    print("BRAND BACKFILL - EXECUTING (OPTIMIZED)")
    print("=" * 70)
    print()
    
    products = get_products_needing_brand_backfill(limit=100000)
    
    if not products:
        print("No products found.")
        return
    
    print(f"Products to process: {len(products)}\n")
    
    conn, cur = admin_cursor()
    try:
        updates = []
        stats = {
            'total': len(products),
            'resolved': 0,
            'not_found': 0,
            'by_supplier': defaultdict(lambda: {'total': 0, 'resolved': 0}),
            'brands_used': defaultdict(int),
            'no_brand_samples': [],
        }
        
        start_time = time.time()
        last_report = start_time
        
        for i, product in enumerate(products, 1):
            product_id = product['product_id']
            supplier_code = product['supplier_code']
            name = product['name']
            
            stats['by_supplier'][supplier_code]['total'] += 1
            
            resolved = resolve_supplier_brand(
                supplier_code=supplier_code,
                product_name=name,
            )
            
            if resolved:
                updates.append((resolved.id, product_id))
                stats['resolved'] += 1
                stats['by_supplier'][supplier_code]['resolved'] += 1
                stats['brands_used'][resolved.name] += 1
            else:
                stats['not_found'] += 1
                if len(stats['no_brand_samples']) < 15:
                    stats['no_brand_samples'].append(name[:60])
            
            # Batch commit every 500 records
            if len(updates) >= 500:
                cur.executemany(
                    "UPDATE products SET brand_id = %s, updated_at = NOW() WHERE id = %s",
                    updates
                )
                conn.commit()
                updates = []
                
                now = time.time()
                if now - last_report >= 5:
                    elapsed = now - start_time
                    rate = i / elapsed
                    print(f"  [{i}/{len(products)}] {rate:.0f}/sec...")
                    last_report = now
        
        # Final batch
        if updates:
            cur.executemany(
                "UPDATE products SET brand_id = %s, updated_at = NOW() WHERE id = %s",
                updates
            )
            conn.commit()
        
        elapsed = time.time() - start_time
        
        print("\n" + "=" * 70)
        print("FINAL RESULTS")
        print("=" * 70)
        print(f"Total products:     {stats['total']}")
        print(f"Brand resolved:     {stats['resolved']} ({stats['resolved']/stats['total']*100:.1f}%)")
        print(f"Cannot resolve:     {stats['not_found']} ({stats['not_found']/stats['total']*100:.1f}%)")
        print(f"Time elapsed:      {elapsed:.1f}s")
        
        print("\nBY SUPPLIER")
        print("-" * 70)
        for sup, s in sorted(stats['by_supplier'].items()):
            pct = s['resolved'] / s['total'] * 100 if s['total'] else 0
            print(f"  {sup:12} {s['resolved']:6}/{s['total']:6} ({pct:5.1f}%)")
        
        print("\nTOP BRANDS RECOVERED")
        print("-" * 70)
        for brand, count in sorted(stats['brands_used'].items(), key=lambda x: -x[1])[:30]:
            print(f"  {brand:20} {count:6}")
        
        if stats['no_brand_samples']:
            print("\nPRODUCTS WITHOUT DETECTABLE BRAND (sample)")
            print("-" * 70)
            for name in stats['no_brand_samples']:
                print(f"  {name}")
        
        print("\n" + "=" * 70)
        print("BACKFILL COMPLETE")
        print("=" * 70)
        
    finally:
        conn.close()


if __name__ == '__main__':
    main()
