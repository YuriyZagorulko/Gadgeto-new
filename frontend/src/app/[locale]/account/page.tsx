'use client';
import { useEffect, useState } from 'react';
import { useTranslations } from 'next-intl';
import { Link, useRouter } from '@/i18n/navigation';

const API_BASE = '/api/auth';

export default function AccountPage() {
  const t = useTranslations('account');
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('auth_token');
    if (!token) { router.replace('/login'); return; }
    fetch(`${API_BASE}/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(u => { setUser(u); setLoading(false); })
      .catch(() => { localStorage.removeItem('auth_token'); router.replace('/login'); });
  }, [router]);

  const handleLogout = () => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      fetch(`${API_BASE}/logout`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => {});
    }
    localStorage.removeItem('auth_token');
    router.push('/');
  };

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-8">
        <div className="text-center text-gray-500 py-8">...</div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">{t('title')}</h1>
      {!user ? (
        <div className="text-center text-gray-500 py-8">...</div>
      ) : (
        <div className="space-y-4">
          <div className="card p-6">
            <h2 className="font-semibold mb-3">{t('profile')}</h2>
            <div className="text-sm space-y-2 text-gray-600">
              <div>{t('name')} {user.full_name}</div>
              <div>{t('email')} {user.email}</div>
              {user.phone && <div>{t('phone')} {user.phone}</div>}
              <div className="flex items-center gap-2">
                <span className={
                  user.email_verified
                    ? 'text-green-600 bg-green-50 px-2 py-0.5 rounded text-xs font-medium'
                    : 'text-yellow-600 bg-yellow-50 px-2 py-0.5 rounded text-xs font-medium'
                }>
                  {user.email_verified ? t('emailVerified') : t('emailNotVerified')}
                </span>
              </div>
            </div>
          </div>
          <div className="card p-6 flex items-center justify-between">
            <span className="font-medium">{t('orders')}</span>
            <span className="text-sm text-gray-500">{t('noOrders')}</span>
          </div>
          <button onClick={handleLogout} className="btn-outline inline-block cursor-pointer">{t('logout')}</button>
        </div>
      )}
    </div>
  );
}
