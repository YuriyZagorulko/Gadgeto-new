'use client';
import { useEffect, useState } from 'react';
import { useTranslations } from 'next-intl';
import { Link } from '@/i18n/navigation';
import { formatPrice } from '@/lib/format';

export default function SuccessPage() {
  const t = useTranslations('checkoutSuccess');
  const [order, setOrder] = useState<any>(null);
  useEffect(() => {
    const last = localStorage.getItem('last_order');
    if (last) setOrder(JSON.parse(last));
  }, []);

  return (
    <div className="max-w-md mx-auto px-4 py-12 text-center">
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
