'use client';

import { useTranslations } from 'next-intl';
import { Link } from '@/i18n/navigation';
import PriceDisplay from '@/components/PriceDisplay';
import AddToCartButton from '@/components/AddToCartButton';

interface ProductCardProps {
  product: {
    id: number; sku?: string; name: string; slug: string;
    price: number; old_price?: number | null;
    stock_status?: string; image?: string; brand?: string; category?: string;
  };
}

export default function ProductCard({ product }: ProductCardProps) {
  const t = useTranslations('products');

  return (
    <div className="card overflow-hidden group relative flex flex-col">
      <Link href={`/product/${product.slug}`} className="block">
        <div className="aspect-square bg-gray-100 flex items-center justify-center overflow-hidden">
          {product.image ? (
            <img src={product.image} alt={product.name} className="w-full h-full object-cover group-hover:scale-105 transition" loading="lazy" />
          ) : (
            <span className="text-gray-400 text-sm">{t('noImage')}</span>
          )}
        </div>
        <div className="p-3">
          {product.brand && <div className="text-xs text-gray-500 mb-1">{product.brand}</div>}
          <h3 className="text-sm font-medium line-clamp-2 mb-2">{product.name}</h3>
          <div className="flex items-center gap-2">
            <PriceDisplay price={product.price} oldPrice={product.old_price} variant="card" />
          </div>
          {product.stock_status === 'out_of_stock' && (
            <span className="text-xs text-red-600">{t('outOfStock')}</span>
          )}
        </div>
      </Link>
      <div className="px-3 pb-3 mt-auto">
        <AddToCartButton
          product={{
            id: product.id,
            name: product.name,
            slug: product.slug,
            sku: product.sku,
            price: product.price,
            old_price: product.old_price,
            image: product.image,
            stock_status: product.stock_status,
          }}
          className="w-full text-sm py-2"
        />
      </div>
    </div>
  );
}
