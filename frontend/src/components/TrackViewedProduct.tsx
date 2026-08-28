'use client';

import { useEffect } from 'react';

/**
 * Tracks the current product ID in localStorage for the "Viewed products"
 * section on the homepage. Must be a separate client component because the
 * product detail page is a Server Component.
 */
export default function TrackViewedProduct({ productId }: { productId: number }) {
  useEffect(() => {
    try {
      const key = 'gadgeto_viewed_products';
      const raw = localStorage.getItem(key);
      const ids: number[] = raw ? JSON.parse(raw) : [];
      const filtered = ids.filter((id) => id !== productId);
      filtered.unshift(productId);
      localStorage.setItem(key, JSON.stringify(filtered.slice(0, 12)));
    } catch { /* ignore */ }
  }, [productId]);

  return null;
}