'use client';
import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Link } from '@/i18n/navigation';

const API_BASE = '/api/auth';

export default function ForgotPasswordPage() {
  const t = useTranslations('auth');
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!email.trim()) {
      setError(t('errorEmailFormat'));
      return;
    }
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())) {
      setError(t('errorEmailFormat'));
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim().toLowerCase() }),
      });

      if (!res.ok) {
        setError(t('errorGenericRequest'));
        return;
      }

      setSubmitted(true);
    } catch {
      setError(t('errorServer'));
    } finally {
      setLoading(false);
    }
  };

  if (submitted) {
    return (
      <div className="max-w-md mx-auto px-4 py-12 text-center">
        <div className="card p-8">
          <div className="flex justify-center mb-4">
            <svg className="w-12 h-12 text-green-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <path d="M8 12l2 2 4-4" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold mb-4">{t('forgotPasswordTitle')}</h1>
          <p className="text-gray-600 mb-6">{t('forgotPasswordSuccess')}</p>
          <Link href="/login" className="btn-primary inline-block px-6 py-2 rounded-lg">{t('signIn')}</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-md mx-auto px-4 py-12">
      <h1 className="text-2xl font-bold mb-6 text-center">{t('forgotPasswordTitle')}</h1>
      <p className="text-gray-600 text-center mb-6">{t('forgotPasswordDescription')}</p>
      <form onSubmit={handleSubmit} className="card p-6 space-y-4">
        {error && <div className="bg-red-100 text-red-700 p-3 rounded text-sm">{error}</div>}
        <div>
          <label className="block text-sm font-medium mb-1">{t('forgotPasswordEmail')}</label>
          <input type="email" value={email} onChange={e => setEmail(e.target.value)} className="input-field" required autoFocus />
        </div>
        <button type="submit" disabled={loading} className="btn-primary w-full disabled:opacity-50">
          {loading ? t('sending') : t('forgotPasswordSubmit')}
        </button>
        <p className="text-sm text-gray-500 text-center">
          <Link href="/login" className="text-blue-600 hover:underline">{t('signIn')}</Link>
        </p>
      </form>
    </div>
  );
}
