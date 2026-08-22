'use client';
import { useState, useEffect } from 'react';
import Link from 'next/link';

export default function Header() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [searchQ, setSearchQ] = useState('');
  const [categories, setCategories] = useState<any[]>([]);
  const [cartCount, setCartCount] = useState(0);
  const [user, setUser] = useState<any>(null);

  useEffect(() => {
    fetch('/api/categories').then(r => r.json()).then(d => setCategories(d.items || [])).catch(() => {});
    const token = localStorage.getItem('auth_token');
    if (token) {
      fetch('/api/auth/me', { headers: { Authorization: `Bearer ${token}` } })
        .then(r => r.json()).then(d => setUser(d)).catch(() => {});
    }
    const cart = localStorage.getItem('cart');
    if (cart) {
      try { setCartCount(JSON.parse(cart).length || 0); } catch {}
    }
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQ.trim()) window.location.href = `/search?q=${encodeURIComponent(searchQ.trim())}`;
  };

  return (
    <header className="bg-white shadow-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <Link href="/" className="text-2xl font-bold text-blue-700">Gadgeto</Link>
          <nav className="hidden md:flex items-center gap-6 text-sm">
            {categories.slice(0, 6).map((c: any) => (
              <Link key={c.slug} href={`/catalog/${c.slug}`} className="hover:text-blue-600 transition">{c.name}</Link>
            ))}
          </nav>
          <form onSubmit={handleSearch} className="hidden md:flex items-center gap-2">
            <input type="search" value={searchQ} onChange={e => setSearchQ(e.target.value)}
              placeholder="Search products..." className="input-field w-48 lg:w-64 text-sm" />
          </form>
          <div className="flex items-center gap-4">
            {user ? (
              <Link href="/account" className="text-sm hover:text-blue-600">Account</Link>
            ) : (
              <Link href="/login" className="text-sm hover:text-blue-600">Sign In</Link>
            )}
            <Link href="/cart" className="relative text-sm hover:text-blue-600">
              Cart {cartCount > 0 && <span className="absolute -top-2 -right-2 bg-blue-600 text-white text-xs rounded-full w-4 h-4 flex items-center justify-center">{cartCount}</span>}
            </Link>
            <button className="md:hidden" onClick={() => setMenuOpen(!menuOpen)}>☰</button>
          </div>
        </div>
        {menuOpen && (
          <div className="md:hidden pb-4 space-y-2">
            {categories.slice(0, 6).map((c: any) => (
              <Link key={c.slug} href={`/catalog/${c.slug}`} className="block px-2 py-1 hover:bg-gray-100 rounded">{c.name}</Link>
            ))}
            <form onSubmit={handleSearch} className="flex gap-2 mt-2">
              <input type="search" value={searchQ} onChange={e => setSearchQ(e.target.value)}
                placeholder="Search..." className="input-field flex-1 text-sm" />
            </form>
          </div>
        )}
      </div>
    </header>
  );
}
