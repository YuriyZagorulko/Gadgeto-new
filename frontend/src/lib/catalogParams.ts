/**
 * Shared catalog filter-parameter handling for the public storefront.
 *
 * URL is the single source of truth. One parser builds the same view of the
 * query for server pages (data fetching) and the client sidebar (URL edits).
 *
 * Parameter conventions (matching GET /api/v1/products):
 *   q          — keyword search;
 *   category   — category slug (search page only; catalog pages carry the
 *                category in the path);
 *   price_min / price_max — price bounds in kopiykas (canonical DB unit);
 *   f<attribute_id>       — attribute filter, comma-separated values;
 *   sort, page, page_size — as supported by the products endpoint.
 *
 * The price inputs are labelled in ₴ (major units); conversion to/from
 * kopiykas happens only here and in FiltersSidebar — never inline elsewhere.
 */

export type AttrFilter = { attributeId: number; values: string[] };

export type CatalogQuery = {
  q: string;
  category: string;
  sort: string;
  page: number;
  priceMin: number | null; // kopiykas
  priceMax: number | null; // kopiykas
  attrs: AttrFilter[];
};

export type RawParams = Record<string, string | string[] | undefined>;

const first = (v: string | string[] | undefined): string => {
  const s = Array.isArray(v) ? v[0] : v;
  return typeof s === 'string' ? s.trim() : '';
};

const toInt = (s: string): number | null => {
  if (!/^\d{1,9}$/.test(s)) return null;
  return parseInt(s, 10);
};

/** UAH → kopiykas; accepts comma decimal separator; null on empty/invalid. */
export function uahToKop(input: string): number | null {
  const s = input.trim().replace(',', '.');
  if (!s || !/^\d{1,9}(\.\d{1,2})?$/.test(s)) return null;
  return Math.round(parseFloat(s) * 100);
}

/** kopiykas → UAH string for input display. */
export function kopToUah(kop: number | null | undefined): string {
  if (kop === null || kop === undefined) return '';
  return String(kop / 100);
}

export function parseCatalogParams(sp: RawParams | undefined | null): CatalogQuery {
  const q: CatalogQuery = {
    q: '',
    category: '',
    sort: '',
    page: 1,
    priceMin: null,
    priceMax: null,
    attrs: [],
  };
  if (!sp) return q;

  q.q = first(sp.q).slice(0, 100);
  q.category = first(sp.category).slice(0, 120);
  const sort = first(sp.sort);
  q.sort = ['price_asc', 'price_desc', 'name', 'newest'].includes(sort) ? sort : '';
  const page = toInt(first(sp.page));
  if (page !== null && page >= 1) q.page = Math.min(page, 10000);

  const min = toInt(first(sp.price_min));
  const max = toInt(first(sp.price_max));
  if (min !== null) q.priceMin = min;
  if (max !== null) q.priceMax = max;

  for (const [key, rawVal] of Object.entries(sp)) {
    if (!/^f\d{1,6}$/.test(key)) continue;
    const arr = Array.isArray(rawVal) ? rawVal : [rawVal];
    const values = [
      ...new Set(
        arr
          .flatMap((v) => (typeof v === 'string' ? v.split(',') : []))
          .map((v) => v.trim())
          .filter(Boolean)
          .slice(0, 50)
      ),
    ];
    if (values.length) q.attrs.push({ attributeId: parseInt(key.slice(1), 10), values });
    if (q.attrs.length >= 20) break;
  }
  return q;
}

/** Builds the public /api/v1/products URL for a parsed query. */
export function buildProductsApiUrl(apiBase: string, query: CatalogQuery, pageSize: number): string {
  const url = new URL('/api/v1/products', apiBase);
  if (query.q) url.searchParams.set('q', query.q);
  if (query.category) url.searchParams.set('category', query.category);
  if (query.priceMin !== null) url.searchParams.set('price_min', String(query.priceMin));
  if (query.priceMax !== null) url.searchParams.set('price_max', String(query.priceMax));
  if (query.sort) url.searchParams.set('sort', query.sort);
  for (const a of query.attrs) {
    url.searchParams.set(`f${a.attributeId}`, a.values.join(','));
  }
  url.searchParams.set('page', String(query.page));
  url.searchParams.set('page_size', String(pageSize));
  return url.toString();
}

/** Flattens Next.js searchParams into a plain single-value record (for the sidebar). */
export function rawParamsRecord(sp: RawParams): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(sp)) {
    const s = first(v);
    if (s) out[k] = s;
  }
  return out;
}
