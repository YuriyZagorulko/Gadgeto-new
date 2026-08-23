'use client';
import { useState, useEffect } from 'react';
import { useTranslations } from 'next-intl';
import { Link } from '@/i18n/navigation';
import SearchBox from '@/components/SearchBox';

export default function Header() {
  const t = useTranslations('header');
  const [menuOpen, setMenuOpen] = useState(false);
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
          <SearchBox
            wrapperClassName="hidden md:flex items-center gap-2"
            formClassName="flex items-center"
            inputClassName="input-field w-48 lg:w-64 text-sm"
            placeholder={t('searchPlaceholder')}
          />
          <div className="flex items-center gap-3 sm:gap-4">
            {user ? (
              <Link href="/account" className="hidden sm:inline text-sm hover:text-blue-600">{t('account')}</Link>
            ) : (
              <Link href="/login" className="hidden sm:inline text-sm hover:text-blue-600">{t('signIn')}</Link>
            )}
            <Link href="/cart" className="relative text-sm hover:text-blue-600">
              {t('cart')} {cartCount > 0 && <span className="absolute -top-2 -right-2 bg-blue-600 text-white text-xs rounded-full w-4 h-4 flex items-center justify-center">{cartCount}</span>}
            </Link>
            <button className="md:hidden" onClick={() => setMenuOpen(!menuOpen)} aria-label={t('menu')}>☰</button>
          </div>
        </div>
        {menuOpen && (
          <div className="md:hidden pb-4 space-y-2">
            {categories.slice(0, 6).map((c: any) => (
              <Link key={c.slug} href={`/catalog/${c.slug}`} className="block px-2 py-1 hover:bg-gray-100 rounded">{c.name}</Link>
            ))}
            <SearchBox
              wrapperClassName="mt-2"
              formClassName="flex gap-2"
              inputClassName="input-field flex-1 text-sm"
              placeholder={t('searchPlaceholderMobile')}
            />
          </div>
        )}
      </div>
    </header>
  );
}
