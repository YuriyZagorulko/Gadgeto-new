import Link from 'next/link';

export default function CatalogPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-6">Product Catalog</h1>

        <div className="flex gap-6">
          <div className="w-64 space-y-4">
            <div className="bg-white p-4 rounded-lg shadow">
              <h3 className="font-semibold mb-4">Categories</h3>
              <nav className="space-y-2">
                {['All Products', 'SSD Storage', 'RAM', 'Laptops', 'Monitors'].map((cat) => (
                  <Link key={cat} href="/catalog" className="block text-gray-600 hover:text-primary-600">
                    {cat}
                  </Link>
                ))}
              </nav>
            </div>
            <div className="bg-white p-4 rounded-lg shadow">
              <h3 className="font-semibold mb-4">Brands</h3>
              {['Samsung', 'Kingston', 'WD', 'Corsair'].map((brand) => (
                <label key={brand} className="flex items-center gap-2 mb-2">
                  <input type="checkbox" className="rounded" />
                  {brand}
                </label>
              ))}
            </div>
          </div>

          <div className="flex-1">
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
              {[1,2,3,4,5,6,7,8].map((i) => (
                <div key={i} className="bg-white rounded-lg overflow-hidden shadow hover:shadow-lg transition">
                  <div className="h-48 bg-gray-200 flex items-center justify-center">
                    <span className="text-gray-400">Product {i}</span>
                  </div>
                  <div className="p-4">
                    <h3 className="font-semibold mb-2">Samsung 990 PRO {i * 100}GB</h3>
                    <div className="text-gray-600 mb-2">NVMe SSD</div>
                    <div className="flex justify-between items-center">
                      <span className="font-bold text-primary-600">{(1000 + i * 100)} ₴</span>
                      <button className="bg-primary-600 text-white px-4 py-2 rounded hover:bg-primary-700">
                        Add to Cart
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
