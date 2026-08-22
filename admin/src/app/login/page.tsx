'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/components/AuthProvider';
import { Button, Field, Input } from '@/components/ui';

export default function LoginPage() {
  const { user, ready, login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  // Already authenticated -> straight to the dashboard.
  useEffect(() => {
    if (ready && user) router.replace('/dashboard');
  }, [ready, user, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      await login(email.trim(), password);
      router.replace('/dashboard');
    } catch (err: any) {
      setError(err?.message || 'Не вдалося увійти. Перевірте дані.');
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-900 px-4">
      <form onSubmit={handleSubmit} className="bg-white p-8 rounded-lg shadow-lg w-full max-w-sm" noValidate>
        <div className="text-center mb-6">
          <div className="text-2xl font-bold text-gray-900">
            Gadgeto <span className="text-blue-600">Admin</span>
          </div>
          <p className="text-sm text-gray-500 mt-1">Вхід до адміністративної панелі</p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm p-3 rounded-md mb-4" role="alert">
            {error}
          </div>
        )}

        <div className="space-y-4">
          <Field label="Електронна пошта">
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              autoFocus
              required
            />
          </Field>
          <Field label="Пароль">
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </Field>
        </div>

        <Button type="submit" loading={busy} className="w-full mt-6">
          {busy ? 'Вхід...' : 'Увійти'}
        </Button>
      </form>
    </div>
  );
}
