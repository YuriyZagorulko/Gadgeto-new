export default function Footer() {
  return (
    <footer className="bg-gray-800 text-gray-300 py-8 mt-auto">
      <div className="max-w-7xl mx-auto px-4 grid grid-cols-1 md:grid-cols-3 gap-8">
        <div>
          <h3 className="text-white font-bold mb-3">Gadgeto</h3>
          <p className="text-sm">Computer & electronics store in Ukraine. Quality products, fast delivery.</p>
        </div>
        <div>
          <h3 className="text-white font-bold mb-3">Information</h3>
          <ul className="text-sm space-y-1">
            <li><a href="/catalog" className="hover:text-white">Catalog</a></li>
            <li><a href="/search" className="hover:text-white">Search</a></li>
            <li><a href="/cart" className="hover:text-white">Cart</a></li>
          </ul>
        </div>
        <div>
          <h3 className="text-white font-bold mb-3">Contact</h3>
          <p className="text-sm">Dnipro, Ukraine</p>
          <p className="text-sm">Nova Poshta delivery</p>
        </div>
      </div>
      <div className="border-t border-gray-700 mt-6 pt-4 text-center text-sm">
        &copy; 2026 Gadgeto. All rights reserved.
      </div>
    </footer>
  );
}
