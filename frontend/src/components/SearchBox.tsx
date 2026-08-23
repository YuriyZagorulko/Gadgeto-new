'use client';
import { useEffect, useRef, useState } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { useRouter } from '@/i18n/navigation';
import { formatPrice } from '@/lib/format';

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
}

const MIN_QUERY_LENGTH = 2;
const SUGGESTION_LIMIT = 8;
const DEBOUNCE_MS = 300;

/**
 * Storefront product search input with an autocomplete suggestions dropdown.
 * Debounced suggestions are fetched from the existing backend `/search` API.
 */
export default function SearchBox({
  wrapperClassName = '',
  formClassName = 'flex items-center',
  inputClassName = 'input-field w-full text-sm',
  placeholder,
}: SearchBoxProps) {
  const t = useTranslations('search');
  const locale = useLocale();
  const router = useRouter();

  const [query, setQuery] = useState('');
  const [items, setItems] = useState<Suggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activeRef = useRef(-1);
  activeRef.current = active;

  // Navigate to the full search results page for the current query.
  const goSearch = (value?: string) => {
    const q = (value ?? query).trim();
    setOpen(false);
    setActive(-1);
    if (q) router.push(`/search?q=${encodeURIComponent(q)}`);
  };

  const selectSuggestion = (product: Suggestion) => {
    setOpen(false);
    setActive(-1);
    router.push(`/product/${encodeURIComponent(product.slug)}`);
  };

  // Fetch matching products from the existing search API.
  const fetchSuggestions = (raw: string) => {
    const q = raw.trim();
    if (q.length < MIN_QUERY_LENGTH) {
      setItems([]);
      setLoading(false);
      setOpen(false);
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
      setOpen(false);
      return;
    }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => fetchSuggestions(value), DEBOUNCE_MS);
  };

  // Close the dropdown when the user clicks anywhere outside this component.
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
      const optionCount = items.length + 1; // suggestions + "show all results"
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
        <input
          type="search"
          value={query}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onFocus={() => {
            if (query.trim().length >= MIN_QUERY_LENGTH) setOpen(true);
          }}
          placeholder={placeholder}
          className={inputClassName}
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize="none"
          spellCheck={false}
          role="combobox"
          aria-expanded={open}
          aria-controls="gadgeto-search-suggestions"
          aria-autocomplete="list"
        />
      </form>

      {open && (
        <div
          id="gadgeto-search-suggestions"
          role="listbox"
          className="absolute left-0 right-0 top-full z-[70] mt-1 bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden"
        >
          <div className="max-h-72 overflow-y-auto">
            {loading ? (
              <div className="px-3 py-2 text-sm text-gray-500">{t('loading')}</div>
            ) : error ? (
              <div className="px-3 py-2 text-sm text-gray-500">{t('error')}</div>
            ) : items.length > 0 ? (
              items.map((p, i) => (
                <button
                  key={p.id}
                  type="button"
                  role="option"
                  aria-selected={active === i}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => selectSuggestion(p)}
                  className={`w-full text-left px-3 py-2 text-sm flex items-center gap-2 ${
                    active === i ? 'bg-blue-50' : 'bg-white hover:bg-gray-50'
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
                  <span className="flex-shrink-0 font-semibold text-blue-700 whitespace-nowrap">
                    {formatPrice(p.price, locale)}
                  </span>
                </button>
              ))
            ) : (
              <div className="px-3 py-2 text-sm text-gray-500">{t('noResults')}</div>
            )}
          </div>

          <button
            type="button"
            role="option"
            aria-selected={active === items.length}
            onMouseEnter={() => setActive(items.length)}
            onClick={() => goSearch(undefined)}
            className={`w-full text-left px-3 py-2 text-sm font-medium border-t border-gray-200 ${
              active === items.length ? 'bg-blue-50 text-blue-700' : 'bg-white text-blue-700 hover:bg-gray-50'
            }`}
          >
            {t('showAll')} ›
          </button>
        </div>
      )}
    </div>
  );
}