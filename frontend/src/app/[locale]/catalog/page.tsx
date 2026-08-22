import { getTranslations, setRequestLocale } from 'next-intl/server';
import { hasLocale } from 'next-intl';
import { notFound } from 'next/navigation';
import { Link } from '@/i18n/navigation';
import { routing } from '@/i18n/routing';

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://backend:8000').replace(/\/+$/, '');

async function getCategories() {
  try {
    const res = await fetch(new URL('/api/v1/categories', API_BASE).toString(), { next: { revalidate: 300 } });
    if (!res.ok) return { items: [] };
    return res.json();
  } catch { return { items: [] }; }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const t = await getTranslations({
    locale: hasLocale(routing.locales, locale) ? locale : routing.defaultLocale,
    namespace: 'catalog',
  });
  return {
    title: t('metaTitle'),
    alternates: {
      canonical: '/catalog',
      languages: { uk: '/catalog', 'x-default': '/catalog' },
    },
  };
}

export default async function CatalogRoot({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);

  const t = await getTranslations('catalog');
  const tProducts = await getTranslations('products');
  const { items: cats } = await getCategories();
  const roots = (cats || []).filter((c: any) => !c.parent_id);

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-8">{t('title')}</h1>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {(roots || []).map((cat: any) => (
          <Link key={cat.slug} href={`/catalog/${cat.slug}`} className="card p-6 text-center hover:border-blue-300">
            <div className="font-semibold text-lg">{cat.name}</div>
            {cat.product_count > 0 && <div className="text-sm text-gray-500 mt-1">{tProducts('productsCount', { count: cat.product_count })}</div>}
            {cat.children?.length > 0 && <div className="text-xs text-gray-400 mt-1">{tProducts('subcategoriesCount', { count: cat.children.length })}</div>}
          </Link>
        ))}
      </div>
    </div>
  );
}
