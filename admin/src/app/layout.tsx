import type { Metadata } from 'next';
import './globals.css';
import { Providers } from '@/components/Providers';
import { AppShell } from '@/components/AppShell';

export const metadata: Metadata = {
  title: 'Gadgeto Admin',
  description: 'Адміністративна панель інтернет-магазину Gadgeto',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="uk">
      <body>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
