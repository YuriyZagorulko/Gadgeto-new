'use client';
import { useEffect, useMemo, useRef, useState } from 'react';

export interface CatOption {
  id: number;
  name: string;
  parent_id: number | null;
}

/**
 * Searchable multi-select for categories with removable chips.
 * Fetches the full category tree once (147 rows — fine), filters client-side,
 * shows hierarchical "Parent → Child" labels. Replaces the checkbox grid.
 */
export default function CategorySelect({
  value,
  options,
  onChange,
}: {
  value: number[];
  options: CatOption[];
  onChange: (ids: number[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  const byId = useMemo(() => new Map(options.map((c) => [c.id, c])), [options]);
  const path = (id: number): string => {
    const c = byId.get(id);
    if (!c) return `#${id}`;
    return c.parent_id ? `${path(c.parent_id)} → ${c.name}` : c.name;
  };

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = q ? options.filter((c) => path(c.id).toLowerCase().includes(q)) : options;
    return list.slice(0, 60);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options, query, byId]);

  const toggle = (id: number) =>
    onChange(value.includes(id) ? value.filter((v) => v !== id) : [...value, id]);

  return (
    <div className="relative" ref={boxRef}>
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {value.map((id) => (
            <span key={id} className="inline-flex items-center gap-1 bg-blue-900/60 border border-blue-700 text-blue-100 text-xs px-2 py-1 rounded">
              {path(id)}
              <button type="button" onClick={() => toggle(id)} className="text-blue-300 hover:text-white ml-0.5" aria-label="Видалити">×</button>
            </span>
          ))}
        </div>
      )}
      <button type="button" onClick={() => setOpen(!open)} className="w-full text-left input-field flex justify-between items-center">
        <span className="text-gray-400">+ Обрати категорії…</span>
        <span className="text-gray-500">▾</span>
      </button>
      {open && (
        <div className="absolute z-20 mt-1 w-full bg-gray-900 border border-gray-700 rounded shadow-lg max-h-72 overflow-auto">
          <div className="sticky top-0 bg-gray-900 p-2 border-b border-gray-700">
            <input autoFocus value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Пошук категорій…" className="input-field text-sm w-full" />
          </div>
          {results.length === 0 && <div className="p-3 text-sm text-gray-500">Нічого не знайдено</div>}
          {results.map((c) => (
            <label key={c.id} className="flex items-center gap-2 px-3 py-1.5 text-sm hover:bg-gray-800 cursor-pointer">
              <input type="checkbox" checked={value.includes(c.id)} onChange={() => toggle(c.id)} className="rounded bg-gray-800 border-gray-600" />
              <span>{path(c.id)}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
