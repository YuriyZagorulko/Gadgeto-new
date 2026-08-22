import { getTranslations, setRequestLocale } from 'next-intl/server';
import { hasLocale } from 'next-intl';
import { notFound } from 'next/navigation';
import { Link } from '@/i18n/navigation';
import { routing } from '@/i18n/routing';
import ProductCard from '@/components/ProductCard';

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://backend:8000').replace(/\/+$/, '');

async function getData() {
  try {
    const [catsRes, prodsRes] = await Promise.all([
      fetch(new URL('/api/v1/categories', API_BASE).toString(), { next: { revalidate: 300 } }),
      fetch(new URL('/api/v1/products?page=1&page_size=12', API_BASE).toString(), { next: { revalidate: 300 } }),
    ]);
    const cats = await catsRes.json();
    const prods = await prodsRes.json();
    return { categories: cats.items || [], products: prods.items || [] };
  } catch {
    return { categories: [], products: [] };
  }
}

export default async function HomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);

  const t = await getTranslations('home');
  const tProducts = await getTranslations('products');
  const { categories, products } = await getData();
  const rootCats = (categories || []).filter((c: any) => !c.parent_id);

  return (
    <div>
      <section className="bg-gradient-to-r from-blue-700 to-blue-900 text-white py-16">
        <div className="max-w-7xl mx-auto px-4">
          <h1 className="text-4xl md:text-5xl font-bold mb-4">{t('heroTitle')}</h1>
          <p className="text-xl mb-8 max-w-2xl text-blue-100">{t('heroSubtitle')}</p>
          <Link href="/catalog" className="inline-block bg-white text-blue-700 px-6 py-3 rounded-lg font-semibold hover:bg-blue-50 transition">{t('shopNow')}</Link>
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-4 py-12">
        <h2 className="text-2xl font-bold mb-6">{t('categoriesTitle')}</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {(rootCats as any[]).slice(0, 10).map((cat: any) => (
            <Link key={cat.slug} href={`/catalog/${cat.slug}`} className="card p-4 text-center hover:border-blue-300">
              <div className="font-medium text-sm">{cat.name}</div>
              {cat.product_count > 0 && <div className="text-xs text-gray-500 mt-1">{tProducts('productsCount', { count: cat.product_count })}</div>}
            </Link>
          ))}
        </div>
      </section>

      {products.length > 0 && (
        <section className="max-w-7xl mx-auto px-4 py-12">
          <h2 className="text-2xl font-bold mb-6">{t('latestProductsTitle')}</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-4">
            {(products as any[]).map((p: any) => <ProductCard key={p.id} product={p} />)}
          </div>
        </section>
      )}
    </div>
  );
}
