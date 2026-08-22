import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import Header from '@/components/Header';
import Footer from '@/components/Footer';

const inter = Inter({ subsets: ['latin', 'cyrillic'] });

export const metadata: Metadata = {
  title: { default: 'Gadgeto — Computer & Electronics Store', template: '%s | Gadgeto' },
  description: 'Buy computer hardware, components, electronics in Ukraine. Fast delivery, quality guarantee.',
  openGraph: { type: 'website', locale: 'uk_UA', siteName: 'Gadgeto' },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="uk">
      <body className={inter.className + " min-h-screen flex flex-col bg-gray-50"}>
        <Header />
        <main className="flex-1">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
