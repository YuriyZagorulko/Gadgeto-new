'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from './AuthProvider';
import { LoadingState } from './ui';

const navItems = [
  { href: '/dashboard', label: 'Панель керування', icon: '📊' },
  { href: '/products', label: 'Товари', icon: '📦' },
  { href: '/categories', label: 'Категорії', icon: '📁' },
  { href: '/attributes', label: 'Атрибути', icon: '🏷️' },
  { href: '/brands', label: 'Бренди', icon: '™️' },
  { href: '/suppliers', label: 'Постачальники', icon: '🚚' },
  { href: '/filters', label: 'Фільтри', icon: '🔽' },
  { href: '/mappings', label: 'Відповідності', icon: '🔗' },
  { href: '/imports', label: 'Імпорти', icon: '📥' },
  { href: '/orders', label: 'Замовлення', icon: '🧾' },
  { href: '/users', label: 'Користувачі', icon: '👤' },
  { href: '/settings', label: 'Налаштування', icon: '⚙️' },
];

/**
 * Authenticated application shell: responsive sidebar, header with the
 * current user and logout. The login route renders without the shell.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, ready, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [menuOpen, setMenuOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);

  const isLoginPage = pathname === '/login';

  useEffect(() => {
    if (ready && !user && !isLoginPage) router.replace('/login');
  }, [ready, user, isLoginPage, router]);

  // Close the mobile menu on navigation.
  useEffect(() => setMenuOpen(false), [pathname]);

  if (!ready) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <LoadingState label="Перевірка сесії..." />
      </div>
    );
  }

  if (isLoginPage) return <>{children}</>;

  if (!user) return null; // redirecting to /login

  const handleLogout = async () => {
    setLoggingOut(true);
    await logout();
  };

  const activeLabel =
    [...navItems].sort((a, b) => b.href.length - a.href.length).find((i) => pathname.startsWith(i.href))?.label ||
    'Панель керування';

  const sidebar = (
    <nav className="flex-1 overflow-y-auto py-2" aria-label="Розділи адмінпанелі">
      {navItems.map((item) => {
        const active = pathname === item.href || pathname.startsWith(item.href + '/');
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`flex items-center gap-3 px-5 py-2.5 text-sm transition-colors ${
              active ? 'bg-blue-600 text-white font-medium' : 'text-gray-300 hover:bg-gray-800 hover:text-white'
            }`}
          >
            <span className="text-base w-5 text-center">{item.icon}</span>
            <span>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );

  return (
    <div className="flex h-screen bg-gray-100">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex bg-gray-900 text-white w-60 flex-col flex-shrink-0">
        <div className="px-5 py-4 border-b border-gray-700">
          <Link href="/dashboard" className="font-bold text-lg tracking-tight">
            Gadgeto <span className="text-blue-400">Admin</span>
          </Link>
        </div>
        {sidebar}
        <div className="px-5 py-3 border-t border-gray-700 text-xs text-gray-400">
          <div className="font-medium text-gray-200 truncate">{user.full_name || user.email}</div>
          <div className="truncate">{user.email}</div>
          <div className="mt-1 inline-block bg-gray-800 rounded px-1.5 py-0.5 uppercase tracking-wide">{user.role}</div>
        </div>
      </aside>

      {/* Mobile sidebar overlay */}
      {menuOpen && (
        <div className="md:hidden fixed inset-0 z-40 flex">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMenuOpen(false)} aria-hidden />
          <aside className="relative bg-gray-900 text-white w-64 flex flex-col">
            <div className="px-5 py-4 border-b border-gray-700 flex justify-between items-center">
              <span className="font-bold text-lg">Gadgeto Admin</span>
              <button onClick={() => setMenuOpen(false)} aria-label="Закрити меню" className="text-gray-400 hover:text-white text-xl leading-none">×</button>
            </div>
            {sidebar}
          </aside>
        </div>
      )}

      {/* Main area */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="bg-white border-b border-gray-200 h-14 flex items-center gap-3 px-4 md:px-6 flex-shrink-0">
          <button
            className="md:hidden text-gray-500 hover:text-gray-800 text-xl"
            onClick={() => setMenuOpen(true)}
            aria-label="Відкрити меню"
          >
            ☰
          </button>
          <h1 className="text-sm font-semibold text-gray-500 hidden sm:block">{activeLabel}</h1>
          <div className="ml-auto flex items-center gap-3">
            <span className="text-sm text-gray-600 hidden lg:block truncate max-w-[220px]">
              {user.full_name || user.email}
            </span>
            <button
              onClick={handleLogout}
              disabled={loggingOut}
              className="text-sm text-red-600 hover:text-red-700 font-medium disabled:opacity-50"
            >
              {loggingOut ? 'Вихід...' : 'Вийти'}
            </button>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto">
          <div className="p-4 md:p-6 max-w-7xl mx-auto">{children}</div>
        </main>
      </div>
    </div>
  );
}
