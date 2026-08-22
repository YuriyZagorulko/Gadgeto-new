'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({email:'',password:'',confirm:'',full_name:'',phone:''});
  const [error, setError] = useState('');

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault(); setError('');
    if (form.password !== form.confirm) { setError('Passwords do not match'); return; }
    if (form.password.length < 6) { setError('Password must be at least 6 characters'); return; }
    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email:form.email, password:form.password, full_name:form.full_name, phone:form.phone }),
      });
      if (!res.ok) { const d = await res.json(); throw new Error(d.detail||'Registration failed'); }
      const data = await res.json();
      localStorage.setItem('auth_token', data.access_token);
      router.push('/account');
    } catch (err:any) { setError(err.message); }
  };

  return (
    <div className="max-w-md mx-auto px-4 py-12">
      <h1 className="text-2xl font-bold mb-6 text-center">Create Account</h1>
      <form onSubmit={handleRegister} className="card p-6 space-y-4">
        {error && <div className="bg-red-100 text-red-700 p-3 rounded text-sm">{error}</div>}
        <div><label className="block text-sm font-medium mb-1">Full Name</label><input type="text" value={form.full_name} onChange={e=>setForm({...form,full_name:e.target.value})} className="input-field" required /></div>
        <div><label className="block text-sm font-medium mb-1">Email</label><input type="email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})} className="input-field" required /></div>
        <div><label className="block text-sm font-medium mb-1">Phone</label><input type="tel" value={form.phone} onChange={e=>setForm({...form,phone:e.target.value})} className="input-field" /></div>
        <div><label className="block text-sm font-medium mb-1">Password</label><input type="password" value={form.password} onChange={e=>setForm({...form,password:e.target.value})} className="input-field" required /></div>
        <div><label className="block text-sm font-medium mb-1">Confirm Password</label><input type="password" value={form.confirm} onChange={e=>setForm({...form,confirm:e.target.value})} className="input-field" required /></div>
        <button type="submit" className="btn-primary w-full">Create Account</button>
      </form>
    </div>
  );
}
