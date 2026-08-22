'use client';
import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Link, useRouter } from '@/i18n/navigation';

export default function RegisterPage() {
  const t = useTranslations('auth');
  const router = useRouter();
  const [form, setForm] = useState({email:'',password:'',confirm:'',full_name:'',phone:''});
  const [error, setError] = useState('');

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault(); setError('');
    if (form.password !== form.confirm) { setError(t('errorPasswordMismatch')); return; }
    if (form.password.length < 6) { setError(t('errorPasswordLength')); return; }
    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email:form.email, password:form.password, full_name:form.full_name, phone:form.phone }),
      });
      if (!res.ok) throw new Error(t('errorRegistrationFailed'));
      const data = await res.json();
      localStorage.setItem('auth_token', data.access_token);
      router.push('/account');
    } catch (err:any) { setError(err.message); }
  };

  return (
    <div className="max-w-md mx-auto px-4 py-12">
      <h1 className="text-2xl font-bold mb-6 text-center">{t('registerTitle')}</h1>
      <form onSubmit={handleRegister} className="card p-6 space-y-4">
        {error && <div className="bg-red-100 text-red-700 p-3 rounded text-sm">{error}</div>}
        <div><label className="block text-sm font-medium mb-1">{t('fullName')}</label><input type="text" value={form.full_name} onChange={e=>setForm({...form,full_name:e.target.value})} className="input-field" required /></div>
        <div><label className="block text-sm font-medium mb-1">{t('email')}</label><input type="email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})} className="input-field" required /></div>
        <div><label className="block text-sm font-medium mb-1">{t('phone')}</label><input type="tel" value={form.phone} onChange={e=>setForm({...form,phone:e.target.value})} className="input-field" /></div>
        <div><label className="block text-sm font-medium mb-1">{t('password')}</label><input type="password" value={form.password} onChange={e=>setForm({...form,password:e.target.value})} className="input-field" required /></div>
        <div><label className="block text-sm font-medium mb-1">{t('confirmPassword')}</label><input type="password" value={form.confirm} onChange={e=>setForm({...form,confirm:e.target.value})} className="input-field" required /></div>
        <button type="submit" className="btn-primary w-full">{t('register')}</button>
      </form>
    </div>
  );
}
