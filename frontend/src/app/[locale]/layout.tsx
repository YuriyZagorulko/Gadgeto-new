import type {Metadata} from 'next';
import {Inter} from 'next/font/google';
import {notFound} from 'next/navigation';
import {NextIntlClientProvider, hasLocale} from 'next-intl';
import {getTranslations, setRequestLocale} from 'next-intl/server';
import {routing} from '@/i18n/routing';
import Header from '@/components/Header';
import Footer from '@/components/Footer';
import GtmProvider from '@/components/GtmProvider';
import GtmNoscript from '@/components/GtmNoscript';
import ConsentBanner from '@/components/ConsentBanner';
import {Suspense} from 'react';
import Script from 'next/script';
import '../globals.css';

const GTM_ID = process.env.NEXT_PUBLIC_GTM_ID || '';

const GTM_SNIPPET = `(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src='https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);})(window,document,'script','dataLayer','${GTM_ID}');`;

const CONSENT_DEFAULT_SNIPPET = `window.dataLayer=window.dataLayer||[];window.dataLayer.push({'event':'consent_default','analytics_storage':'denied','ad_storage':'denied','ad_user_data':'denied','ad_personalization':'denied'});try{if(localStorage.getItem('gadgeto_consent')==='accepted'){window.dataLayer.push({'event':'consent_update','analytics_consent':'granted'});}}catch(e){}`;

const inter = Inter({subsets: ['latin', 'cyrillic']});

export function generateStaticParams() {
  return routing.locales.map((locale) => ({locale}));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{locale: string}>;
}): Promise<Metadata> {
  const {locale} = await params;
  if (!hasLocale(routing.locales, locale)) return {};

  const t = await getTranslations({locale, namespace: 'metadata'});

  return {
    metadataBase: new URL(
      process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000'
    ),
    title: {default: t('title'), template: t('titleTemplate')},
    description: t('description'),
    openGraph: {
      type: 'website',
      locale: 'uk_UA',
      siteName: 'Gadgeto',
    },
  };
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{locale: string}>;
}) {
  const {locale} = await params;
  if (!hasLocale(routing.locales, locale)) {
    notFound();
  }

  // Enables static rendering for pages that use translations.
  setRequestLocale(locale);

  return (
    <html lang={locale}>
      <body className={inter.className + ' min-h-screen flex flex-col bg-gray-50'}>
        {GTM_ID ? <Script id="gtm-loader" strategy="afterInteractive" dangerouslySetInnerHTML={{__html: GTM_SNIPPET}} /> : null}
        <Script id="consent-default" strategy="beforeInteractive" dangerouslySetInnerHTML={{__html: CONSENT_DEFAULT_SNIPPET}} />
        {GTM_ID ? <GtmNoscript /> : null}
        <NextIntlClientProvider>
          <Suspense fallback={null}>
            <GtmProvider />
          </Suspense>
          <Header />
          <main className="flex-1">{children}</main>
          <Footer />
          <ConsentBanner />
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
