'use client';
import { useEffect, useState } from 'react';
import { useTranslations } from 'next-intl';
import { Link, useRouter } from '@/i18n/navigation';

const API_BASE = '/api/auth';

export default function LoginPage() {
  const t = useTranslations('auth');
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [emailNotVerified, setEmailNotVerified] = useState(false);
  const [resending, setResending] = useState(false);
  const [resendSent, setResendSent] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      fetch('/api/auth/me', { headers: { Authorization: `Bearer ${token}` } })
        .then(r => {
          if (r.ok) router.push('/account');
        })
        .catch(() => {});
    }
  }, [router]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault(); setError(''); setEmailNotVerified(false); setResendSent(false);
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim().toLowerCase(), password }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        if (data.detail === 'EMAIL_NOT_VERIFIED') {
          setEmailNotVerified(true);
          setError(t('emailNotVerified'));
        } else {
          setError(data.detail || t('errorInvalidCredentials'));
        }
        return;
      }
      localStorage.setItem('auth_token', data.access_token);
      router.push('/account');
    } catch (err: any) {
      setError(t('errorServer'));
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    setResending(true); setError(''); setResendSent(false);
    try {
      const res = await fetch(`${API_BASE}/resend-verification`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim().toLowerCase() }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data.detail || t('errorServer'));
        return;
      }
      setResendSent(true);
    } catch {
      setError(t('errorServer'));
    } finally {
      setResending(false);
    }
  };

  return (
    <div className="max-w-md mx-auto px-4 py-12">
      <h1 className="text-2xl font-bold mb-6 text-center">{t('signInTitle')}</h1>
      <form onSubmit={handleLogin} className="card p-6 space-y-4">
        {error && <div className="bg-red-100 text-red-700 p-3 rounded text-sm">{error}</div>}
        {resendSent && <div className="bg-green-100 text-green-700 p-3 rounded text-sm">{t('resendSuccess')}</div>}
        <div><label className="block text-sm font-medium mb-1">{t('email')}</label><input type="email" value={email} onChange={e=>setEmail(e.target.value)} className="input-field" required /></div>
        <div><label className="block text-sm font-medium mb-1">{t('password')}</label><input type="password" value={password} onChange={e=>setPassword(e.target.value)} className="input-field" required /></div>
        <div className="text-right -mt-2">
          <Link href="/forgot-password" className="text-sm text-blue-600 hover:underline">{t('forgotPasswordLink')}</Link>
        </div>
        <button type="submit" disabled={loading} className="btn-primary w-full disabled:opacity-50">{loading ? '...' : t('signIn')}</button>
        {emailNotVerified && (
          <div className="text-center">
            <button onClick={handleResend} disabled={resending} className="text-blue-600 hover:underline text-sm disabled:opacity-50">
              {resending ? '...' : t('resendEmailPrompt')}
            </button>
          </div>
        )}
        <p className="text-sm text-gray-500 text-center">{t('noAccountPrompt')} <Link href="/register" className="text-blue-600 hover:underline">{t('registerLink')}</Link></p>
      </form>
    </div>
  );
}
