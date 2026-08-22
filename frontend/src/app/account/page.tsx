'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

export default function AccountPage() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [orders, setOrders] = useState<any[]>([]);
  const [tab, setTab] = useState('profile');

  useEffect(() => {
    const token = localStorage.getItem('auth_token');
    if (!token) { router.push('/login'); return; }
    fetch('/api/auth/me', { headers: { Authorization: 'Bearer ' + token } })
      .then(r => r.json()).then(setUser).catch(() => router.push('/login'));
    fetch('/api/orders', { headers: { Authorization: 'Bearer ' + token } })
      .then(r => r.json()).then(d => setOrders(d.items || [])).catch(() => {});
  }, []);

  const logout = () => { localStorage.removeItem('auth_token'); router.push('/'); };

  if (!user) return <div className="p-8 text-center">Loading...</div>;

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">My Account</h1>
      <div className="flex gap-4 mb-6 border-b pb-2">
        <button onClick={() => setTab('profile')} className={`pb-2 ${tab==='profile'?'border-b-2 border-blue-600 font-medium':'text-gray-500'}`}>Profile</button>
        <button onClick={() => setTab('orders')} className={`pb-2 ${tab==='orders'?'border-b-2 border-blue-600 font-medium':'text-gray-500'}`}>Orders</button>
        <button onClick={logout} className="pb-2 text-red-600 ml-auto">Logout</button>
      </div>
      {tab=='profile' && <div className="card p-6"><p><strong>Name:</strong> {user.full_name}</p><p><strong>Email:</strong> {user.email}</p><p><strong>Phone:</strong> {user.phone || '-'}</p></div>}
      {tab=='orders' && <div className="space-y-3">{(orders||[]).map((o:any)=>(
        <div key={o.id} className="card p-4 flex justify-between">
          <div>#{o.number}<div className="text-sm text-gray-500">{new Date(o.created_at).toLocaleDateString()}</div></div>
          <div className="text-right"><div className="font-medium">{(o.total_amount/100).toLocaleString()}</div><div className="text-sm">{o.status}</div></div>
        </div>
      ))}{orders.length===0 && <p className="text-gray-500">No orders yet.</p>}</div>}
    </div>
  );
}
