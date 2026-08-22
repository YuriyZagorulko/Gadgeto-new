'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { api, qs } from '@/lib/api';
import {
  formatPrice, formatDateTime, ORDER_STATUSES, ORDER_STATUS_LABELS,
  PAYMENT_STATUS_LABELS, orderStatusTone,
} from '@/lib/format';
import { PageHeader, Button, Input, Select, Table, Th, Td, Badge, Pagination, LoadingState, ErrorState, EmptyState } from '@/components/ui';

type Row = {
  id: number; number: string; buyer_name: string; email: string; phone: string;
  status: string; payment_status: string | null; payment_method: string | null;
  total_amount: number; shipping_amount: number; created_at: string; items_count: number;
};
type ListResp = { items: Row[]; total: number; page: number; per_page: number };

const PAYMENT_STATUSES = ['pending', 'paid', 'failed', 'refunded'];

export default function OrdersPage() {
  const [q, setQ] = useState('');
  const [appliedQ, setAppliedQ] = useState('');
  const [status, setStatus] = useState('');
  const [payment, setPayment] = useState('');
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ListResp | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError('');
    api.get<ListResp>('/orders' + qs({
      page, per_page: 20, q: appliedQ || undefined,
      status: status || undefined, payment_status: payment || undefined,
    }))
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [page, appliedQ, status, payment, tick]);

  return (
    <div>
      <PageHeader title="Замовлення" />

      <div className="bg-white border border-gray-200 rounded-lg p-3 mb-4 flex flex-wrap gap-3 items-end">
        <div className="w-64">
          <label className="block text-xs text-gray-500 mb-1">Пошук</label>
          <Input value={q} onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { setPage(1); setAppliedQ(q); } }}
            placeholder="Номер, ім'я, телефон або email..." />
        </div>
        <div className="w-48">
          <label className="block text-xs text-gray-500 mb-1">Статус замовлення</label>
          <Select value={status} onChange={(e) => { setPage(1); setStatus(e.target.value); }}>
            <option value="">Усі статуси</option>
            {ORDER_STATUSES.map((s) => <option key={s} value={s}>{ORDER_STATUS_LABELS[s]}</option>)}
          </Select>
        </div>
        <div className="w-44">
          <label className="block text-xs text-gray-500 mb-1">Оплата</label>
          <Select value={payment} onChange={(e) => { setPage(1); setPayment(e.target.value); }}>
            <option value="">Будь-яка</option>
            {PAYMENT_STATUSES.map((s) => <option key={s} value={s}>{PAYMENT_STATUS_LABELS[s]}</option>)}
          </Select>
        </div>
        <Button variant="secondary" onClick={() => { setPage(1); setAppliedQ(q); }}>Застосувати</Button>
        <Button variant="ghost" onClick={() => { setQ(''); setAppliedQ(''); setStatus(''); setPayment(''); setPage(1); }}>Скинути</Button>
      </div>

      {error && <ErrorState message={error} onRetry={() => setTick((t) => t + 1)} />}
      {!error && loading && !data && <LoadingState label="Завантаження замовлень..." />}
      {!error && data?.items.length === 0 && <EmptyState title="Замовлень не знайдено" />}
      {data && data.items.length > 0 && (
        <>
          <Table head={<tr><Th>Номер</Th><Th>Покупець</Th><Th>Телефон</Th><Th>Позицій</Th><Th>Сума</Th><Th>Статус</Th><Th>Оплата</Th><Th>Дата</Th></tr>}>
            {data.items.map((o) => (
              <tr key={o.id} className="hover:bg-gray-50">
                <Td>
                  <Link href={`/orders/${o.id}`} className="font-mono font-medium text-blue-600 hover:underline">{o.number}</Link>
                </Td>
                <Td>{o.buyer_name}<div className="text-xs text-gray-400">{o.email}</div></Td>
                <Td className="text-sm whitespace-nowrap">{o.phone}</Td>
                <Td>{o.items_count}</Td>
                <Td className="font-medium whitespace-nowrap">{formatPrice(o.total_amount)}</Td>
                <Td><Badge tone={orderStatusTone(o.status)}>{ORDER_STATUS_LABELS[o.status] || o.status}</Badge></Td>
                <Td>
                  <Badge tone={o.payment_status === 'paid' ? 'green' : o.payment_status === 'failed' ? 'red' : 'gray'}>
                    {PAYMENT_STATUS_LABELS[o.payment_status || ''] || o.payment_status || '—'}
                  </Badge>
                </Td>
                <Td className="whitespace-nowrap text-xs text-gray-500">{formatDateTime(o.created_at)}</Td>
              </tr>
            ))}
          </Table>
          <div className="mt-4">
            <Pagination page={data.page} pages={Math.max(1, Math.ceil(data.total / data.per_page))} total={data.total}
              onPage={(p) => setPage(p)} />
          </div>
        </>
      )}
    </div>
  );
}

