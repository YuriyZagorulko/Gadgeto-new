'use client';
import { useEffect, useState } from 'react';
import { useTranslations } from 'next-intl';
import { Link, useRouter } from '@/i18n/navigation';

export default function AccountPage() {
  const t = useTranslations('account');
  const router = useRouter();
  const [user, setUser] = useState<any>(null);

  useEffect(() => {
    const token = localStorage.getItem('auth_token');
    if (!token) { router.replace('/login'); return; }
    fetch('/api/auth/me', { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(setUser)
      .catch(() => { localStorage.removeItem('auth_token'); router.replace('/login'); });
  }, [router]);

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">{t('title')}</h1>
      {!user ? (
        <div className="text-center text-gray-500 py-8">...</div>
      ) : (
        <div className="space-y-4">
          <div className="card p-6">
            <h2 className="font-semibold mb-3">{t('profile')}</h2>
            <div className="text-sm space-y-1 text-gray-600">
              <div>{t('name')} {user.full_name}</div>
              <div>{t('email')} {user.email}</div>
              {user.phone && <div>{t('phone')} {user.phone}</div>}
            </div>
          </div>
          <div className="card p-6 flex items-center justify-between">
            <span className="font-medium">{t('orders')}</span>
            <span className="text-sm text-gray-500">{t('noOrders')}</span>
          </div>
          <Link href="/" className="btn-outline inline-block">{t('logout')}</Link>
        </div>
      )}
    </div>
  );
}
