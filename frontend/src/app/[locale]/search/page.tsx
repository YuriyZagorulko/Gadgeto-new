import { getTranslations, setRequestLocale } from 'next-intl/server';
import { hasLocale } from 'next-intl';
import { notFound } from 'next/navigation';
import { routing } from '@/i18n/routing';
import ProductCard from '@/components/ProductCard';
import FiltersSidebar from '@/components/FiltersSidebar';
import SortSelect from '@/components/SortSelect';
import CatalogPagination from '@/components/CatalogPagination';
import {
  buildProductsApiUrl,
  parseCatalogParams,
  rawParamsRecord,
  type CatalogQuery,
  type RawParams,
} from '@/lib/catalogParams';

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://backend:8000').replace(/\/+$/, '');
const PAGE_SIZE = 24;

/** Admin-configured category filters for the selected category (may be null). */
async function getFilters(slug: string) {
  try {
    const url = new URL(`/api/v1/categories/${encodeURIComponent(slug)}/filters`, API_BASE).toString();
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) return null;
    return res.json();
  } catch { return null; }
}

async function getCategoriesTree() {
  try {
    const res = await fetch(new URL('/api/v1/categories', API_BASE).toString(), { cache: 'no-store' });
    if (!res.ok) return [];
    const d = await res.json();
    return d.items ?? [];
  } catch { return []; }
}

/** Products endpoint (not /search) so q, price and attribute filters combine server-side. */
async function getProducts(query: CatalogQuery) {
  try {
    const url = buildProductsApiUrl(API_BASE, query, PAGE_SIZE);
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) return { items: [], total: 0, total_pages: 1 };
    return res.json();
  } catch { return { items: [], total: 0, total_pages: 1 }; }
}

export async function generateMetadata({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string }>;
  searchParams: Promise<RawParams>;
}) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) return {};

  const t = await getTranslations({ locale, namespace: 'search' });
  const query = parseCatalogParams(await searchParams);
  const q = query.q;
  const canonical = q ? `/search?q=${encodeURIComponent(q)}` : '/search';

  return {
    title: q ? t('resultsFor', { q }) : t('title'),
    alternates: {
      canonical,
      languages: { uk: canonical, 'x-default': canonical },
    },
  };
}

export default async function SearchPage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string }>;
  searchParams: Promise<RawParams>;
}) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);

  const sp = await searchParams;
  const query = parseCatalogParams(sp);
  const [products, filters, categories] = await Promise.all([
    getProducts(query),
    query.category ? getFilters(query.category) : Promise.resolve(null),
    getCategoriesTree(),
  ]);

  const t = await getTranslations('search');
  const tProducts = await getTranslations('products');

  const basePath = '/search';
  const pageParams = rawParamsRecord(sp);
  const total = products.total ?? products.items?.length ?? 0;
  const totalPages = products.total_pages ?? Math.max(1, Math.ceil(total / PAGE_SIZE));
  const bare = !query.q && !query.category && query.attrs.length === 0 &&
    query.priceMin === null && query.priceMax === null;

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-2xl font-bold">
          {query.q ? t('resultsFor', { q: query.q }) : t('title')}
        </h1>
        {!bare && (
          <span className="text-sm text-gray-500">
            {tProducts('productsCount', { count: total })}
          </span>
        )}
      </div>

      <div className="flex gap-6 items-start">
        <div className="w-full md:w-64 md:flex-shrink-0">
          <FiltersSidebar
            basePath={basePath}
            params={pageParams}
            filters={filters?.filters ?? []}
            categories={categories}
            activeCategorySlug={query.category || undefined}
            categoryMode="param"
          />
        </div>

        <div className="flex-1 min-w-0">
          {bare ? (
            <p className="text-gray-500 mt-4">{t('entryPrompt')}</p>
          ) : (products.items || []).length > 0 ? (
            <>
              <div className="flex justify-end mb-3">
                <SortSelect basePath={basePath} params={pageParams} value={query.sort} />
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                {products.items.map((p: any) => <ProductCard key={p.id} product={p} />)}
              </div>
              <CatalogPagination
                basePath={basePath}
                params={pageParams}
                page={query.page}
                totalPages={totalPages}
              />
            </>
          ) : (
            <p className="text-gray-500 mt-4">{t('noResults')}</p>
          )}
        </div>
      </div>
    </div>
  );
}