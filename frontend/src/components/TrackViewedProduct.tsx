'use client';

import { useEffect } from 'react';
import { trackViewItem } from '@/lib/analytics';

/**
 * Tracks the current product ID in localStorage for the "Viewed products"
 * section on the homepage + pushes GA4 `view_item`. Separate client
 * component because the product detail page is a Server Component.
 */
export default function TrackViewedProduct({ productId, product }: { productId: number; product?: { id: number; name: string; price: number; sku?: string | null } }) {
  useEffect(() => {
    try {
      const key = 'gadgeto_viewed_products';
      const raw = localStorage.getItem(key);
      const ids: number[] = raw ? JSON.parse(raw) : [];
      const filtered = ids.filter((id) => id !== productId);
      filtered.unshift(productId);
      localStorage.setItem(key, JSON.stringify(filtered.slice(0, 12)));
    } catch { /* ignore */ }
    if (product) {
      trackViewItem({
        id: product.id, name: product.name, price: product.price,
        quantity: 1, sku: product.sku ?? null,
      });
    }
  }, [productId]);

  return null;
}