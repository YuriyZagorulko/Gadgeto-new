"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Input } from "@/components/ui";

interface Option {
  id: string | number;
  name: string;
}

interface SearchableMultiSelectProps {
  options: Option[];
  selected: (string | number)[];
  onChange: (ids: (string | number)[]) => void;
  placeholder?: string;
  label?: string;
  loading?: boolean;
  /** How to display each option — by default shows option.name */
  displayOption?: (opt: Option) => string;
  /** How to display a selected item (chip) — by default uses displayOption */
  displaySelected?: (opt: Option) => string;
  /**
   * Async mode: called with the search text; the parent is responsible for
   * fetching options (e.g. server-side search). When set, client-side
   * filtering is skipped because options already reflect the query.
   */
  onSearch?: (q: string) => void;
}

/**
 * A searchable multi-select component for picking existing entities.
 *
 * - Opens a dropdown on click
 * - Filters as user types
 * - Multiple selections allowed (OR inside filter)
 * - Each selected item shows a × to remove individually
 * - No arbitrary values allowed
 */
export default function SearchableMultiSelect({
  options,
  selected,
  onChange,
  placeholder = "Введіть для пошуку...",
  label,
  loading = false,
  displayOption = (opt: Option) => opt.name,
  displaySelected = (opt: Option) => opt.name,
  onSearch,
}: SearchableMultiSelectProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Close on click outside
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setSearch("");
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  // In async mode options come from the server already filtered by the query.
  const filtered = onSearch
    ? options
    : search.trim()
      ? options.filter((o) =>
          displayOption(o).toLowerCase().includes(search.toLowerCase())
        )
      : options;

  const selectedSet = new Set(selected.map(String));

  const toggle = useCallback(
    (id: string | number) => {
      const key = String(id);
      const next = selectedSet.has(key)
        ? selected.filter((s) => String(s) !== key)
        : [...selected, id];
      onChange(next);
    },
    [selected, selectedSet, onChange]
  );

  const removeItem = useCallback(
    (id: string | number) => {
      onChange(selected.filter((s) => String(s) !== String(id)));
    },
    [selected, onChange]
  );

  const selectedOptions = options.filter((o) => selectedSet.has(String(o.id)));

  return (
    <div ref={containerRef} className="relative">
      {label && (
        <label className="block text-xs text-gray-500 mb-1">{label}</label>
      )}
      {/* Chips + trigger */}
      <div
        onClick={() => {
          setOpen(true);
          setTimeout(() => inputRef.current?.focus(), 50);
        }}
        className="min-h-[32px] cursor-text flex flex-wrap items-center gap-1 px-2 py-1 border border-gray-300 rounded-md bg-white text-sm hover:border-gray-400 transition-colors"
      >
        {selectedOptions.map((opt) => (
          <span
            key={opt.id}
            className="inline-flex items-center gap-1 bg-blue-50 text-blue-700 rounded-full px-2 py-0.5 text-xs font-medium"
          >
            {displaySelected(opt)}
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                removeItem(opt.id);
              }}
              className="hover:text-blue-900 leading-none text-blue-400 hover:bg-blue-100 rounded-full w-3.5 h-3.5 inline-flex items-center justify-center"
            >
              ×
            </button>
          </span>
        ))}
        <input
          ref={inputRef}
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            onSearch?.(e.target.value);
          }}
          onFocus={() => setOpen(true)}
          placeholder={selectedOptions.length === 0 ? placeholder : ""}
          className="flex-1 min-w-[60px] outline-none border-none bg-transparent text-xs py-0.5"
        />
      </div>

      {/* Dropdown */}
      {open && (
        <div className="absolute z-50 mt-1 w-full bg-white border border-gray-200 rounded-md shadow-lg max-h-60 overflow-y-auto">
          {loading && (
            <div className="px-3 py-2 text-xs text-gray-400">Завантаження...</div>
          )}
          {!loading && filtered.length === 0 && (
            <div className="px-3 py-2 text-xs text-gray-400">
              {search.trim() ? "Немає результатів" : "Немає даних"}
            </div>
          )}
          {!loading &&
            filtered.map((opt) => {
              const checked = selectedSet.has(String(opt.id));
              return (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => toggle(opt.id)}
                  className={`w-full text-left px-3 py-1.5 text-sm hover:bg-blue-50 flex items-center gap-2 ${
                    checked ? "bg-blue-50 font-medium" : ""
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    readOnly
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span>{displayOption(opt)}</span>
                </button>
              );
            })}
        </div>
      )}
    </div>
  );
}
