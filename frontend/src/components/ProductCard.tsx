import Link from 'next/link';

interface ProductCardProps {
  product: {
    id: number; sku?: string; name: string; slug: string;
    price: number; old_price?: number | null;
    stock_status?: string; image?: string; brand?: string; category?: string;
  };
}

export default function ProductCard({ product }: ProductCardProps) {
  const price = (product.price / 100).toLocaleString('uk-UA', { style: 'currency', currency: 'UAH' });
  const oldPrice = product.old_price ? (product.old_price / 100).toLocaleString('uk-UA', { style: 'currency', currency: 'UAH' }) : null;
  
  return (
    <Link href={`/product/${product.slug}`} className="card overflow-hidden group">
      <div className="aspect-square bg-gray-100 flex items-center justify-center overflow-hidden">
        {product.image ? (
          <img src={product.image} alt={product.name} className="w-full h-full object-cover group-hover:scale-105 transition" loading="lazy" />
        ) : (
          <span className="text-gray-400 text-sm">No image</span>
        )}
      </div>
      <div className="p-3">
        {product.brand && <div className="text-xs text-gray-500 mb-1">{product.brand}</div>}
        <h3 className="text-sm font-medium line-clamp-2 mb-2">{product.name}</h3>
        <div className="flex items-center gap-2">
          <span className="font-bold text-blue-700">{price}</span>
          {oldPrice && <span className="text-sm text-gray-400 line-through">{oldPrice}</span>}
        </div>
        {product.stock_status === 'out_of_stock' && (
          <span className="text-xs text-red-600">Out of stock</span>
        )}
      </div>
    </Link>
  );
}
