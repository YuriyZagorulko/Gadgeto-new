import { getTranslations, setRequestLocale } from 'next-intl/server';
import { hasLocale } from 'next-intl';
import { notFound } from 'next/navigation';
import { routing } from '@/i18n/routing';
import ProductCard from '@/components/ProductCard';

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://backend:8000').replace(/\/+$/, '');

type SearchParams = Record<string, string | string[] | undefined>;

/** Extracts a trimmed `q` from the URL query (handles repeated params safely). */
function extractQuery(searchParams: SearchParams): string {
  const raw = searchParams?.q;
  const value = Array.isArray(raw) ? raw[0] : raw;
  return typeof value === 'string' ? value.trim() : '';
}

async function searchProducts(query: string) {
  if (!query) return { items: [], total: 0, query: '' };
  try {
    const url = new URL('/api/v1/search', API_BASE);
    url.searchParams.set('q', query);
    url.searchParams.set('page', '1');
    url.searchParams.set('page_size', '24');
    const res = await fetch(url.toString(), { next: { revalidate: 0 } });
    if (!res.ok) return { items: [], total: 0, query };
    return res.json();
  } catch {
    return { items: [], total: 0, query };
  }
}

export async function generateMetadata({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string }>;
  searchParams: Promise<SearchParams>;
}) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) return {};

  const t = await getTranslations({ locale, namespace: 'search' });
  const q = extractQuery(await searchParams);

  return {
    title: q ? t('resultsFor', { q }) : t('title'),
    alternates: {
      canonical: q ? `/search?q=${encodeURIComponent(q)}` : '/search',
      languages: {
        uk: q ? `/search?q=${encodeURIComponent(q)}` : '/search',
        'x-default': q ? `/search?q=${encodeURIComponent(q)}` : '/search',
      },
    },
  };
}

export default async function SearchPage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string }>;
  searchParams: Promise<SearchParams>;
}) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);

  const q = extractQuery(await searchParams);
  const data = await searchProducts(q);

  const t = await getTranslations('search');
  const tProducts = await getTranslations('products');

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-2xl font-bold">
          {q ? t('resultsFor', { q }) : t('title')}
        </h1>
        {q && (
          <span className="text-sm text-gray-500">
            {tProducts('productsCount', { count: data?.total ?? 0 })}
          </span>
        )}
      </div>

      {!q ? (
        <p className="text-gray-500 mt-4">{t('entryPrompt')}</p>
      ) : (data?.items?.length ?? 0) > 0 ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {data.items.map((p: any) => <ProductCard key={p.id} product={p} />)}
        </div>
      ) : (
        <p className="text-gray-500 mt-4">{t('noResults')}</p>
      )}
    </div>
  );
}