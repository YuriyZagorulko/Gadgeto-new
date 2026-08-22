'use client';

import React from 'react';
import { AuthProvider } from './AuthProvider';
import { ToastProvider } from './ui';

/** Global client providers: authentication + toast notifications. */
export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <ToastProvider>{children}</ToastProvider>
    </AuthProvider>
  );
}
