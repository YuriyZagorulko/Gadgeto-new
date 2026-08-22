'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function LoginPage() {
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
      if (!res.ok) throw new Error('Invalid email or password');
      const data = await res.json();
      localStorage.setItem('auth_token', data.access_token);
      router.push('/account');
    } catch (err: any) { setError(err.message || 'Login failed'); }
  };

  return (
    <div className="max-w-md mx-auto px-4 py-12">
      <h1 className="text-2xl font-bold mb-6 text-center">Sign In</h1>
      <form onSubmit={handleLogin} className="card p-6 space-y-4">
        {error && <div className="bg-red-100 text-red-700 p-3 rounded text-sm">{error}</div>}
        <div><label className="block text-sm font-medium mb-1">Email</label><input type="email" value={email} onChange={e=>setEmail(e.target.value)} className="input-field" required /></div>
        <div><label className="block text-sm font-medium mb-1">Password</label><input type="password" value={password} onChange={e=>setPassword(e.target.value)} className="input-field" required /></div>
        <button type="submit" className="btn-primary w-full">Sign In</button>
        <p className="text-sm text-gray-500 text-center">No account? <a href="/register" className="text-blue-600 hover:underline">Register</a></p>
      </form>
    </div>
  );
}
