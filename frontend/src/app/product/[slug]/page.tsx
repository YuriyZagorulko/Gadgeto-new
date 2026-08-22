import Link from 'next/link';
import { notFound } from 'next/navigation';

async function getProduct(slug: string) {
  try {
    // Build URL via URL constructor for correct encoding
    const base = process.env.NEXT_PUBLIC_API_URL!.replace(/\/+$/, '');
    const url = new URL(`/api/v1/products/${slug}`, base).toString();
    const res = await fetch(url, { next: { revalidate: 60 } });
    if (!res.ok) return null;
    return res.json();
  } catch { return null; }
}

export default async function ProductPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const product = await getProduct(slug);
  if (!product) notFound();

  const price = (product.price / 100).toLocaleString('uk-UA', { style: 'currency', currency: 'UAH' });
  const oldPrice = product.old_price ? (product.old_price / 100).toLocaleString('uk-UA', { style: 'currency', currency: 'UAH' }) : null;

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <nav className="text-sm text-gray-500 mb-4">
        <Link href="/catalog" className="hover:text-blue-600">Catalog</Link>
        {product.breadcrumbs?.map((b: any, i: number) => (
          <span key={b.slug}> <span className="mx-1">›</span> <Link href={"/catalog/" + b.slug} className="hover:text-blue-600">{b.name}</Link></span>
        ))}
      </nav>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div>
          {product.images?.length > 0 ? (
            <img src={product.images[0].url} alt={product.name} className="w-full rounded-lg" />
          ) : (
            <div className="aspect-square bg-gray-100 rounded-lg flex items-center justify-center text-gray-400">No image</div>
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
          {product.sku && <div className="text-sm text-gray-500 mb-2">SKU: {product.sku}</div>}
          {product.brand && <div className="text-sm text-gray-500 mb-2">Brand: {product.brand}</div>}

          <div className="text-3xl font-bold text-blue-700 my-4">{price}</div>
          {oldPrice && <div className="text-lg text-gray-400 line-through">{oldPrice}</div>}

          <div className="mb-4">
            {product.stock_status === 'in_stock' ? (
              <span className="text-green-600 font-medium">In Stock</span>
            ) : (
              <span className="text-red-600">Out of Stock</span>
            )}
          </div>

          <button className="bg-blue-600 text-white w-full text-lg py-3 rounded-lg hover:bg-blue-700 transition font-medium">Add to Cart</button>

          {product.attributes?.length > 0 && (
            <div className="mt-6 border-t pt-4">
              <h3 className="font-semibold mb-3">Specifications</h3>
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
              <h3 className="font-semibold mb-2">Description</h3>
              <div className="text-sm text-gray-700 whitespace-pre-wrap">{product.description.replace(/<[^>]+>/g, '')}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
