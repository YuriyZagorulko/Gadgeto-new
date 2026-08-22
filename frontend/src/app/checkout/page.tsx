'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function CheckoutPage() {
  const router = useRouter();
  const [cart, setCart] = useState<any>(null);
  const [form, setForm] = useState({first_name:'',last_name:'',phone:'',email:'',city:'',branch:'',notes:''});
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetch('/api/cart').then(r=>r.json()).then(d=>setCart(d));
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault(); setError(''); setSubmitting(true);
    const token = localStorage.getItem('auth_token');
    try {
      const res = await fetch('/api/checkout', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({
          session_token: cart?.session_token||'',
          first_name: form.first_name, last_name: form.last_name,
          phone: form.phone, email: form.email,
          city_name: form.city, city_ref: form.city,
          warehouse_number: form.branch,
          auth_token: token||'',
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Checkout failed');
      localStorage.setItem('last_order', JSON.stringify(data));
      router.push('/checkout/success?order_id='+data.order_id);
    } catch (err:any) { setError(err.message); setSubmitting(false); }
  };

  if (!cart) return <div className="p-8 text-center">Loading...</div>;
  if (!cart.items?.length) return <div className="p-8 text-center">Cart is empty</div>;

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">Checkout</h1>
      <form onSubmit={handleSubmit} className="space-y-6">
        {error && <div className="bg-red-100 text-red-700 p-3 rounded text-sm">{error}</div>}
        <div className="card p-6 space-y-4">
          <h2 className="font-semibold">Customer Information</h2>
          <div className="grid grid-cols-2 gap-4">
            <div><label className="block text-sm font-medium mb-1">First Name</label><input type="text" value={form.first_name} onChange={e=>setForm({...form,first_name:e.target.value})} className="input-field" required /></div>
            <div><label className="block text-sm font-medium mb-1">Last Name</label><input type="text" value={form.last_name} onChange={e=>setForm({...form,last_name:e.target.value})} className="input-field" required /></div>
          </div>
          <div><label className="block text-sm font-medium mb-1">Phone</label><input type="tel" value={form.phone} onChange={e=>setForm({...form,phone:e.target.value})} className="input-field" required /></div>
          <div><label className="block text-sm font-medium mb-1">Email</label><input type="email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})} className="input-field" required /></div>
        </div>

        <div className="card p-6 space-y-4">
          <h2 className="font-semibold">Delivery (Nova Poshta)</h2>
          <div><label className="block text-sm font-medium mb-1">City</label><input type="text" value={form.city} onChange={e=>setForm({...form,city:e.target.value})} className="input-field" placeholder="Search city..." /></div>
          <div><label className="block text-sm font-medium mb-1">Branch / Post Office</label><input type="text" value={form.branch} onChange={e=>setForm({...form,branch:e.target.value})} className="input-field" placeholder="Branch number or address" /></div>
        </div>

        <div className="card p-4 text-right space-y-2">
          <div>Items: {cart.items.length}</div>
          <div className="text-xl font-bold">Total: {(cart.subtotal/100).toLocaleString()} ₴</div>
          <button type="submit" disabled={submitting} className="btn-primary w-full text-lg">{submitting ? 'Processing...' : 'Place Order'}</button>
        </div>
      </form>
    </div>
  );
}
