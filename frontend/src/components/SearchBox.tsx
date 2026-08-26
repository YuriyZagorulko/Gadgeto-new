'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslations } from 'next-intl';
import { useRouter } from '@/i18n/navigation';
import PriceDisplay from '@/components/PriceDisplay';

interface Suggestion {
  id: number;
  sku?: string;
  name: string;
  slug: string;
  price: number;
  old_price?: number | null;
  stock_status?: string;
  image?: string;
}

interface SearchBoxProps {
  /** Extra classes for the outer `relative` container. */
  wrapperClassName?: string;
  /** Classes for the inner `<form>`. */
  formClassName?: string;
  /** Classes for the search `<input>`. */
  inputClassName?: string;
  placeholder?: string;
  /** Whether to show the submit button next to the input. Default true. */
  showSubmitButton?: boolean;
}

const MIN_QUERY_LENGTH = 2;
const SUGGESTION_LIMIT = 8;
const DEBOUNCE_MS = 300;
const HISTORY_KEY = 'gadgeto_search_history';
const HISTORY_MAX = 10;

// ── localStorage search history helpers ──────────────────────────────

function loadHistory(): string[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((s): s is string => typeof s === 'string' && s.trim().length > 0);
  } catch {
    return [];
  }
}

function saveHistory(query: string): void {
  try {
    const q = query.trim();
    if (!q) return;
    const history = loadHistory();
    // Remove duplicates (case-insensitive comparison) & keep max
    const filtered = history.filter(
      (s) => s.toLowerCase() !== q.toLowerCase()
    );
    filtered.unshift(q);
    localStorage.setItem(HISTORY_KEY, JSON.stringify(filtered.slice(0, HISTORY_MAX)));
  } catch {
    // Silently ignore localStorage errors
  }
}

// ── Component ────────────────────────────────────────────────────────

export default function SearchBox({
  wrapperClassName = '',
  formClassName = 'flex items-center',
  inputClassName = 'input-field w-full text-sm',
  placeholder,
  showSubmitButton = true,
}: SearchBoxProps) {
  const t = useTranslations('search');
  const router = useRouter();

  const [query, setQuery] = useState('');
  const [items, setItems] = useState<Suggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [history, setHistory] = useState<string[]>([]);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activeRef = useRef(-1);
  activeRef.current = active;

  // Reload history from localStorage (called on mount & after saving).
  const refreshHistory = useCallback(() => {
    setHistory(loadHistory());
  }, []);

  useEffect(() => {
    refreshHistory();
  }, [refreshHistory]);

  // ── Navigation ──────────────────────────────────────────────────────

  /** Navigate to the full search results page. Falls back to window.location if needed. */
  const goSearch = (value?: string) => {
    const q = (value ?? query).trim();
    if (!q) return;
    setOpen(false);
    setActive(-1);
    // Save to search history
    saveHistory(q);
    refreshHistory();
    // Navigate using i18n router, with a hard-nav fallback
    const url = `/search?q=${encodeURIComponent(q)}`;
    try {
      router.push(url);
    } catch {
      window.location.href = url;
    }
  };

  const selectSuggestion = (product: Suggestion) => {
    setOpen(false);
    setActive(-1);
    router.push(`/product/${encodeURIComponent(product.slug)}`);
  };

  const handleHistoryClick = (q: string) => {
    setQuery(q);
    goSearch(q);
  };

  // ── Suggestions fetching ──────────────────────────────────────────────

  // Fetch matching products from the existing search API.
  const fetchSuggestions = (raw: string) => {
    const q = raw.trim();
    if (q.length < MIN_QUERY_LENGTH) {
      setItems([]);
      setLoading(false);
      if (history.length > 0) {
        setOpen(true); // keep open for history
      } else {
        setOpen(false);
      }
      return;
    }
    setLoading(true);
    setError(false);
    fetch(`/api/search?q=${encodeURIComponent(q)}&page=1&page_size=${SUGGESTION_LIMIT}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => {
        setItems(d?.items || []);
        setLoading(false);
        setOpen(true);
      })
      .catch(() => {
        setError(true);
        setItems([]);
        setLoading(false);
        setOpen(true);
      });
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setQuery(value);
    if (value.trim().length < MIN_QUERY_LENGTH) {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      setItems([]);
      setLoading(false);
      // Show history when query is too short but there is history
      setOpen(history.length > 0);
      return;
    }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => fetchSuggestions(value), DEBOUNCE_MS);
  };

  // ── Outside click handling ───────────────────────────────────────────

  useEffect(() => {
    if (!open) return;
    const onDocClick = (ev: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(ev.target as Node)) {
        setOpen(false);
        setActive(-1);
      }
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, [open]);

  // Clear any pending debounce timer on unmount.
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  // ── Keyboard handling ────────────────────────────────────────────────

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      setOpen(false);
      setActive(-1);
      return;
    }

    if (e.key === 'Enter') {
      e.preventDefault();
      const current = activeRef.current;
      if (current >= 0 && items[current]) {
        selectSuggestion(items[current]);
      } else {
        goSearch();
      }
      return;
    }

    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      const suggestionCount = items.length;
      const showHistorySection = query.trim().length < MIN_QUERY_LENGTH && history.length > 0;
      const optionCount = suggestionCount + 1 + (showHistorySection ? history.length : 0);
      const current = activeRef.current;
      if (current < 0) {
        setActive(e.key === 'ArrowDown' ? 0 : optionCount - 1);
        setOpen(true);
      } else {
        const delta = e.key === 'ArrowDown' ? 1 : -1;
        setActive((current + delta + optionCount) % optionCount);
      }
    }
  };

  // ── Determine what to show in the dropdown ───────────────────────────

  const showHistorySection = query.trim().length < MIN_QUERY_LENGTH && history.length > 0;
  const hasSuggestions = items.length > 0;

  /** Offset for ARIA active index: history items come before suggestions. */
  const historyOffset = 0;
  const suggestionsOffset = showHistorySection ? history.length : 0;

  return (
    <div ref={containerRef} className={`relative ${wrapperClassName}`}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          goSearch(undefined);
        }}
        className={formClassName}
        role="search"
      >
        <div className="relative flex flex-1">
          <input
            type="search"
            value={query}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            onFocus={() => {
              // Show history dropdown immediately even when empty
              if (query.trim().length < MIN_QUERY_LENGTH) {
                if (history.length > 0) {
                  setOpen(true);
                }
              } else {
                setOpen(true);
              }
            }}
            placeholder={placeholder}
            className={`${inputClassName}${showSubmitButton ? ' rounded-r-none' : ''}`}
            autoComplete="off"
            autoCorrect="off"
            autoCapitalize="none"
            spellCheck={false}
            role="combobox"
            aria-expanded={open}
            aria-controls="gadgeto-search-suggestions"
            aria-autocomplete="list"
          />
          {showSubmitButton && (
            <button
              type="submit"
              className="flex-shrink-0 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-r-lg transition-colors"
            >
              {t('find')}
            </button>
          )}
        </div>
      </form>

      {open && (
        <div
          id="gadgeto-search-suggestions"
          role="listbox"
          className="absolute left-0 right-0 top-full z-[70] mt-1 bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden"
        >
          <div className="max-h-72 overflow-y-auto">
            {/* ── History section (shown when input is empty/short) ── */}
            {showHistorySection && (
              <>
                <div className="px-3 py-1.5 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  {t('historyTitle')}
                </div>
                {history.map((h, i) => (
                  <button
                    key={`h-${i}`}
                    type="button"
                    role="option"
                    aria-selected={active === historyOffset + i}
                    onMouseEnter={() => setActive(historyOffset + i)}
                    onClick={() => handleHistoryClick(h)}
                    className={`w-full text-left px-3 py-2 text-sm flex items-center gap-2 ${
                      active === historyOffset + i
                        ? 'bg-blue-50'
                        : 'bg-white hover:bg-gray-50'
                    }`}
                  >
                    <svg
                      className="w-4 h-4 flex-shrink-0 text-gray-400"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <circle cx="12" cy="12" r="10" />
                      <polyline points="12 6 12 12 16 14" />
                    </svg>
                    <span className="flex-1 min-w-0 truncate">{h}</span>
                  </button>
                ))}
              </>
            )}

            {/* ── Loading / Error / Suggestions ── */}
            {showHistorySection && (loading || error || hasSuggestions) && (
              <div className="border-t border-gray-100" />
            )}

            {loading ? (
              <div className="px-3 py-2 text-sm text-gray-500">{t('loading')}</div>
            ) : error ? (
              <div className="px-3 py-2 text-sm text-gray-500">{t('error')}</div>
            ) : hasSuggestions ? (
              items.map((p, i) => (
                <button
                  key={p.id}
                  type="button"
                  role="option"
                  aria-selected={active === suggestionsOffset + i}
                  onMouseEnter={() => setActive(suggestionsOffset + i)}
                  onClick={() => selectSuggestion(p)}
                  className={`w-full text-left px-3 py-2 text-sm flex items-center gap-2 ${
                    active === suggestionsOffset + i
                      ? 'bg-blue-50'
                      : 'bg-white hover:bg-gray-50'
                  }`}
                >
                  {p.image ? (
                    <img src={p.image} alt="" className="w-8 h-8 rounded object-cover flex-shrink-0" />
                  ) : (
                    <span className="w-8 h-8 rounded bg-gray-100 flex items-center justify-center text-xs text-gray-400 flex-shrink-0">
                      {t('noImage')}
                    </span>
                  )}
                  <span className="flex-1 min-w-0 truncate">{p.name}</span>
                  <PriceDisplay price={p.price} oldPrice={p.old_price} variant="inline" />
                </button>
              ))
            ) : !showHistorySection && (
              <div className="px-3 py-2 text-sm text-gray-500">{t('noResults')}</div>
            )}
          </div>

          {/* ── "Show all results" button ── */}
          {(hasSuggestions || query.trim().length >= MIN_QUERY_LENGTH) && (
            <button
              type="button"
              role="option"
              aria-selected={
                active === suggestionsOffset + items.length
              }
              onMouseEnter={() =>
                setActive(suggestionsOffset + items.length)
              }
              onClick={() => goSearch(undefined)}
              className={`w-full text-left px-3 py-2 text-sm font-medium border-t border-gray-200 ${
                active === suggestionsOffset + items.length
                  ? 'bg-blue-50 text-blue-700'
                  : 'bg-white text-blue-700 hover:bg-gray-50'
              }`}
            >
              {t('showAll')} ›
            </button>
          )}
        </div>
      )}
    </div>
  );
}