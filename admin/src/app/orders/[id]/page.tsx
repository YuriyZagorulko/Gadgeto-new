'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { api } from '@/lib/api';
import {
  formatPrice, formatDateTime, ORDER_STATUSES, ORDER_STATUS_LABELS,
  PAYMENT_STATUS_LABELS, orderStatusTone,
} from '@/lib/format';
import { PageHeader, Button, Select, Table, Th, Td, Badge, LoadingState, ErrorState, ConfirmDialog, useToast } from '@/components/ui';

type Order = {
  id: number; number: string; user_id: number | null;
  buyer_name: string; email: string; phone: string;
  status: string; payment_status: string | null; payment_method: string | null;
  total_amount: number; subtotal_amount: number; shipping_amount: number;
  city_ref?: string | null; warehouse_number?: string | null; warehouse_ref?: string | null;
  area_name?: string | null; delivery_address?: string | null;
  notes?: string | null; ip_address?: string | null; created_at: string; updated_at?: string;
};
type Item = { id: number; product_id: number | null; product_name: string; product_sku: string | null; qty: number; price: number; total: number; product_slug: string | null };
type Event = { id: number; event: string; actor: string | null; payload: Record<string, unknown> | null; created_at: string };
type Payment = { id: number; payment_id: string; status: string; amount: number; currency: string; card_mask: string | null; card_type: string | null; created_at: string };
type Shipping = Record<string, string> | null;
type Detail = { order: Order; items: Item[]; events: Event[]; payments: Payment[]; shipping: Shipping };

export default function OrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const toast = useToast();
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState('');
  const [newStatus, setNewStatus] = useState('');
  const [confirmStatus, setConfirmStatus] = useState(false);
  const [saving, setSaving] = useState(false);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setError('');
    api.get<Detail>(`/orders/${id}`)
      .then((d) => { if (!cancelled) { setDetail(d); setNewStatus(d.order.status); } })
      .catch((e) => !cancelled && setError(e.message));
    return () => { cancelled = true; };
  }, [id, tick]);

  if (error) return <ErrorState message={error} />;
  if (!detail) return <LoadingState label="Завантаження замовлення..." />;

  const o = detail.order;

  const changeStatus = async () => {
    setSaving(true);
    try {
      await api.patch(`/orders/${o.id}/status`, { status: newStatus });
      toast.push('success', 'Статус замовлення змінено');
      setConfirmStatus(false);
      setTick((t) => t + 1);
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
      setConfirmStatus(false);
    } finally { setSaving(false); }
  };

  const shippingLines = detail.shipping
    ? Object.entries(detail.shipping).filter(([, v]) => v !== null && v !== undefined && v !== '')
    : [];

  return (
    <div>
      <PageHeader
        title={`Замовлення ${o.number}`}
        actions={
          <div className="flex gap-2 items-center">
            <Link href="/orders"><Button variant="secondary">До списку</Button></Link>
            {newStatus !== o.status && (
              <Button onClick={() => setConfirmStatus(true)}>Змінити статус</Button>
            )}
          </div>
        }
      />

      {/* Summary + status control */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <div className="text-xs text-gray-500 mb-1">Статус замовлення</div>
          <Badge tone={orderStatusTone(o.status)}>{ORDER_STATUS_LABELS[o.status] || o.status}</Badge>
          <div className="mt-3">
            <Select value={newStatus} onChange={(e) => setNewStatus(e.target.value)}>
              {ORDER_STATUSES.map((s) => <option key={s} value={s}>{ORDER_STATUS_LABELS[s]}</option>)}
            </Select>
            {newStatus === o.status && <p className="text-xs text-gray-400 mt-1">Оберіть інший статус для збереження.</p>}
          </div>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <div className="text-xs text-gray-500 mb-1">Оплата</div>
          <Badge tone={o.payment_status === 'paid' ? 'green' : 'gray'}>
            {PAYMENT_STATUS_LABELS[o.payment_status || ''] || o.payment_status || '—'}
          </Badge>
          <div className="text-sm text-gray-600 mt-2">{o.payment_method || 'Спосіб оплати не вказано'}</div>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <div className="text-xs text-gray-500 mb-1">Сума</div>
          <div className="text-xl font-bold">{formatPrice(o.total_amount)}</div>
          <div className="text-sm text-gray-500 mt-1">
            Товари: {formatPrice(o.subtotal_amount)} · Доставка: {formatPrice(o.shipping_amount)}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <div className="bg-white border border-gray-200 rounded-lg p-4 text-sm space-y-1">
          <h3 className="font-semibold mb-2">Покупець</h3>
          <div><span className="text-gray-500">Ім'я:</span> {o.buyer_name}</div>
          <div><span className="text-gray-500">Телефон:</span> {o.phone}</div>
          <div><span className="text-gray-500">Email:</span> {o.email}</div>
          <div><span className="text-gray-500">Створено:</span> {formatDateTime(o.created_at)}</div>
          {o.notes && <div><span className="text-gray-500">Примітка:</span> {o.notes}</div>}
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4 text-sm space-y-1">
          <h3 className="font-semibold mb-2">Доставка</h3>
          {shippingLines.length > 0 ? (
            shippingLines.map(([k, v]) => (
              <div key={k}><span className="text-gray-500">{k}:</span> {String(v)}</div>
            ))
          ) : (
            <>
              <div><span className="text-gray-500">Область:</span> {o.area_name || '—'}</div>
              <div><span className="text-gray-500">Місто (ref):</span> {o.city_ref || '—'}</div>
              <div><span className="text-gray-500">Відділення:</span> {o.warehouse_number || '—'}</div>
              <div><span className="text-gray-500">Адреса:</span> {o.delivery_address || '—'}</div>
            </>
          )}
        </div>
      </div>

      {/* Items */}
      <section className="mb-6">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">Склад замовлення</h3>
        <Table head={<tr><Th>Товар</Th><Th>Артикул</Th><Th>К-сть</Th><Th>Ціна</Th><Th>Сума</Th></tr>}>
          {detail.items.map((i) => (
            <tr key={i.id}>
              <Td>
                {i.product_slug
                  ? <Link href={`/products`} className="text-blue-600 hover:underline">{i.product_name}</Link>
                  : i.product_name}
              </Td>
              <Td className="text-xs text-gray-500">{i.product_sku || '—'}</Td>
              <Td>{i.qty}</Td>
              <Td className="whitespace-nowrap">{formatPrice(i.price)}</Td>
              <Td className="whitespace-nowrap font-medium">{formatPrice(i.total)}</Td>
            </tr>
          ))}
        </Table>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Payments */}
        <section>
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">Платежі</h3>
          {detail.payments.length === 0 ? (
            <p className="text-sm text-gray-400">Платежів немає.</p>
          ) : (
            <Table head={<tr><Th>Payment ID</Th><Th>Статус</Th><Th>Сума</Th><Th>Карта</Th><Th>Дата</Th></tr>}>
              {detail.payments.map((p) => (
                <tr key={p.id}>
                  <Td className="font-mono text-xs break-all max-w-[180px]">{p.payment_id}</Td>
                  <Td><Badge tone={p.status === 'success' || p.status === 'paid' ? 'green' : p.status === 'failure' || p.status === 'failed' ? 'red' : 'gray'}>{p.status}</Badge></Td>
                  <Td className="whitespace-nowrap">{formatPrice(p.amount)} {p.currency}</Td>
                  <Td className="text-xs">{p.card_mask || '—'}{p.card_type ? ` · ${p.card_type}` : ''}</Td>
                  <Td className="whitespace-nowrap text-xs text-gray-500">{formatDateTime(p.created_at)}</Td>
                </tr>
              ))}
            </Table>
          )}
        </section>

        {/* Events timeline */}
        <section>
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">Історія замовлення</h3>
          {detail.events.length === 0 ? (
            <p className="text-sm text-gray-400">Подій немає.</p>
          ) : (
            <ol className="relative border-l border-gray-200 ml-2 space-y-4">
              {detail.events.map((ev) => (
                <li key={ev.id} className="ml-4">
                  <span className="absolute -left-[5px] w-2.5 h-2.5 rounded-full bg-blue-500 mt-1" aria-hidden />
                  <div className="text-sm font-medium">{ev.event}</div>
                  <div className="text-xs text-gray-400">
                    {formatDateTime(ev.created_at)}
                    {ev.actor ? ` · ${ev.actor}` : ''}
                    {ev.payload ? ` · ${JSON.stringify(ev.payload)}` : ''}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>

      <ConfirmDialog
        open={confirmStatus}
        title="Змінити статус замовлення?"
        message={`Новий статус: ${ORDER_STATUS_LABELS[newStatus] || newStatus}. Зміна буде записана в історію замовлення.`}
        confirmLabel="Змінити статус" busy={saving}
        onConfirm={changeStatus} onCancel={() => setConfirmStatus(false)}
      />
    </div>
  );
}


