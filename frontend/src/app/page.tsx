import Link from 'next/link';

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Hero Section */}
      <section className="bg-gradient-to-r from-primary-600 to-primary-800 text-white py-20">
        <div className="container mx-auto px-4">
          <h1 className="text-4xl md:text-6xl font-bold mb-6">
            Computer Components & Gadgets Store
          </h1>
          <p className="text-xl mb-8 max-w-2xl">
            High-quality computer hardware, components, and accessories at competitive prices.
            Fast delivery across Ukraine.
          </p>
          <div className="flex gap-4">
            <Link href="/catalog" className="bg-white text-primary-700 px-6 py-3 rounded-lg font-semibold hover:bg-gray-100 transition">
              Shop Now
            </Link>
            <Link href="/catalog" className="bg-primary-700 text-white px-6 py-3 rounded-lg font-semibold hover:bg-primary-800 transition">
              View Catalog
            </Link>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-16 bg-white">
        <div className="container mx-auto px-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="text-center p-6">
              <div className="text-4xl mb-4">🚚</div>
              <h3 className="text-xl font-semibold mb-2">Fast Delivery</h3>
              <p className="text-gray-600">Nova Poshta delivery across Ukraine</p>
            </div>
            <div className="text-center p-6">
              <div className="text-4xl mb-4">💳</div>
              <h3 className="text-xl font-semibold mb-2">Secure Payment</h3>
              <p className="text-gray-600">LiqPay secure payment gateway</p>
            </div>
            <div className="text-center p-6">
              <div className="text-4xl mb-4">🛡️</div>
              <h3 className="text-xl font-semibold mb-2">Quality Guarantee</h3>
              <p className="text-gray-600">Original products with warranty</p>
            </div>
          </div>
        </div>
      </section>

      {/* Categories */}
      <section className="py-16 bg-gray-50">
        <div className="container mx-auto px-4">
          <h2 className="text-3xl font-bold mb-8 text-center">Shop by Category</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { name: 'SSD Storage', icon: '💾' },
              { name: 'RAM Memory', icon: '📊' },
              { name: 'Laptops', icon: '💻' },
              { name: 'Monitors', icon: '🖥️' },
              { name: 'Components', icon: '🔧' },
              { name: 'Peripherals', icon: '🖱️' },
              { name: 'Networking', icon: '📡' },
              { name: 'Power Supplies', icon: '🔋' },
            ].map((cat) => (
              <Link
                key={cat.name}
                href="/catalog"
                className="bg-white p-4 rounded-lg shadow hover:shadow-lg transition text-center"
              >
                <span className="text-3xl block mb-2">{cat.icon}</span>
                <span className="font-medium">{cat.name}</span>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Latest Products */}
      <section className="py-16 bg-white">
        <div className="container mx-auto px-4">
          <h2 className="text-3xl font-bold mb-8 text-center">Latest Products</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-6">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="bg-gray-50 rounded-lg overflow-hidden">
                <div className="h-48 bg-gray-200 flex items-center justify-center">
                  <span className="text-gray-400">Product Image</span>
                </div>
                <div className="p-4">
                  <h3 className="font-semibold mb-2">Product Name {i}</h3>
                  <div className="text-gray-600 mb-2">1 TB SSD Storage</div>
                  <div className="font-bold text-primary-600">1,500 ₴</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
