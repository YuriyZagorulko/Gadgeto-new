'use client';
import { Suspense, useState } from 'react';
import { useTranslations } from 'next-intl';
import { Link } from '@/i18n/navigation';
import { useSearchParams } from 'next/navigation';

const API_BASE = '/api/auth';

type ResetState = 'form' | 'success' | 'invalid';

function ResetPasswordInner() {
  const t = useTranslations('auth');
  const searchParams = useSearchParams();
  const token = searchParams.get('token');

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [state, setState] = useState<ResetState>(token ? 'form' : 'invalid');

  const validateForm = () => {
    if (password.length < 8) { setError(t('errorPasswordLength')); return false; }
    if (!/[A-Za-z]/.test(password)) { setError(t('errorPasswordLetter')); return false; }
    if (!/[0-9]/.test(password)) { setError(t('errorPasswordDigit')); return false; }
    if (password !== confirmPassword) { setError(t('errorPasswordMismatch')); return false; }
    return true;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!validateForm()) return;
    if (!token) { setState('invalid'); return; }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, password, confirm_password: confirmPassword }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const detail = (data.detail || '').toLowerCase();
        if (detail.includes('недійсн') || detail.includes('застаріл')) {
          setState('invalid');
        } else {
          setError(t('errorGenericRequest'));
        }
        return;
      }

      setState('success');
    } catch {
      setError(t('errorServer'));
    } finally {
      setLoading(false);
    }
  };


  if (state === 'success') {
    return (
      <div className="max-w-md mx-auto px-4 py-12 text-center">
        <div className="card p-8">
          <div className="flex justify-center mb-4">
            <svg className="w-12 h-12 text-green-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <path d="M8 12l2 2 4-4" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold mb-4">{t('resetPasswordTitle')}</h1>
          <p className="text-gray-600 mb-6">{t('resetPasswordSuccess')}</p>
          <Link href="/login" className="btn-primary inline-block px-6 py-2 rounded-lg">{t('goToLogin')}</Link>
        </div>
      </div>
    );
  }

  if (state === 'invalid') {
    return (
      <div className="max-w-md mx-auto px-4 py-12 text-center">
        <div className="card p-8">
          <div className="flex justify-center mb-4">
            <svg className="w-12 h-12 text-red-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <path d="M15 9l-6 6" />
              <path d="M9 9l6 6" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold mb-4">{t('resetPasswordTitle')}</h1>
          <p className="text-gray-600 mb-6">{t('resetPasswordInvalidToken')}</p>
          <Link href="/forgot-password" className="btn-primary inline-block px-6 py-2 rounded-lg">{t('resetPasswordRequestNew')}</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-md mx-auto px-4 py-12">
      <h1 className="text-2xl font-bold mb-6 text-center">{t('resetPasswordTitle')}</h1>
      <form onSubmit={handleSubmit} className="card p-6 space-y-4">
        {error && <div className="bg-red-100 text-red-700 p-3 rounded text-sm">{error}</div>}
        <div>
          <label className="block text-sm font-medium mb-1">{t('resetPasswordNewPassword')}</label>
          <input type="password" value={password} onChange={e => setPassword(e.target.value)} className="input-field" required autoFocus />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">{t('resetPasswordConfirmPassword')}</label>
          <input type="password" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} className="input-field" required />
        </div>
        <button type="submit" disabled={loading} className="btn-primary w-full disabled:opacity-50">
          {loading ? '...' : t('resetPasswordSubmit')}
        </button>
        <p className="text-sm text-gray-500 text-center">
          <Link href="/login" className="text-blue-600 hover:underline">{t('signIn')}</Link>
        </p>
      </form>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div className="max-w-md mx-auto px-4 py-12 text-center">
      <svg className="w-8 h-8 text-blue-600 animate-spin mx-auto" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 12a9 9 0 11-6.219-8.56" />
      </svg>
    </div>}>
      <ResetPasswordInner />
    </Suspense>
  );
}
