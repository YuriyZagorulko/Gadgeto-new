'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { api, getToken, setToken } from '@/lib/api';

export type AdminUser = {
  id: number;
  email: string;
  full_name: string | null;
  phone?: string | null;
  role: string;
  status?: string;
};

type AuthCtx = {
  user: AdminUser | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const Ctx = createContext<AuthCtx>({ user: null, ready: false, login: async () => {}, logout: async () => {} });

export function useAuth() {
  return useContext(Ctx);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AdminUser | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!getToken()) {
        setReady(true);
        return;
      }
      try {
        const me = await api.get<AdminUser>('/auth/me');
        if (!cancelled) setUser(me);
      } catch {
        setToken(null);
      } finally {
        if (!cancelled) setReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = async (email: string, password: string) => {
    const data = await api.post<{ access_token: string; user: AdminUser }>('/auth/login', { email, password });
    setToken(data.access_token);
    setUser(data.user);
  };

  const logout = async () => {
    try {
      await api.post('/auth/logout');
    } catch {
      /* session may already be gone */
    }
    setToken(null);
    setUser(null);
    window.location.href = '/login';
  };

  return <Ctx.Provider value={{ user, ready, login, logout }}>{children}</Ctx.Provider>;
}
