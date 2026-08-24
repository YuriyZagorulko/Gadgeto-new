'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from './AuthProvider';
import { LoadingState } from './ui';

type NavChild = { href: string; label: string };
type NavItem = {
  href?: string;
  label: string;
  icon: string;
  children?: NavChild[];
};

const navItems: NavItem[] = [
  { href: '/dashboard', label: 'Панель керування', icon: '📊' },
  { href: '/products', label: 'Товари', icon: '📦' },
  { href: '/media', label: 'Медіа', icon: '🖼️' },
  { href: '/categories', label: 'Категорії', icon: '📁' },
  { href: '/attributes', label: 'Атрибути', icon: '🏷️' },
  { href: '/brands', label: 'Бренди', icon: '™️' },
  { href: '/filters', label: 'Фільтри', icon: '🔽' },
  {
    label: 'Імпорт',
    icon: '📥',
    children: [
      { href: '/imports/mappings', label: 'Маппінг' },
      { href: '/imports/suppliers', label: 'Постачальники' },
    ],
  },
  { href: '/orders', label: 'Замовлення', icon: '🧾' },
  { href: '/users', label: 'Користувачі', icon: '👤' },
  {
    label: 'Налаштування',
    icon: '⚙️',
    children: [
      { href: '/settings/global-actions', label: 'Глобальні дії' },
    ],
  },
];

/** Routes that are reachable by URL but no longer have their own menu entry. */
const LEGACY_LABELS: Record<string, string> = {
  '/imports': 'Імпорт — історія завдань',
  '/settings': 'Налаштування',
};

function isActivePath(href: string, pathname: string): boolean {
  return pathname === href || pathname.startsWith(href + '/');
}

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
  // Collapsible menu groups (label → expanded). Groups whose child page is
  // active are expanded automatically (also on direct URL load / refresh).
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({});

  const isLoginPage = pathname === '/login';

  useEffect(() => {
    if (ready && !user && !isLoginPage) router.replace('/login');
  }, [ready, user, isLoginPage, router]);

  // Close the mobile menu on navigation.
  useEffect(() => setMenuOpen(false), [pathname]);

  // Keep the parent of the active child page expanded.
  useEffect(() => {
    const group = navItems.find((i) => i.children?.some((c) => isActivePath(c.href, pathname)));
    if (group) setOpenGroups((prev) => (prev[group.label] ? prev : { ...prev, [group.label]: true }));
  }, [pathname]);

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

  // Header label: prefer the most specific nav entry (children included),
  // falling back to legacy route labels.
  const flatNav = navItems.flatMap((i) =>
    i.children ? i.children.map((c) => c) : [{ href: i.href as string, label: i.label }],
  );
  const legacyLabel =
    Object.entries(LEGACY_LABELS)
      .sort((a, b) => b[0].length - a[0].length)
      .find(([href]) => isActivePath(href, pathname))?.[1];
  const activeLabel =
    [...flatNav].sort((a, b) => b.href.length - a.href.length).find((i) => isActivePath(i.href, pathname))?.label ||
    legacyLabel ||
    'Панель керування';

  const sidebar = (
    <nav className="flex-1 overflow-y-auto py-2" aria-label="Розділи адмінпанелі">
      {navItems.map((item) => {
        if (!item.children) {
          const active = isActivePath(item.href as string, pathname);
          return (
            <Link
              key={item.label}
              href={item.href as string}
              className={`flex items-center gap-3 px-5 py-2.5 text-sm transition-colors ${
                active ? 'bg-blue-600 text-white font-medium' : 'text-gray-300 hover:bg-gray-800 hover:text-white'
              }`}
            >
              <span className="text-base w-5 text-center">{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          );
        }

        // Expandable/collapsible group (e.g. Імпорт, Налаштування).
        const groupActive = item.children.some((c) => isActivePath(c.href, pathname));
        const open = !!openGroups[item.label];
        return (
          <div key={item.label}>
            <button
              type="button"
              onClick={() => setOpenGroups((prev) => ({ ...prev, [item.label]: !prev[item.label] }))}
              aria-expanded={open}
              className={`w-full flex items-center gap-3 px-5 py-2.5 text-sm transition-colors ${
                groupActive ? 'text-white' : 'text-gray-300'
              } hover:bg-gray-800 hover:text-white`}
            >
              <span className="text-base w-5 text-center">{item.icon}</span>
              <span className="flex-1 text-left">{item.label}</span>
              <span
                className={`text-[10px] text-gray-400 transition-transform ${open ? 'rotate-90' : ''}`}
                aria-hidden
              >
                ▶
              </span>
            </button>
            {open && (
              <div>
                {item.children.map((child) => {
                  const childActive = isActivePath(child.href, pathname);
                  return (
                    <Link
                      key={child.href}
                      href={child.href}
                      aria-current={childActive ? 'page' : undefined}
                      className={`flex items-center gap-3 pl-12 pr-5 py-2 text-sm transition-colors ${
                        childActive
                          ? 'bg-blue-600 text-white font-medium'
                          : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                      }`}
                    >
                      <span>{child.label}</span>
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
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
          <div className="p-4 md:p-6 max-w-8xl mx-auto">{children}</div>
        </main>
      </div>
    </div>
  );
}
