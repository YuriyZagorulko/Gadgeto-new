'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { kopToUah, uahToKop } from '@/lib/catalogParams';

export type FilterValue = { value: string; count: number };

/** One configured attribute filter (from Admin → Фільтри категорій). */
export type CategoryFilter = {
  attribute_id: number;
  attribute_name: string;
  attribute_slug: string;
  filter_type: string;
  position: number;
  values: FilterValue[];
};

export type CategoryNode = {
  id: number;
  name: string;
  slug: string;
  parent_id: number | null;
  product_count?: number;
  children?: CategoryNode[];
};

type Props = {
  /** Path prefix for navigation, e.g. `/search` or `/catalog/монітори`. */
  basePath: string;
  /** Current single-value query params (from the page URL). */
  params: Record<string, string>;
  /** Admin-configured filters for the active category (may be empty). */
  filters: CategoryFilter[];
  /** Full category tree (optional; enables the Категорія block). */
  categories?: CategoryNode[];
  activeCategorySlug?: string;
  /** How category selection navigates: `path` = catalog pages (/catalog/<slug>),
   *  `param` = search page (?category=<slug> keeps other filters). */
  categoryMode?: 'path' | 'param';
};

const VALUES_LIMIT = 8;

/**
 * Marketplace-style filter sidebar.
 * The URL is the source of truth: every interaction rewrites the query part
 * of the URL (page reset to 1) and the server page refetches. Attribute
 * filters are sent as `f<attribute_id>=v1,v2` matching GET /api/v1/products.
 */
export default function FiltersSidebar({
  basePath,
  params,
  filters,
  categories,
  activeCategorySlug,
  categoryMode = 'path',
}: Props) {
  const t = useTranslations('filters');
  const router = useRouter();
  const [open, setOpen] = useState(false); // mobile drawer
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [priceFrom, setPriceFrom] = useState(() => kopToUah(num(params.price_min)));
  const [priceTo, setPriceTo] = useState(() => kopToUah(num(params.price_max)));

  const hasActive = Object.keys(params).some(
    (k) => /^f\d+$/.test(k) || k === 'price_min' || k === 'price_max'
  );

  /** Clones current params, applies mutations, resets page, navigates. */
  const navigate = (mutate: (sp: URLSearchParams) => void) => {
    const sp = new URLSearchParams(params);
    mutate(sp);
    sp.delete('page');
    const qs = sp.toString();
    router.push(qs ? `${basePath}?${qs}` : basePath, { scroll: false });
  };

  const selectedFor = (attributeId: number): Set<string> => {
    const raw = params[`f${attributeId}`] || '';
    return new Set(raw.split(',').map((v) => v.trim()).filter(Boolean));
  };

  const toggleValue = (attributeId: number, value: string) => {
    const key = `f${attributeId}`;
    const selected = selectedFor(attributeId);
    if (selected.has(value)) selected.delete(value);
    else selected.add(value);
    navigate((sp) => {
      if (selected.size) sp.set(key, [...selected].join(','));
      else sp.delete(key);
    });
  };

  const applyPrice = () => {
    navigate((sp) => {
      const min = uahToKop(priceFrom);
      const max = uahToKop(priceTo);
      if (min !== null) sp.set('price_min', String(min));
      else sp.delete('price_min');
      if (max !== null) sp.set('price_max', String(max));
      else sp.delete('price_max');
    });
  };

  const resetFilters = () => {
    navigate((sp) => {
      for (const key of [...sp.keys()]) {
        if (/^f\d+$/.test(key) || key === 'price_min' || key === 'price_max') sp.delete(key);
      }
    });
    setPriceFrom('');
    setPriceTo('');
  };

  const selectCategory = (slug: string) => {
    if (categoryMode === 'param') {
      // Search page: category is a URL param; keep q/price/attribute filters.
      navigate((sp) => sp.set('category', slug));
    } else {
      // Catalog page: navigate to the new category; attribute/price filters
      // are category-scoped, so drop them; keep the keyword search.
      const sp = new URLSearchParams();
      if (params.q) sp.set('q', params.q);
      const qs = sp.toString();
      router.push(`/catalog/${encodeURIComponent(slug)}${qs ? '?' + qs : ''}`, { scroll: false });
    }
    setOpen(false);
  };

  const toggleExpanded = (attributeId: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(attributeId)) next.delete(attributeId);
      else next.add(attributeId);
      return next;
    });
  };

  const priceInvalid =
    (priceFrom.trim() !== '' && uahToKop(priceFrom) === null) ||
    (priceTo.trim() !== '' && uahToKop(priceTo) === null);

  const body = (
    <div className="space-y-4">
      {categories && categories.length > 0 && (
        <section>
          <h4 className="text-sm font-semibold uppercase tracking-wide text-gray-500 mb-2">
            {t('category')}
          </h4>
          <CategoryTree nodes={categories} activeSlug={activeCategorySlug} onSelect={selectCategory} level={0} />
        </section>
      )}

      <section>
        <h4 className="text-sm font-semibold uppercase tracking-wide text-gray-500 mb-2">{t('price')}</h4>
        <div className="flex items-center gap-2">
          <input
            type="text"
            inputMode="decimal"
            placeholder={t('from')}
            value={priceFrom}
            onChange={(e) => setPriceFrom(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !priceInvalid && applyPrice()}
            className="input-field w-full min-w-0"
          />
          <span className="text-gray-400">—</span>
          <input
            type="text"
            inputMode="decimal"
            placeholder={t('to')}
            value={priceTo}
            onChange={(e) => setPriceTo(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !priceInvalid && applyPrice()}
            className="input-field w-full min-w-0"
          />
        </div>
        {priceInvalid && <p className="mt-1 text-xs text-red-500">{t('priceInvalid')}</p>}
        <button
          onClick={applyPrice}
          disabled={priceInvalid}
          className="mt-2 w-full rounded-md border border-blue-200 bg-blue-50 px-3 py-1.5 text-sm text-blue-700 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {t('apply')}
        </button>
      </section>

      {filters.map((f) => {
        if (!f.values.length) return null; // no usable values → no section
        const selected = selectedFor(f.attribute_id);
        const showAll = expanded.has(f.attribute_id);
        const visible = showAll ? f.values : f.values.slice(0, VALUES_LIMIT);
        return (
          <section key={f.attribute_id}>
            <h4 className="text-sm font-semibold uppercase tracking-wide text-gray-500 mb-2">
              {f.attribute_name}
            </h4>
            {visible.map((v) => (
              <label key={v.value} className="flex items-center gap-2 text-sm mb-1.5 cursor-pointer hover:text-blue-700">
                <input
                  type="checkbox"
                  className="rounded border-gray-300"
                  checked={selected.has(v.value)}
                  onChange={() => toggleValue(f.attribute_id, v.value)}
                />
                <span className="min-w-0 truncate">
                  {v.value} <span className="text-gray-400">({v.count})</span>
                </span>
              </label>
            ))}
            {f.values.length > VALUES_LIMIT && (
              <button onClick={() => toggleExpanded(f.attribute_id)} className="text-xs text-blue-600 hover:underline">
                {showAll ? t('showLess') : t('showMore', { count: f.values.length - VALUES_LIMIT })}
              </button>
            )}
          </section>
        );
      })}

      {hasActive && (
        <button
          onClick={resetFilters}
          className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm text-gray-600 hover:bg-gray-50"
        >
          {t('reset')}
        </button>
      )}
    </div>
  );

  return (
    <>
      {/* Mobile toggle */}
      <button
        onClick={() => setOpen(true)}
        className="md:hidden mb-3 flex w-full items-center justify-center gap-2 rounded-md border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm"
      >
        <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <path strokeLinecap="round" d="M3 6h18M6 12h12M10 18h4" />
        </svg>
        {t('openMobile')}
      </button>

      {/* Desktop sidebar */}
      <aside className="hidden md:block bg-white rounded-lg p-4 shadow-sm">
        <h3 className="font-semibold mb-3">{t('title')}</h3>
        {body}
      </aside>

      {/* Mobile drawer */}
      {open && (
        <div className="md:hidden fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <div className="absolute left-0 top-0 h-full w-[85%] max-w-xs overflow-y-auto bg-white p-4 shadow-xl">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold">{t('title')}</h3>
              <button onClick={() => setOpen(false)} className="rounded-md bg-blue-600 px-3 py-1.5 text-sm text-white">
                {t('close')}
              </button>
            </div>
            {body}
          </div>
        </div>
      )}
    </>
  );
}

function num(v: string | undefined): number | null {
  if (!v || !/^\d{1,9}$/.test(v)) return null;
  return parseInt(v, 10);
}

function CategoryTree({
  nodes,
  activeSlug,
  onSelect,
  level,
}: {
  nodes: CategoryNode[];
  activeSlug?: string;
  onSelect: (slug: string) => void;
  level: number;
}) {
  return (
    <ul className={level === 0 ? 'space-y-1' : 'mt-1 space-y-1 border-l border-gray-100 pl-3'}>
      {nodes.map((c) => (
        <li key={c.id}>
          <button
            onClick={() => onSelect(c.slug)}
            className={
              'block w-full text-left text-sm py-0.5 hover:text-blue-700 ' +
              (c.slug === activeSlug ? 'font-semibold text-blue-700' : 'text-gray-700')
            }
          >
            {c.name}
          </button>
          {(c.children?.length ?? 0) > 0 && (
            <CategoryTree nodes={c.children ?? []} activeSlug={activeSlug} onSelect={onSelect} level={level + 1} />
          )}
        </li>
      ))}
    </ul>
  );
}
