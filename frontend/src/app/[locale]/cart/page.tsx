'use client';
import { useEffect, useState } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { Link } from '@/i18n/navigation';
import { formatPrice } from '@/lib/format';

export default function CartPage() {
  const t = useTranslations('cart');
  const locale = useLocale();
  const [cart, setCart] = useState<any>(null);
  
  const load = async () => {
    const res = await fetch('/api/cart');
    setCart(await res.json());
  };
  useEffect(() => { load(); }, []);

  const updateQty = async (id: number, qty: number) => {
    await fetch('/api/cart/items/'+id, { method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({qty}) });
    load();
  };
  const remove = async (id: number) => {
    await fetch('/api/cart/items/'+id, { method:'DELETE' });
    load();
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">{t('title')}</h1>
      {!cart?.items?.length ? (
        <div className="text-center py-12"><p className="text-gray-500 mb-4">{t('empty')}</p><Link href="/catalog" className="btn-primary inline-block">{t('continueShopping')}</Link></div>
      ) : (
        <div className="space-y-4">
          {cart.items.map((item:any) => (
            <div key={item.id} className="card p-4 flex items-center gap-4">
              {item.image ? <img src={item.image} alt={item.name} className="w-20 h-20 object-cover rounded" /> : <div className="w-20 h-20 bg-gray-100 rounded flex items-center justify-center text-xs text-gray-400">{t('noImage')}</div>}
              <div className="flex-1">
                <Link href={'/product/' + item.sku} className="font-medium hover:text-blue-600">{item.name}</Link>
                <div className="text-sm text-gray-500">{t('sku', { sku: item.sku })}</div>
              </div>
              <div className="text-right">
                <div className="font-medium">{formatPrice(item.price_at_addition || 0, locale)}</div>
                <div className="flex items-center gap-2 mt-2">
                  <button onClick={() => updateQty(item.id, Math.max(1, item.qty-1))} className="px-2 py-1 border rounded text-sm">-</button>
                  <span className="w-8 text-center">{item.qty}</span>
                  <button onClick={() => updateQty(item.id, item.qty+1)} className="px-2 py-1 border rounded text-sm">+</button>
                </div>
                <button onClick={() => remove(item.id)} className="text-sm text-red-600 mt-1">{t('remove')}</button>
              </div>
            </div>
          ))}
          <div className="card p-4 text-right">
            <div className="text-xl font-bold">{t('total', { total: formatPrice(cart.subtotal, locale) })}</div>
            <Link href="/checkout" className="btn-primary mt-4 inline-block">{t('proceedToCheckout')}</Link>
          </div>
        </div>
      )}
    </div>
  );
}
