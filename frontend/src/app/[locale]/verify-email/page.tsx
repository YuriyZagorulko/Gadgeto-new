'use client';
import { useEffect, useState } from 'react';
import { useTranslations } from 'next-intl';
import { Link, useSearchParams } from 'next/navigation';

const API_BASE = '/api/auth';

type VerifyState = 'loading' | 'success' | 'expired' | 'invalid' | 'already_verified';

export default function VerifyEmailPage() {
  const t = useTranslations('verifyEmail');
  const searchParams = useSearchParams();
  const token = searchParams.get('token');
  const [state, setState] = useState<VerifyState>('loading');
  const [resending, setResending] = useState(false);
  const [resendSent, setResendSent] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!token) {
      setState('invalid');
      return;
    }
    verifyToken(token);
  }, [token]);

  const verifyToken = async (tkn: string) => {
    try {
      const res = await fetch(`${API_BASE}/verify-email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: tkn }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        setState('success');
      } else if (res.status === 410) {
        setState('expired');
      } else if (res.status === 400 && data.detail === 'Електронну пошту вже підтверджено.') {
        setState('already_verified');
      } else {
        setState('invalid');
      }
    } catch {
      setState('invalid');
    }
  };

  const handleResend = async () => {
    if (!token) return;
    setResending(true); setError('');
    // We need email for resend - try to extract from token or show error
    setError('Будь ласка, введіть свою електронну пошту на сторінці входу та натисніть "Надіслати лист повторно".');
    setResending(false);
  };

  return (
    <div className="max-w-md mx-auto px-4 py-12 text-center">
      <div className="card p-8">
        {state === 'loading' && (
          <>
            <div className="animate-spin text-blue-600 text-4xl mb-4 inline-block">⟳</div>
            <h1 className="text-2xl font-bold mb-4">{t('loading')}</h1>
          </>
        )}
        {state === 'success' && (
          <>
            <div className="text-green-500 text-5xl mb-4">✓</div>
            <h1 className="text-2xl font-bold mb-4">{t('success')}</h1>
            <p className="text-gray-600 mb-6">{t('successText')}</p>
            <Link href="/login" className="btn-primary inline-block px-6 py-2 rounded-lg">{t('loginButton')}</Link>
          </>
        )}
        {state === 'expired' && (
          <>
            <div className="text-yellow-500 text-5xl mb-4">!</div>
            <h1 className="text-2xl font-bold mb-4">{t('expired')}</h1>
            <p className="text-gray-600 mb-6">{t('expiredText')}</p>
            <Link href="/login" className="btn-primary inline-block px-6 py-2 rounded-lg">{t('loginButton')}</Link>
          </>
        )}
        {state === 'invalid' && (
          <>
            <div className="text-red-500 text-5xl mb-4">✕</div>
            <h1 className="text-2xl font-bold mb-4">{t('invalid')}</h1>
            <Link href="/login" className="btn-primary inline-block px-6 py-2 rounded-lg">{t('loginButton')}</Link>
          </>
        )}
        {state === 'already_verified' && (
          <>
            <div className="text-green-500 text-5xl mb-4">✓</div>
            <h1 className="text-2xl font-bold mb-4">{t('success')}</h1>
            <p className="text-gray-600 mb-6">{t('alreadyVerified')}</p>
            <Link href="/login" className="btn-primary inline-block px-6 py-2 rounded-lg">{t('loginButton')}</Link>
          </>
        )}
      </div>
    </div>
  );
}
