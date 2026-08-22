'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';
import { formatPrice, formatDateTime, orderStatusTone, importStatusTone } from '@/lib/format';
import { PageHeader, Table, Th, Td, Badge, LoadingState, ErrorState, EmptyState } from '@/components/ui';

type Stats = {
  products: { total: number; active: number; without_images: number; without_price: number; out_of_stock: number };
  catalog: { categories: number; brands: number; attributes: number };
  orders: { total: number; pending: number; processing: number; completed: number; cancelled: number };
  imports: { total: number; running: number; failed: number };
  revenue: number;
  recent_orders: Array<{ number: string; buyer_name: string; email: string; total_amount: number; status: string; payment_status: string; created_at: string }>;
  recent_imports: Array<{ id: number; status: string; import_type: string; started_at: string | null; finished_at: string | null; supplier_name: string | null }>;
};

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState('');
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setError('');
    api.get<Stats>('/dashboard/stats')
      .then((d) => { if (!cancelled) setStats(d); })
      .catch((e) => { if (!cancelled) setError(e.message); });
    return () => { cancelled = true; };
  }, [tick]);

  if (error) return <ErrorState message={error} onRetry={() => setTick((t) => t + 1)} />;
  if (!stats) return <LoadingState label="Завантаження статистики..." />;
/* PART2 */

  const productCards = [
    { label: 'Всього товарів', value: stats.products.total, href: '/products' },
    { label: 'Активні', value: stats.products.active, href: '/products?status=PUBLISHED' },
    { label: 'Без зображень', value: stats.products.without_images, href: '/products?no_image=1', warn: true },
    { label: 'Без ціни', value: stats.products.without_price, href: '/products?no_price=1', warn: true },
    { label: 'Немає в наявності', value: stats.products.out_of_stock, href: '/products?stock=out_of_stock' },
  ];
  const orderCards = [
    { label: 'Всього замовлень', value: stats.orders.total, href: '/orders' },
    { label: 'Очікують', value: stats.orders.pending, href: '/orders?status=PENDING' },
    { label: 'В обробці', value: stats.orders.processing, href: '/orders?status=PROCESSING' },
    { label: 'Виконані', value: stats.orders.completed, href: '/orders' },
    { label: 'Скасовані', value: stats.orders.cancelled, href: '/orders?status=CANCELLED' },
  ];

  return (
    <div>
      <PageHeader
        title="Панель керування"
        actions={
          <div className="bg-blue-50 border border-blue-200 rounded-md px-4 py-2 text-right">
            <div className="text-xs text-blue-700">Дохід (оплачені замовлення)</div>
            <div className="text-lg font-bold text-blue-800">{formatPrice(stats.revenue)}</div>
          </div>
        }
      />

      <StatSection title="Товари" cards={productCards} />
      <StatSection title="Замовлення" cards={orderCards} />

      <section className="mb-6">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">Каталог</h3>
        <div className="grid grid-cols-3 gap-3">
          <StatCard label="Категорії" value={stats.catalog.categories} href="/categories" />
          <StatCard label="Бренди" value={stats.catalog.brands} href="/brands" />
          <StatCard label="Атрибути" value={stats.catalog.attributes} href="/attributes" />
        </div>
      </section>

      <section className="mb-6">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">Імпорти</h3>
        <div className="grid grid-cols-3 gap-3">
          <StatCard label="Всього імпортів" value={stats.imports.total} href="/imports" />
          <StatCard label="Виконується / у черзі" value={stats.imports.running} href="/imports" />
          <StatCard label="З помилками" value={stats.imports.failed} href="/imports" warn />
        </div>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section>
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">Останні замовлення</h3>
          {stats.recent_orders.length === 0 ? (
            <EmptyState title="Замовлень ще немає" />
          ) : (
            <Table head={<tr><Th>Номер</Th><Th>Покупець</Th><Th>Сума</Th><Th>Статус</Th></tr>}>
              {stats.recent_orders.map((o) => (
                <tr key={o.number} className="hover:bg-gray-50">
                  <Td><Link href="/orders" className="font-medium text-blue-600 hover:underline">{o.number}</Link></Td>
                  <Td>{o.buyer_name}<div className="text-xs text-gray-400">{o.email}</div></Td>
                  <Td className="whitespace-nowrap">{formatPrice(o.total_amount)}</Td>
                  <Td><Badge tone={orderStatusTone(o.status)}>{o.status}</Badge></Td>
                </tr>
              ))}
            </Table>
          )}
        </section>

        <section>
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">Останні імпорти</h3>
          {stats.recent_imports.length === 0 ? (
            <EmptyState title="Імпортів ще не було" />
          ) : (
            <Table head={<tr><Th>ID</Th><Th>Постачальник</Th><Th>Тип</Th><Th>Статус</Th></tr>}>
              {stats.recent_imports.map((j) => (
                <tr key={j.id} className="hover:bg-gray-50">
                  <Td><Link href="/imports" className="text-blue-600 hover:underline">#{j.id}</Link></Td>
                  <Td>{j.supplier_name || '—'}</Td>
                  <Td>{j.import_type}</Td>
                  <Td><Badge tone={importStatusTone(j.status)}>{j.status}</Badge></Td>
                </tr>
              ))}
            </Table>
          )}
        </section>
      </div>
    </div>
  );
}

function StatSection({ title, cards }: { title: string; cards: Array<{ label: string; value: number; href?: string; warn?: boolean }> }) {
  return (
    <section className="mb-6">
      <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">{title}</h3>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {cards.map((c) => <StatCard key={c.label} {...c} />)}
      </div>
    </section>
  );
}

function StatCard({ label, value, href, warn }: { label: string; value: number; href?: string; warn?: boolean }) {
  const hot = warn && value > 0;
  const body = (
    <div className={`bg-white rounded-lg border p-4 transition ${hot ? 'border-red-200 bg-red-50/40' : 'border-gray-200'} ${href ? 'hover:border-blue-300 hover:shadow-sm' : ''}`}>
      <div className="text-xs text-gray-500">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${hot ? 'text-red-600' : 'text-gray-900'}`}>{value.toLocaleString('uk-UA')}</div>
    </div>
  );
  return href ? <Link href={href}>{body}</Link> : body;
}
