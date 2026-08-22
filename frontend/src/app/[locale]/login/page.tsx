'use client';
import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Link, useRouter } from '@/i18n/navigation';

export default function LoginPage() {
  const t = useTranslations('auth');
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault(); setError('');
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) throw new Error(t('errorInvalidCredentials'));
      const data = await res.json();
      localStorage.setItem('auth_token', data.access_token);
      router.push('/account');
    } catch (err: any) { setError(err.message || t('errorLoginFailed')); }
  };

  return (
    <div className="max-w-md mx-auto px-4 py-12">
      <h1 className="text-2xl font-bold mb-6 text-center">{t('signInTitle')}</h1>
      <form onSubmit={handleLogin} className="card p-6 space-y-4">
        {error && <div className="bg-red-100 text-red-700 p-3 rounded text-sm">{error}</div>}
        <div><label className="block text-sm font-medium mb-1">{t('email')}</label><input type="email" value={email} onChange={e=>setEmail(e.target.value)} className="input-field" required /></div>
        <div><label className="block text-sm font-medium mb-1">{t('password')}</label><input type="password" value={password} onChange={e=>setPassword(e.target.value)} className="input-field" required /></div>
        <button type="submit" className="btn-primary w-full">{t('signIn')}</button>
        <p className="text-sm text-gray-500 text-center">{t('noAccountPrompt')} <Link href="/register" className="text-blue-600 hover:underline">{t('registerLink')}</Link></p>
      </form>
    </div>
  );
}
