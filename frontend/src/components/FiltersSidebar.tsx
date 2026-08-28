'use client';

import { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { kopToUah, uahToKop } from '@/lib/catalogParams';

export type FilterValue = { value: string; count: number };

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
  basePath: string;
  params: Record<string, string>;
  filters: CategoryFilter[];
  categories?: CategoryNode[];
  activeCategorySlug?: string;
  categoryMode?: 'path' | 'param';
};

const VALUES_LIMIT = 8;

/* ---------- Reusable filter dropdown ---------- */

function FilterDropdown({
  label,
  selectionLabel,
  active,
  children,
}: {
  label: string;
  selectionLabel?: string | null;
  active?: boolean;
  children: React.ReactNode;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    const handle = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setIsOpen(false);
    };
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, [isOpen]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        className={
          'flex w-full items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm transition-colors ' +
          (active
            ? 'border-blue-400 bg-blue-50 text-blue-700'
            : 'border-gray-200 bg-white text-gray-700 hover:border-gray-300')
        }
      >
        <span className="truncate font-medium">
          {label}
          {selectionLabel && (
            <span className="ml-1.5 font-normal text-gray-500">: {selectionLabel}</span>
          )}
        </span>
        <svg
          className={'h-4 w-4 shrink-0 text-gray-400 transition-transform ' + (isOpen ? 'rotate-180' : '')}
          fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {isOpen && (
        <div className="absolute left-0 top-full z-40 mt-1 w-72 max-h-72 overflow-y-auto rounded-lg border border-gray-200 bg-white p-3 shadow-lg">
          {children}
        </div>
      )}
    </div>
  );
}

/* ---------- Chip (selected filter pill) ---------- */

function Chip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-md bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
      {label}
      <button onClick={onRemove} className="ml-0.5 inline-flex leading-none hover:text-blue-900">&times;</button>
    </span>
  );
}

/* ---------- Main sidebar ---------- */

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
  const [mobileOpen, setMobileOpen] = useState(false);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [priceFrom, setPriceFrom] = useState(() => kopToUah(num(params.price_min)));
  const [priceTo, setPriceTo] = useState(() => kopToUah(num(params.price_max)));

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
      navigate((sp) => sp.set('category', slug));
    } else {
      const sp = new URLSearchParams();
      if (params.q) sp.set('q', params.q);
      const qs = sp.toString();
      router.push("/catalog/" + encodeURIComponent(slug) + (qs ? '?' + qs : ''), { scroll: false });
    }
  };

  const clearCategory = () => {
    if (categoryMode === 'param') {
      navigate((sp) => sp.delete('category'));
    } else {
      router.push('/catalog', { scroll: false });
    }
  };

  const toggleExpanded = (attributeId: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(attributeId)) next.delete(attributeId);
      else next.add(attributeId);
      return next;
    });
  };

  const flattenCategories = (nodes: CategoryNode[]): CategoryNode[] => {
    const result: CategoryNode[] = [];
    const walk = (list: CategoryNode[]) => {
      for (const c of list) { result.push(c); if (c.children?.length) walk(c.children); }
    };
    walk(nodes);
    return result;
  };

  const flatCategories = categories ? flattenCategories(categories) : [];
  const activeCategoryName = activeCategorySlug
    ? flatCategories.find((c) => c.slug === activeCategorySlug)?.name ?? null
    : null;

  const priceActive = !!params.price_min || !!params.price_max;

  const body = (
    <div className="space-y-3">
      {/* Category — single-select dropdown */}
      {categories && categories.length > 0 && (
        <FilterDropdown label={t('category')} selectionLabel={activeCategoryName} active={!!activeCategorySlug}>
          <div className="space-y-1">
            <button
              onClick={clearCategory}
              className={
                'block w-full text-left rounded px-2 py-1.5 text-sm transition-colors ' +
                (!activeCategorySlug ? 'bg-blue-50 font-semibold text-blue-700' : 'text-gray-600 hover:bg-gray-50')
              }
            >
              {t('allCategories')}
            </button>
            <div className="max-h-60 overflow-y-auto border-t border-gray-100 pt-1">
              {categories.map((c) => (
                <CategoryOption key={c.id} node={c} activeSlug={activeCategorySlug} onSelect={selectCategory} level={0} />
              ))}
            </div>
          </div>
        </FilterDropdown>
      )}

      {/* Price — dropdown */}
      <FilterDropdown label={t('price')} active={priceActive}>
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <input type="text" inputMode="decimal" placeholder={t('from')}
              className="w-full rounded border border-gray-200 px-2 py-1.5 text-sm"
              value={priceFrom} onChange={(e) => setPriceFrom(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') applyPrice(); }} />
            <span className="text-gray-400">&ndash;</span>
            <input type="text" inputMode="decimal" placeholder={t('to')}
              className="w-full rounded border border-gray-200 px-2 py-1.5 text-sm"
              value={priceTo} onChange={(e) => setPriceTo(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') applyPrice(); }} />
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={applyPrice}
              className="flex-1 rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700">{t('apply')}</button>
            {priceActive && (
              <button type="button"
                onClick={() => { setPriceFrom(''); setPriceTo(''); navigate((sp) => { sp.delete('price_min'); sp.delete('price_max'); }); }}
                className="rounded border border-gray-200 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50">{t('reset')}</button>
            )}
          </div>
        </div>
      </FilterDropdown>

      {/* Attribute filters — multi-select dropdowns */}
      {filters.map((f) => {
        if (!f.values.length) return null;
        const selected = selectedFor(f.attribute_id);
        const showAll = expanded.has(f.attribute_id);
        const visible = showAll ? f.values : f.values.slice(0, VALUES_LIMIT);
        return (
          <FilterDropdown key={f.attribute_id} label={f.attribute_name}
            selectionLabel={selected.size > 0 ? "" + selected.size : null} active={selected.size > 0}>
            <div className="space-y-1">
              {visible.map((v) => (
                <label key={v.value} className="flex items-center gap-2 rounded px-1 py-1 text-sm cursor-pointer hover:bg-gray-50">
                  <input type="checkbox" className="rounded border-gray-300"
                    checked={selected.has(v.value)}
                    onChange={() => toggleValue(f.attribute_id, v.value)} />
                  <span className="min-w-0 flex-1 truncate">{v.value}</span>
                  <span className="text-xs text-gray-400">({v.count})</span>
                </label>
              ))}
              {f.values.length > VALUES_LIMIT && (
                <button type="button" onClick={() => toggleExpanded(f.attribute_id)}
                  className="w-full text-left text-xs text-blue-600 hover:underline pt-1">
                  {showAll ? t('showLess') : t('showMore', { count: f.values.length - VALUES_LIMIT })}
                </button>
              )}
            </div>
          </FilterDropdown>
        );
      })}

      {/* Selected filter summary + reset */}
      {(activeCategorySlug || priceActive || filters.some((f) => selectedFor(f.attribute_id).size > 0)) && (
        <div className="space-y-2 pt-1">
          <div className="flex flex-wrap gap-1.5">
            {activeCategorySlug && activeCategoryName && <Chip label={activeCategoryName} onRemove={clearCategory} />}
            {priceActive && (
              <Chip
                label={
                  'Ціна ' +
                  (params.price_min ? kopToUah(num(params.price_min)) + '₴' : '0₴') +
                  '–' +
                  (params.price_max ? kopToUah(num(params.price_max)) + '₴' : '∞')
                }
                onRemove={() => { setPriceFrom(''); setPriceTo(''); navigate((sp) => { sp.delete('price_min'); sp.delete('price_max'); }); }}
              />
            )}
            {filters.map((f) => {
              const sel = selectedFor(f.attribute_id);
              return [...sel].map((v) => (
                <Chip key={"" + f.attribute_id + '-' + v} label={v} onRemove={() => toggleValue(f.attribute_id, v)} />
              ));
            })}
          </div>
          <button onClick={resetFilters}
            className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm text-gray-600 hover:bg-gray-50">{t('reset')}</button>
        </div>
      )}
    </div>
  );

  return (
    <>
      {/* Mobile toggle */}
      <button
        onClick={() => setMobileOpen(true)}
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
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/40" onClick={() => setMobileOpen(false)} />
          <div className="absolute left-0 top-0 h-full w-[85%] max-w-xs overflow-y-auto bg-white p-4 shadow-xl">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold">{t('title')}</h3>
              <button onClick={() => setMobileOpen(false)} className="rounded-md bg-blue-600 px-3 py-1.5 text-sm text-white">
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

/* ---------- Recursive category option for single-select dropdown ---------- */

function CategoryOption({
  node,
  activeSlug,
  onSelect,
  level,
}: {
  node: CategoryNode;
  activeSlug?: string;
  onSelect: (slug: string) => void;
  level: number;
}) {
  const [subOpen, setSubOpen] = useState(false);
  const hasChildren = (node.children?.length ?? 0) > 0;

  return (
    <div>
      <div className="flex items-center gap-1">
        {hasChildren && (
          <button type="button" onClick={(e) => { e.stopPropagation(); setSubOpen((v) => !v); }}
            className="shrink-0 p-0.5 text-gray-400 hover:text-gray-600">
            <svg className={'h-3 w-3 transition-transform ' + (subOpen ? 'rotate-90' : '')}
              fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
          </button>
        )}
        {!hasChildren && <span className="w-4 shrink-0" />}
        <button onClick={() => onSelect(node.slug)}
          className={'block w-full text-left rounded px-2 py-1 text-sm transition-colors ' +
            (node.slug === activeSlug ? 'bg-blue-50 font-semibold text-blue-700' : 'text-gray-700 hover:bg-gray-50')}>
          {node.name}
        </button>
      </div>
      {subOpen && hasChildren && (
        <div className="ml-3 mt-0.5 space-y-0.5 border-l border-gray-100 pl-2">
          {(node.children ?? []).map((child) => (
            <CategoryOption key={child.id} node={child} activeSlug={activeSlug} onSelect={onSelect} level={level + 1} />
          ))}
        </div>
      )}
    </div>
  );
}
