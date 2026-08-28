
'use client';

import { useEffect, useState } from 'react';
import { useTranslations } from 'next-intl';
import ProductCard from '@/components/ProductCard';

const STORAGE_KEY = 'gadgeto_viewed_products';
const MAX_IDS = 12;
const MIN_SHOW = 6;

/**
 * Reads viewed product IDs from localStorage, fetches their details, and
 * renders the section if at least MIN_SHOW distinct products were viewed.
 *
 * The product list is populated by a separate useEffect in the product detail
 * page (not shown here) that pushes the current product ID into localStorage.
 */
export default function HomepageViewedProducts() {
  const t = useTranslations('home');
  const [products, setProducts] = useState<any[] | null>(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) { setProducts([]); return; }
      const ids: number[] = JSON.parse(raw);
      if (!Array.isArray(ids) || ids.length < MIN_SHOW) { setProducts([]); return; }
      const unique = [...new Set(ids)].slice(0, MAX_IDS);
      if (unique.length < MIN_SHOW) { setProducts([]); return; }

      const apiBase = (window as any).NEXT_PUBLIC_API_URL || 'http://backend:8000';
      const url = new URL('/api/v1/home', apiBase.replace(/\/+$/, ''));
      fetch(url.toString())
        .then((r) => r.json())
        .then((d) => {
          const all = [...(d.recommended || []), ...(d.new_arrivals || [])];
          const map = new Map(all.map((p: any) => [p.id, p]));
          const found = unique.map((id) => map.get(id)).filter(Boolean);
          setProducts(found.length >= MIN_SHOW ? found.slice(0, MAX_IDS) : []);
        })
        .catch(() => setProducts([]));
    } catch { setProducts([]); }
  }, []);

  if (products === null) return null;
  if (products.length < MIN_SHOW) return null;

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">{t('viewedTitle')}</h2>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-4">
        {products.map((p: any) => <ProductCard key={p.id} product={p} />)}
      </div>
    </div>
  );
}
