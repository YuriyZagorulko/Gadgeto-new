import { getTranslations, setRequestLocale } from 'next-intl/server';
import { hasLocale } from 'next-intl';
import { notFound } from 'next/navigation';
import { Link } from '@/i18n/navigation';
import { routing } from '@/i18n/routing';
import ProductCard from '@/components/ProductCard';

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://backend:8000').replace(/\/+$/, '');

async function getCategory(slug: string) {
  try {
    const url = new URL(`/api/v1/categories/${slug}`, API_BASE).toString();
    const res = await fetch(url);
    if (!res.ok) return null;
    return res.json();
  } catch { return null; }
}

async function getFilters(slug: string) {
  try {
    const url = new URL(`/api/v1/categories/${slug}/filters`, API_BASE).toString();
    const res = await fetch(url);
    if (!res.ok) return null;
    return res.json();
  } catch { return null; }
}

async function getProducts(catSlug: string) {
  try {
    const url = new URL(`/api/v1/products?category=${encodeURIComponent(catSlug)}&page=1&page_size=24`, API_BASE).toString();
    const res = await fetch(url);
    if (!res.ok) return { items: [], total: 0 };
    return res.json();
  } catch { return { items: [], total: 0 }; }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}) {
  const { locale, slug } = await params;
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
}: {
  params: Promise<{ locale: string; slug: string }>;
}) {
  const { locale, slug } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);

  const [category, filters, products] = await Promise.all([
    getCategory(slug), getFilters(slug), getProducts(slug)
  ]);
  if (!category) notFound();

  const t = await getTranslations('catalog');
  const tFilters = await getTranslations('filters');
  const tProducts = await getTranslations('products');

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

      <div className="flex gap-6">
        <aside className="w-64 flex-shrink-0 hidden md:block space-y-4">
          <div className="bg-white rounded-lg p-4 shadow-sm">
            <h3 className="font-semibold mb-3">{tFilters('title')}</h3>
            {filters?.filters?.length > 0 ? (
              filters.filters.map((f: any) => (
                <div key={f.attribute_id} className="mb-4">
                  <h4 className="text-sm font-medium mb-2">{f.attribute_name}</h4>
                  {f.values?.slice(0, 8).map((v: any) => (
                    <label key={v.value} className="flex items-center gap-2 text-sm mb-1 cursor-pointer">
                      <input type="checkbox" className="rounded" />
                      <span>{v.value} <span className="text-gray-400">({v.count})</span></span>
                    </label>
                  ))}
                </div>
              ))
            ) : (
              <p className="text-sm text-gray-500">{t('noFilters')}</p>
            )}
          </div>
        </aside>

        <div className="flex-1">
          <div className="flex justify-between items-center mb-4">
            <h1 className="text-2xl font-bold">{category.name}</h1>
            <span className="text-sm text-gray-500">{tProducts('productsCount', { count: products.total ?? products.items?.length ?? 0 })}</span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {(products.items || []).map((p: any) => <ProductCard key={p.id} product={p} />)}
          </div>
          {products.items?.length === 0 && <p className="text-gray-500 mt-4">{t('noProducts')}</p>}
        </div>
      </div>
    </div>
  );
}
