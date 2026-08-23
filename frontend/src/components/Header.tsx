'use client';
import { useState, useEffect, useCallback } from 'react';
import { useTranslations } from 'next-intl';
import { Link, usePathname } from '@/i18n/navigation';
import SearchBox from '@/components/SearchBox';
import CartModal from '@/components/CartModal';
import { useCartStore, useCartTotalItems } from '@/lib/cart-store';

export default function Header() {
  const t = useTranslations('header');
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const [categories, setCategories] = useState<any[]>([]);
  const [user, setUser] = useState<any>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const initSession = useCartStore((s) => s.initSession);
  const refreshFromAPI = useCartStore((s) => s.refreshFromAPI);
  const cartCount = useCartTotalItems();
  const cartModalOpen = useCartStore((s) => s.cartModalOpen);
  const openCartModal = useCartStore((s) => s.openCartModal);
  const closeCartModal = useCartStore((s) => s.closeCartModal);

  const fetchUser = useCallback(() => {
    const token = localStorage.getItem('auth_token');
    if (!token) {
      setUser(null);
      setAuthLoading(false);
      return;
    }
    setAuthLoading(true);
    fetch('/api/auth/me', { headers: { Authorization: `Bearer ${token}` } })
      .then(r => {
        if (!r.ok) {
          // Token invalid/expired — clean up
          localStorage.removeItem('auth_token');
          setUser(null);
          return null;
        }
        return r.json();
      })
      .then(d => {
        if (d) setUser(d);
      })
      .catch(() => {
        // Network error — keep current user state to avoid flash
      })
      .finally(() => {
        setAuthLoading(false);
      });
  }, []);

  useEffect(() => {
    fetch('/api/categories').then(r => r.json()).then(d => setCategories(d.items || [])).catch(() => {});
    fetchUser();

    // Initialise cart session and sync with backend
    initSession();
    refreshFromAPI().catch(() => {});
  }, [fetchUser, initSession, refreshFromAPI, pathname]);

  // Listen for auth changes (login in another tab, custom auth events)
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === 'auth_token') {
        fetchUser();
      }
    };
    const onFocus = () => {
      fetchUser();
    };
    window.addEventListener('storage', onStorage);
    window.addEventListener('focus', onFocus);
    return () => {
      window.removeEventListener('storage', onStorage);
      window.removeEventListener('focus', onFocus);
    };
  }, [fetchUser]);

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
              {authLoading ? null : user ? (
                <Link href="/account" className="hidden sm:inline-flex items-center hover:text-blue-600 p-1.5 rounded-lg">
                  <svg className="h-6 w-6 text-gray-700" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
                    <circle cx="12" cy="7" r="4" />
                  </svg>
                </Link>
              ) : (
                <Link href="/login" className="hidden sm:inline-flex items-center hover:text-blue-600 p-1.5 rounded-lg" aria-label={t('signIn')}>
                  <svg className="h-6 w-6 text-gray-700" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
                    <circle cx="12" cy="7" r="4" />
                  </svg>
                </Link>
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
