'use client';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

export interface CatOption {
  id: number;
  name: string;
  parent_id: number | null;
}

/**
 * Searchable multi-select for categories with removable chips.
 * Receives the full category list as options, filters client-side,
 * shows hierarchical "Parent → Child" labels.
 *
 * The dropdown uses position:fixed so it never gets clipped by parent
 * overflow/scroll containers and always stacks above subsequent blocks.
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
  const containerRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const [menuStyle, setMenuStyle] = useState<React.CSSProperties>({});

  // Close dropdown on click outside
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  // Position the dropdown fixed relative to viewport, tracking button position
  const updateMenuPosition = useCallback(() => {
    if (!buttonRef.current) return;
    const rect = buttonRef.current.getBoundingClientRect();
    setMenuStyle({
      position: 'fixed',
      top: `${rect.bottom + 4}px`,
      left: `${rect.left}px`,
      width: `${rect.width}px`,
      zIndex: 9999,
    });
  }, []);

  useEffect(() => {
    if (!open) return;
    updateMenuPosition();
    window.addEventListener('scroll', updateMenuPosition, true);
    window.addEventListener('resize', updateMenuPosition);
    return () => {
      window.removeEventListener('scroll', updateMenuPosition, true);
      window.removeEventListener('resize', updateMenuPosition);
    };
  }, [open, updateMenuPosition]);

  const byId = useMemo(() => new Map(options.map((c) => [c.id, c])), [options]);

  const path = useCallback((id: number): string => {
    const c = byId.get(id);
    if (!c) return `#${id}`;
    return c.parent_id ? `${path(c.parent_id)} → ${c.name}` : c.name;
  }, [byId]);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = q ? options.filter((c) => path(c.id).toLowerCase().includes(q)) : options;
    return list.slice(0, 60);
  }, [options, query, path]);

  const toggle = useCallback((id: number) => {
    onChange(value.includes(id) ? value.filter((v) => v !== id) : [...value, id]);
  }, [value, onChange]);

  return (
    <div className="relative" ref={containerRef}>
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
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full text-left input-field flex justify-between items-center"
      >
        <span className="text-gray-400">+ Обрати категорії…</span>
        <span className="text-gray-500">▾</span>
      </button>
      {open && (
        <div style={menuStyle} className="border rounded shadow-lg max-h-72 overflow-auto bg-white">
          <div className="sticky top-0 p-2 border-b bg-white">
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Пошук категорій…"
              className="input-field text-sm w-full"
            />
          </div>
          {results.length === 0 && (
            <div className="p-3 text-sm text-gray-500">Нічого не знайдено</div>
          )}
          {results.map((c) => (
            <label
              key={c.id}
              className="flex items-center gap-2 px-3 py-1.5 text-sm hover:bg-gray-100 cursor-pointer"
            >
              <input
                type="checkbox"
                checked={value.includes(c.id)}
                onChange={() => toggle(c.id)}
                className="rounded border-gray-300"
              />
              <span>{path(c.id)}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
