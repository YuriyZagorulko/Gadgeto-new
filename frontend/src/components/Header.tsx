'use client';
import { useState, useEffect } from 'react';
import { useTranslations } from 'next-intl';
import { Link } from '@/i18n/navigation';
import SearchBox from '@/components/SearchBox';
import CartModal from '@/components/CartModal';
import { useCartStore, useCartTotalItems } from '@/lib/cart-store';

export default function Header() {
  const t = useTranslations('header');
  const [menuOpen, setMenuOpen] = useState(false);
  const [categories, setCategories] = useState<any[]>([]);
  const [user, setUser] = useState<any>(null);
  const initSession = useCartStore((s) => s.initSession);
  const refreshFromAPI = useCartStore((s) => s.refreshFromAPI);
  const cartCount = useCartTotalItems();
  const cartModalOpen = useCartStore((s) => s.cartModalOpen);
  const openCartModal = useCartStore((s) => s.openCartModal);
  const closeCartModal = useCartStore((s) => s.closeCartModal);

  useEffect(() => {
    fetch('/api/categories').then(r => r.json()).then(d => setCategories(d.items || [])).catch(() => {});
    const token = localStorage.getItem('auth_token');
    if (token) {
      fetch('/api/auth/me', { headers: { Authorization: `Bearer ${token}` } })
        .then(r => r.json()).then(d => setUser(d)).catch(() => {});
    }
    // Initialise cart session and sync with backend
    initSession();
    refreshFromAPI().catch(() => {});
  }, [initSession, refreshFromAPI]);

  return (
    <>
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
              <button
                onClick={openCartModal}
                className="relative p-1.5 rounded-lg hover:bg-gray-100 transition"
                aria-label={t('cart')}
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-gray-700" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="9" cy="21" r="1" />
                  <circle cx="20" cy="21" r="1" />
                  <path d="M1 1h4l2.68 13.39a2 2 0 002 1.61h9.72a2 2 0 002-1.61L23 6H6" />
                </svg>
                {cartCount > 0 && (
                  <span className="absolute -top-1 -right-1 bg-blue-600 text-white text-[10px] font-bold rounded-full min-w-[18px] h-[18px] flex items-center justify-center px-1 shadow-sm">
                    {cartCount > 99 ? '99+' : cartCount}
                  </span>
                )}
              </button>
              <button className="md:hidden p-1.5" onClick={() => setMenuOpen(!menuOpen)} aria-label={t('menu')}>
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-gray-700" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="3" y1="6" x2="21" y2="6" />
                  <line x1="3" y1="12" x2="21" y2="12" />
                  <line x1="3" y1="18" x2="21" y2="18" />
                </svg>
              </button>
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

      <CartModal open={cartModalOpen} onClose={closeCartModal} />
    </>
  );
}
