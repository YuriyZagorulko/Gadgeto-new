'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';

export default function SuccessPage() {
  const [order, setOrder] = useState<any>(null);
  useEffect(() => {
    const last = localStorage.getItem('last_order');
    if (last) setOrder(JSON.parse(last));
  }, []);

  return (
    <div className="max-w-md mx-auto px-4 py-12 text-center">
      <div className="text-6xl mb-4">✅</div>
      <h1 className="text-2xl font-bold mb-4">Order Placed!</h1>
      {order && <div className="space-y-2 mb-6">
        <div className="text-lg">Order #{order.number}</div>
        <div className="text-xl font-bold">{(order.total/100).toLocaleString()} ₴</div>
        <div className="text-sm text-gray-500">Status: {order.status}</div>
      </div>}
      <div className="text-sm text-gray-500 mb-6">We will contact you to confirm the order.</div>
      <div className="flex gap-4 justify-center">
        <Link href="/catalog" className="btn-outline">Continue Shopping</Link>
        <Link href="/account" className="btn-primary">My Orders</Link>
      </div>
    </div>
  );
}
