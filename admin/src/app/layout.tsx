'use client';
import React, { useState } from 'react';
import './globals.css';

const navItems = [
  { href: '/dashboard', label: 'Dashboard', icon: '📊' },
  { href: '/products', label: 'Products', icon: '📦' },
  { href: '/categories', label: 'Categories', icon: '📁' },
  { href: '/attributes', label: 'Attributes', icon: '🏷️' },
  { href: '/brands', label: 'Brands', icon: '®️' },
  { href: '/suppliers', label: 'Suppliers', icon: '🚚' },
  { href: '/filters', label: 'Filters', icon: '🔍' },
  { href: '/mappings', label: 'Mappings', icon: '🔗' },
  { href: '/imports', label: 'Imports', icon: '📥' },
  { href: '/orders', label: 'Orders', icon: '📋' },
  { href: '/users', label: 'Users', icon: '👤' },
  { href: '/settings', label: 'Settings', icon: '⚙️' },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [user] = useState({ name: 'Admin', email: 'admin@gadgeto.com.ua' });

  return (
    <html lang="uk">
      <body>
        <div className="flex h-screen bg-gray-100">
          {/* Sidebar */}
          <aside className={`bg-gray-900 text-white ${collapsed ? 'w-16' : 'w-64'} transition-all duration-200 flex flex-col`}>
            <div className="p-4 border-b border-gray-700 flex items-center justify-between">
              {!collapsed && <span className="font-bold text-lg">Gadgeto Admin</span>}
              <button onClick={() => setCollapsed(!collapsed)} className="text-gray-400 hover:text-white">
                {collapsed ? '☰' : '✕'}
              </button>
            </div>
            <nav className="flex-1 overflow-y-auto py-2">
              {navItems.map((item) => (
                <a
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-3 px-4 py-3 hover:bg-gray-800 transition-colors ${collapsed ? 'justify-center' : ''}`}
                >
                  <span className="text-lg">{item.icon}</span>
                  {!collapsed && <span>{item.label}</span>}
                </a>
              ))}
            </nav>
            <div className="p-4 border-t border-gray-700">
              {!collapsed && (
                <div className="text-sm">
                  <div className="font-medium">{user.name}</div>
                  <div className="text-gray-400 text-xs">{user.email}</div>
                </div>
              )}
            </div>
          </aside>

          {/* Main content */}
          <main className="flex-1 overflow-y-auto bg-gray-50">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
