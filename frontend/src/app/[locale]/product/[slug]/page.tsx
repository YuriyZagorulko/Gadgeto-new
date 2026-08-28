import { useLocale, useTranslations } from 'next-intl';
import { Link } from '@/i18n/navigation';
import ProductCard from '@/components/ProductCard';
import PriceDisplay from '@/components/PriceDisplay';
import AddToCartButton from '@/components/AddToCartButton';
import TrackViewedProduct from '@/components/TrackViewedProduct';
import { routing, type Locale } from '@/i18n/routing';
import { notFound } from 'next/navigation';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { hasLocale } from 'next-intl';

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://backend:8000').replace(/\/+$/, '');

async function getProduct(slug: string) {
  try {
    // Build URL via URL constructor for correct encoding
    const url = new URL(`/api/v1/products/${slug}`, API_BASE).toString();
    const res = await fetch(url, { next: { revalidate: 60 } });
    if (!res.ok) return null;
    return res.json();
  } catch { return null; }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}) {
  const { locale, slug } = await params;
  if (!hasLocale(routing.locales, locale)) return {};
  const product = await getProduct(slug);
  if (!product) return {};

  const description = typeof product.description === 'string'
    ? product.description.replace(/<[^>]+>/g, '').slice(0, 160)
    : undefined;

  return {
    title: product.name,
    description,
    alternates: {
      canonical: `/product/${slug}`,
      languages: {
        uk: `/product/${slug}`,
        'x-default': `/product/${slug}`,
      },
    },
  };
}

export default async function ProductPage({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}) {
  const { locale, slug } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);

  const tCatalog = await getTranslations({ locale, namespace: 'catalog' });
  const product = await getProduct(slug);
  if (!product) notFound();

  return (
    <ProductView
      product={product}
      catalogLabel={tCatalog('title')}
    />
  );
}

function ProductView({
  product,
  catalogLabel,
}: {
  product: any;
  catalogLabel: string;
}) {
  const t = useTranslations('product');
  const tProducts = useTranslations('products');

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <TrackViewedProduct productId={product.id} />
      <nav className="text-sm text-gray-500 mb-4">
        <Link href="/catalog" className="hover:text-blue-600">{catalogLabel}</Link>
        {product.breadcrumbs?.map((b: any, i: number) => (
          <span key={b.slug}> <span className="mx-1">›</span> <Link href={"/catalog/" + b.slug} className="hover:text-blue-600">{b.name}</Link></span>
        ))}
      </nav>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div>
          {product.images?.length > 0 ? (
            <img src={product.images[0].url} alt={product.name} className="w-full rounded-lg" />
          ) : (
            <div className="aspect-square bg-gray-100 rounded-lg flex items-center justify-center text-gray-400">{tProducts('noImage')}</div>
          )}
          {product.images?.length > 1 && (
            <div className="flex gap-2 mt-2 overflow-x-auto">
              {product.images.map((img: any) => (
                <img key={img.id} src={img.url} alt="" className="w-16 h-16 object-cover rounded border cursor-pointer hover:border-blue-500" />
              ))}
            </div>
          )}
        </div>

        <div>
          <h1 className="text-2xl font-bold mb-2">{product.name}</h1>
          {product.sku && <div className="text-sm text-gray-500 mb-2">{t('sku', { sku: product.sku })}</div>}
          {product.brand && <div className="text-sm text-gray-500 mb-2">{t('brand', { brand: product.brand })}</div>}

          <div className="my-4">
            <PriceDisplay price={product.price} oldPrice={product.old_price} variant="detail" />
          </div>

          <div className="mb-4">
            {product.stock_status === 'in_stock' ? (
              <span className="text-green-600 font-medium">{tProducts('inStock')}</span>
            ) : (
              <span className="text-red-600">{tProducts('outOfStock')}</span>
            )}
          </div>

          <AddToCartButton product={{
            id: product.id,
            name: product.name,
            slug: product.slug,
            sku: product.sku,
            price: product.price,
            old_price: product.old_price,
            image: product.images?.[0]?.url || '',
            stock_status: product.stock_status,
          }} />

          {product.attributes?.length > 0 && (
            <div className="mt-6 border-t pt-4">
              <h3 className="font-semibold mb-3">{t('specifications')}</h3>
              <table className="w-full text-sm">
                <tbody>
                  {product.attributes.map((attr: any) => (
                    <tr key={attr.id} className="border-b last:border-0">
                      <td className="py-2 pr-4 text-gray-600 font-medium">{attr.name}</td>
                      <td className="py-2">{attr.value}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {product.description && (
            <div className="mt-6 border-t pt-4">
              <h3 className="font-semibold mb-2">{t('description')}</h3>
              <div className="text-sm text-gray-700 whitespace-pre-wrap">{product.description.replace(/<[^>]+>/g, '')}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
