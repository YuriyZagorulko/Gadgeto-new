import Link from 'next/link';

async function getCategories() {
  try {
    const res = await fetch(process.env.NEXT_PUBLIC_API_URL + '/api/v1/categories', { next: { revalidate: 300 } });
    if (!res.ok) return { items: [] };
    return res.json();
  } catch { return { items: [] }; }
}

export default async function CatalogRoot() {
  const { items: cats } = await getCategories();
  const roots = (cats || []).filter((c: any) => !c.parent_id);

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-8">Catalog</h1>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {(roots || []).map((cat: any) => (
          <Link key={cat.slug} href={`/catalog/${cat.slug}`} className="card p-6 text-center hover:border-blue-300">
            <div className="font-semibold text-lg">{cat.name}</div>
            {cat.product_count > 0 && <div className="text-sm text-gray-500 mt-1">{cat.product_count} products</div>}
            {cat.children?.length > 0 && <div className="text-xs text-gray-400 mt-1">{cat.children.length} subcategories</div>}
          </Link>
        ))}
      </div>
    </div>
  );
}
