'use client';
import { Suspense, useEffect, useState } from 'react';
import { useTranslations } from 'next-intl';
import { useSearchParams } from 'next/navigation';
import { Link } from '@/i18n/navigation';
import { formatPrice } from '@/lib/format';
import { trackPurchaseOnce } from '@/lib/analytics';

function PurchaseTrigger({ order }: { order: any }) {
  const searchParams = useSearchParams();
  useEffect(() => {
    if (!order) return;
    // Fire purchase EXACTLY once per order — guarded by order ID, so
    // refresh / back-forward / revisits never duplicate the event.
    const urlOrderId = searchParams?.get('order_id');
    const orderId = order.order_id ?? urlOrderId;
    if (orderId && (order.total !== undefined || order.items)) {
      trackPurchaseOnce({
        transactionId: order.number || orderId,
        items: order.items || [],
        totalMinor: order.total || 0,
      });
    }
  }, [order, searchParams]);
  return null;
}

export default function SuccessPage() {
  const t = useTranslations('checkoutSuccess');
  const [order, setOrder] = useState<any>(null);
  useEffect(() => {
    const last = localStorage.getItem('last_order');
    if (last) setOrder(JSON.parse(last));
  }, []);

  return (
    <div className="max-w-md mx-auto px-4 py-12 text-center">
      <Suspense fallback={null}>
        <PurchaseTrigger order={order} />
      </Suspense>
      <div className="text-6xl mb-4">✅</div>
      <h1 className="text-2xl font-bold mb-4">{t('title')}</h1>
      {order && <div className="space-y-2 mb-6">
        <div className="text-lg">{t('orderNumber', { number: order.number })}</div>
        <div className="text-xl font-bold">{formatPrice(order.total, 'uk')}</div>
        <div className="text-sm text-gray-500">{t('status', { status: order.status })}</div>
      </div>}
      <div className="text-sm text-gray-500 mb-6">{t('note')}</div>
      <div className="flex gap-4 justify-center">
        <Link href="/catalog" className="btn-outline">{t('continueShopping')}</Link>
        <Link href="/account" className="btn-primary">{t('myOrders')}</Link>
      </div>
    </div>
  );
}
