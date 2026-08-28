import { getTranslations, setRequestLocale } from 'next-intl/server';
import { hasLocale } from 'next-intl';
import { notFound } from 'next/navigation';
import { Link } from '@/i18n/navigation';
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

async function getCategory(slug: string) {
  try {
    const url = new URL(`/api/v1/categories/${slug}`, API_BASE).toString();
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) return null;
    return res.json();
  } catch { return null; }
}

/** Admin-configured category filters (source of truth for the sidebar). */
async function getFilters(slug: string) {
  try {
    const url = new URL(`/api/v1/categories/${slug}/filters`, API_BASE).toString();
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

async function getProducts(query: CatalogQuery, catSlug: string) {
  try {
    const url = buildProductsApiUrl(API_BASE, { ...query, category: catSlug }, PAGE_SIZE);
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) return { items: [], total: 0, total_pages: 1 };
    return res.json();
  } catch { return { items: [], total: 0, total_pages: 1 }; }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}) {
  const { locale, slug: rawSlug } = await params;
  // Next.js App Router delivers dynamic params percent-encoded; decode once so
  // downstream URLs (categories/products APIs) do not get double-encoded.
  const slug = decodeURIComponent(rawSlug);
  if (!hasLocale(routing.locales, locale)) return {};
  const tCatalog = await getTranslations({ locale, namespace: 'catalog' });
  const category = await getCategory(slug);
  const title = category?.name || tCatalog('metaTitle');

  return {
    title,
    alternates: {
      canonical: `/catalog/${slug}`,
      languages: {
        uk: `/catalog/${slug}`,
        'x-default': `/catalog/${slug}`,
      },
    },
  };
}

export default async function CatalogSlugPage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string; slug: string }>;
  searchParams: Promise<RawParams>;
}) {
  const { locale, slug: rawSlug } = await params;
  // Decode once at the route boundary (see note in generateMetadata).
  const slug = decodeURIComponent(rawSlug);
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);

  const sp = await searchParams;
  const query = parseCatalogParams(sp);
  const [category, filters, categories, products] = await Promise.all([
    getCategory(slug),
    getFilters(slug),
    getCategoriesTree(),
    getProducts(query, slug),
  ]);
  if (!category) notFound();

  const t = await getTranslations('catalog');
  const tProducts = await getTranslations('products');

  const basePath = `/catalog/${slug}`;
  const pageParams = rawParamsRecord(sp);
  const total = products.total ?? products.items?.length ?? 0;
  const totalPages = products.total_pages ?? Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <nav className="text-sm text-gray-500 mb-4">
        <Link href="/catalog" className="hover:text-blue-600">{t('title')}</Link>
        {category.breadcrumbs?.map((b: any) => (
          <span key={b.slug}> <span className="mx-1">›</span> <Link href={"/catalog/" + b.slug} className="hover:text-blue-600">{b.name}</Link></span>
        ))}
        <span className="mx-1">›</span>
        <span className="text-gray-800">{category.name}</span>
      </nav>

      <div className="flex gap-6 items-start">
        <div className="w-full md:w-64 md:flex-shrink-0">
          <FiltersSidebar
            basePath={basePath}
            params={pageParams}
            filters={filters?.filters ?? []}
            categories={categories}
            activeCategorySlug={slug}
            categoryMode="path"
          />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
            <h1 className="text-2xl font-bold">{category.name}</h1>
            <div className="flex items-center gap-4">
              <SortSelect basePath={basePath} params={pageParams} value={query.sort} />
              <span className="text-sm text-gray-500">
                {tProducts('productsCount', { count: total })}
              </span>
            </div>
          </div>

          {(products.items || []).length > 0 ? (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {(products.items || []).map((p: any) => <ProductCard key={p.id} product={p} />)}
            </div>
          ) : (
            <p className="text-gray-500 mt-4">{t('noProducts')}</p>
          )}

          <CatalogPagination
            basePath={basePath}
            params={pageParams}
            page={query.page}
            totalPages={totalPages}
          />
        </div>
      </div>
    </div>
  );
}
