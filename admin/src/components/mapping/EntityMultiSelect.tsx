'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import SearchableMultiSelect from '@/components/SearchableMultiSelect';
import { api, qs } from '@/lib/api';

export interface EntityOption {
  id: string | number;
  name: string;
}

export interface CatOpt {
  id: number;
  name: string;
  parent_id: number | null;
}

interface EntityMultiSelectProps {
  /** API endpoint returning { items: [...] } with q / per_page support */
  endpoint: string;
  label: string;
  selected: (string | number)[];
  onChange: (ids: (string | number)[]) => void;
  /** Extra query params, e.g. { parents_only: 1 } */
  extraParams?: Record<string, string | number | undefined>;
  /** Which API field is the filter value (default 'id'; use 'external_id' for channel taxonomy) */
  idKey?: string;
  /** Which API field is the display name (default 'name', falls back to 'value') */
  nameKey?: string;
  /** Page size for option fetches */
  perPage?: number;
  placeholder?: string;
}

/**
 * Async SearchableMultiSelect: options are fetched from `endpoint` with a
 * debounced server-side `q` search, so tables with hundreds of thousands of
 * rows are supported. Selected chips keep their labels via an accumulate-only
 * option cache, even when the selection is not in the current result page.
 */
export default function EntityMultiSelect({
  endpoint,
  label,
  selected,
  onChange,
  extraParams = {},
  idKey = 'id',
  nameKey = 'name',
  perPage = 50,
  placeholder,
}: EntityMultiSelectProps) {
  const [options, setOptions] = useState<EntityOption[]>([]);
  const [loading, setLoading] = useState(false);
  const knownRef = useRef<Map<string, EntityOption>>(new Map());
  const seqRef = useRef(0);

  const toOption = useCallback(
    (item: Record<string, unknown>): EntityOption => ({
      id: item[idKey] as string | number,
      name:
        (item[nameKey] as string | undefined) ??
        (item.value as string | undefined) ??
        `#${item[idKey]}`,
    }),
    [idKey, nameKey],
  );

  const search = useCallback(
    (q: string) => {
      const seq = ++seqRef.current;
      setLoading(true);
      api
        .get<{ items: Record<string, unknown>[] }>(
          endpoint + qs({ ...extraParams, q: q || undefined, per_page: perPage }),
        )
        .then((d) => {
          if (seq !== seqRef.current) return;
          const opts = (d.items || []).map(toOption);
          // Deduplicate by id — some API endpoints (e.g. external-attributes
          // without a category filter) can return the same external_id in
          // multiple rows (same attribute across different categories).
          const seen = new Set<string>();
          const deduped: EntityOption[] = [];
          for (const o of opts) {
            const k = String(o.id);
            if (!seen.has(k)) { seen.add(k); deduped.push(o); }
          }
          deduped.forEach((o) => knownRef.current.set(String(o.id), o));
          setOptions(deduped);
        })
        .catch(() => {
          if (seq === seqRef.current) setOptions([]);
        })
        .finally(() => {
          if (seq === seqRef.current) setLoading(false);
        });
    },
    [endpoint, JSON.stringify(extraParams), perPage, toOption],
  );

  // Initial unscoped page (alphabetical head); typing refetches server-side.
  useEffect(() => {
    search('');
  }, [search]);

  // Keep selected chips renderable even when not in the current page.
  const selectedKnown = selected.map((id) => knownRef.current.get(String(id)));
  const pageIds = new Set(options.map((o) => String(o.id)));
  const merged = [
    ...options,
    ...selectedKnown
      .map((o, i) => o ?? { id: selected[i], name: `#${selected[i]}` })
      .filter((o): o is EntityOption => !!o && !pageIds.has(String(o.id))),
  ];

  return (
    <SearchableMultiSelect
      options={merged}
      selected={selected}
      onChange={onChange}
      label={label}
      loading={loading}
      placeholder={placeholder ?? 'Введіть для пошуку...'}
      onSearch={search}
    />
  );
}

/** Loads the (small) internal category tree once for static multi-selects. */
export function useInternalCategories(endpoint = '/categories?per_page=500') {
  const [cats, setCats] = useState<CatOpt[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api
      .get<{ items: CatOpt[] }>(endpoint)
      .then((d) => setCats(d.items || []))
      .catch(() => setCats([]))
      .finally(() => setLoading(false));
  }, [endpoint]);
  return { cats, loading };
}

interface StaticMsProps {
  label: string;
  selected: (string | number)[];
  onChange: (ids: (string | number)[]) => void;
  cats: CatOpt[];
  loading: boolean;
}

/** Внутрішня категорія — static options from the loaded category tree. */
export function InternalCategorySelect({ label, selected, onChange, cats, loading }: StaticMsProps) {
  return (
    <SearchableMultiSelect
      options={cats.map((c) => ({ id: c.id, name: c.name }))}
      selected={selected}
      onChange={onChange}
      label={label}
      loading={loading}
      placeholder="Оберіть категорію..."
    />
  );
}

/** Батьківська внутрішня категорія — real parent_id hierarchy (categories.parent_id). */
export function InternalParentCategorySelect({ label, selected, onChange, cats, loading }: StaticMsProps) {
  const parentOpts = Object.values(
    cats.reduce<Record<number, { id: number; name: string }>>((acc, c) => {
      if (c.parent_id != null && !acc[c.parent_id]) {
        const parent = cats.find((x) => x.id === c.parent_id);
        if (parent) acc[c.parent_id] = { id: parent.id, name: parent.name };
      }
      return acc;
    }, {}),
  );
  return (
    <SearchableMultiSelect
      options={parentOpts}
      selected={selected}
      onChange={onChange}
      label={label}
      loading={loading}
      placeholder="Оберіть батьківську категорію..."
    />
  );
}
