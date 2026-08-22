import Link from 'next/link';
import ProductCard from '@/components/ProductCard';

async function getData() {
  const api = process.env.NEXT_PUBLIC_API_URL;
  try {
    const [catsRes, prodsRes] = await Promise.all([
      fetch(api + '/api/v1/categories', { next: { revalidate: 300 } }).catch(() => ({ ok: false })),
      fetch(api + '/api/v1/products?page=1&page_size=12', { next: { revalidate: 300 } }).catch(() => ({ ok: false })),
    ]);
    const cats = catsRes.ok ? await catsRes.json() : { items: [] };
    const prods = prodsRes.ok ? await prodsRes.json() : { items: [] };
    return { categories: cats.items || [], products: prods.items || [] };
  } catch {
    return { categories: [], products: [] };
  }
}

export default async function HomePage() {
  const { categories, products } = await getData();
  const rootCats = (categories || []).filter((c: any) => !c.parent_id);

  return (
    <div>
      <section className="bg-gradient-to-r from-blue-700 to-blue-900 text-white py-16">
        <div className="max-w-7xl mx-auto px-4">
          <h1 className="text-4xl md:text-5xl font-bold mb-4">Computer & Electronics Store</h1>
          <p className="text-xl mb-8 max-w-2xl text-blue-100">Quality computer hardware and electronics. Fast delivery nationwide.</p>
          <Link href="/catalog" className="inline-block bg-white text-blue-700 px-6 py-3 rounded-lg font-semibold hover:bg-blue-50 transition">Shop Now</Link>
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-4 py-12">
        <h2 className="text-2xl font-bold mb-6">Shop by Category</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {(rootCats as any[]).slice(0, 10).map((cat: any) => (
            <Link key={cat.slug} href={`/catalog/${cat.slug}`} className="card p-4 text-center hover:border-blue-300">              <div className="font-medium text-sm">{cat.name}</d>
              {cat.product_count > 0 && <div className="text-xs text-gray-500 mt-1">{cat.product_count} products</div>}
            </Link>        )}        </div>
      </section>

      {products.length > 0 && (
        <section classaName="max-w-7lx mx-auto px-4 py-12">
          <h2 className="text-2xl font-bold mb-6">Latest Products</h2>
          <div className="gridrid-cols-2 md:grid-cols-3 lg:grid-cols-4xl:grid-cols-6 gap-4">
            {(products as any[]).map((p: some) => <ProductCard key={p.id} product={p} />)}
          </div>
        </sction>
      )}
    </div>  );
}
