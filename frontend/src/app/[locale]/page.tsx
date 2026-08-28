import { getTranslations, setRequestLocale } from 'next-intl/server';
import { hasLocale } from 'next-intl';
import { notFound } from 'next/navigation';
import { Link } from '@/i18n/navigation';
import { routing } from '@/i18n/routing';
import ProductCard from '@/components/ProductCard';
import HomepageSlider from '@/components/HomepageSlider';
import HomepageViewedProducts from '@/components/HomepageViewedProducts';

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://backend:8000').replace(/\/+$/, '');

interface Slide { id: number; image: string; title: string | null; subtitle: string | null; button_text: string | null; url: string; }
interface Product { id: number; sku?: string; name: string; slug: string; price: number; old_price?: number | null; stock_status?: string; image?: string; brand?: string; }
interface Category { id: number; name: string; slug: string; parent_id: number | null; product_count?: number; children?: Category[]; }

async function getHomepageData() {
  try {
    const [homeRes, catsRes] = await Promise.all([
      fetch(new URL('/api/v1/home', API_BASE).toString(), { cache: 'no-store' }),
      fetch(new URL('/api/v1/categories', API_BASE).toString(), { cache: 'no-store' }),
    ]);
    const home = homeRes.ok ? await homeRes.json() : { slides: [], recommended: [], new_arrivals: [] };
    const cats = catsRes.ok ? await catsRes.json() : { items: [] };
    return { ...home, categories: (cats.items || []).filter((c: Category) => !c.parent_id).slice(0, 10) };
  } catch { return { slides: [], recommended: [], new_arrivals: [], categories: [] }; }
}

export default async function HomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);

  const t = await getTranslations('home');
  const { slides, recommended, new_arrivals, categories } = await getHomepageData();

  return (
    <div>
      {/* Hero + Categories Sidebar */}
      <div className="max-w-7xl mx-auto px-4 pt-6">
        <div className="flex gap-4">
          {/* Categories sidebar — desktop only */}
          {categories.length > 0 && (
            <aside className="hidden md:block w-56 shrink-0 bg-white rounded-lg border border-gray-200 p-3">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">Категорії</h3>
              <ul className="space-y-0.5">
                {(categories as Category[]).map((cat) => (
                  <li key={cat.id}>
                    <Link href={`/catalog/${cat.slug}`} className="block text-sm py-1 text-gray-700 hover:text-blue-700 hover:bg-blue-50 rounded px-2 transition">
                      {cat.name}
                    </Link>
                  </li>
                ))}
              </ul>
              <Link href="/catalog" className="block text-xs text-blue-600 hover:underline mt-2 px-2">
                Всі категорії →
              </Link>
            </aside>
          )}

          {/* Slider */}
          <div className="flex-1 min-w-0">
            {slides.length > 0 ? (
              <HomepageSlider slides={slides} />
            ) : (
              <section className="bg-gradient-to-r from-blue-700 to-blue-900 text-white rounded-lg">
                <div className="px-8 py-12">
                  <h1 className="text-3xl md:text-4xl font-bold mb-3">{t('heroTitle')}</h1>
                  <p className="text-lg mb-6 max-w-xl text-blue-100">{t('heroSubtitle')}</p>
                  <Link href="/catalog" className="inline-block bg-white text-blue-700 px-5 py-2.5 rounded-lg font-semibold hover:bg-blue-50 transition text-sm">
                    {t('shopNow')}
                  </Link>
                </div>
              </section>
            )}
          </div>
        </div>
      </div>

      {/* Sections */}
      <div className="max-w-7xl mx-auto px-4">
        {/* Recommended Products */}
        {recommended.length > 0 && (
          <section className="py-10">
            <h2 className="text-2xl font-bold mb-6">{t('recommendedTitle')}</h2>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-4">
              {(recommended as Product[]).slice(0, 12).map((p: Product) => <ProductCard key={p.id} product={p} />)}
            </div>
          </section>
        )}

        {/* New Arrivals */}
        {new_arrivals.length > 0 && (
          <section className="py-10 border-t border-gray-100">
            <h2 className="text-2xl font-bold mb-6">{t('latestProductsTitle')}</h2>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-4">
              {(new_arrivals as Product[]).map((p: Product) => <ProductCard key={p.id} product={p} />)}
            </div>
          </section>
        )}

        {/* Viewed Products (client-side, only renders when >= 6 products) */}
        <HomepageViewedProducts />
      </div>
    </div>
  );
}
