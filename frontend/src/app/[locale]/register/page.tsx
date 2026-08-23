'use client';
import { useEffect, useState } from 'react';
import { useTranslations } from 'next-intl';
import { Link, useRouter } from '@/i18n/navigation';

const API_BASE = '/api/auth';

export default function RegisterPage() {
  const t = useTranslations('auth');
  const router = useRouter();
  const [form, setForm] = useState({email:'',password:'',confirm:'',full_name:'',phone:''});
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [registered, setRegistered] = useState(false);
  const [registeredEmail, setRegisteredEmail] = useState('');

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

  const validateForm = () => {
    if (!form.full_name.trim()) { setError(t('fullName') + ' є обов\'язковим'); return false; }
    if (!form.email.trim()) { setError(t('errorEmailFormat')); return false; }
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email.trim())) { setError(t('errorEmailFormat')); return false; }
    if (form.phone.trim() && !/^(\+?380\d{9}|0\d{9})$/.test(form.phone.replace(/[\s\-\(\)]/g,''))) { setError(t('errorPhoneFormat')); return false; }
    if (form.password.length < 8) { setError(t('errorPasswordLength')); return false; }
    if (!/[A-Za-z]/.test(form.password)) { setError(t('errorPasswordLetter')); return false; }
    if (!/[0-9]/.test(form.password)) { setError(t('errorPasswordDigit')); return false; }
    if (form.password !== form.confirm) { setError(t('errorPasswordMismatch')); return false; }
    return true;
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault(); setError('');
    if (!validateForm()) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/register`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: form.email.trim().toLowerCase(),
          password: form.password,
          confirm_password: form.confirm,
          full_name: form.full_name.trim(),
          phone: form.phone.trim(),
        }),
      });
      if (!res.ok) {
        const data = await res.json();
        if (res.status === 409) {
          if (data.detail === 'EMAIL_EXISTS_UNVERIFIED') {
            setError('Користувач з такою електронною поштою вже існує, але email не підтверджено. Натисніть "Надіслати лист повторно" нижче.');
          } else {
            setError(data.detail || t('errorEmailExists'));
          }
        } else if (data.detail && typeof data.detail === 'object' && Array.isArray(data.detail)) {
          const msgs = data.detail.map((d: any) => d.msg).filter(Boolean);
          setError(msgs.length ? msgs[0] : t('errorRegistrationFailed'));
        } else {
          setError(data.detail || t('errorRegistrationFailed'));
        }
        return;
      }
      const data = await res.json();
      if (data.message && data.message.startsWith('Перевірте')) {
        setRegisteredEmail(form.email.trim().toLowerCase());
        setRegistered(true);
      } else {
        setError(t('errorRegistrationFailed'));
      }
    } catch (err: any) {
      setError(t('errorServer'));
    } finally {
      setLoading(false);
    }
  };

  if (registered) {
    return (
      <div className="max-w-md mx-auto px-4 py-12 text-center">
        <div className="card p-8">
          <div className="text-green-500 text-5xl mb-4">✓</div>
          <h1 className="text-2xl font-bold mb-4">{t('registrationSuccess')}</h1>
          <p className="text-gray-600 mb-6">{t('registrationSuccessText', { email: registeredEmail })}</p>
          <div className="space-y-3">
            <Link href="/login" className="btn-primary inline-block px-6 py-2 rounded-lg">{t('signIn')}</Link>
          </div>
        </div>
      </div>
    );
  }

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
        <button type="submit" disabled={loading} className="btn-primary w-full disabled:opacity-50">{loading ? '...' : t('register')}</button>
        <p className="text-sm text-gray-500 text-center">{t('noAccountPrompt')} <Link href="/login" className="text-blue-600 hover:underline">{t('signInTitle')}</Link></p>
      </form>
    </div>
  );
}
