'use client';

import { GTM_ID } from '@/lib/analytics';

/** GTM <noscript> iframe. Separate client component: GTM_ID is client-safe. */
export default function GtmNoscript() {
  if (!GTM_ID) return null;
  return (
    <noscript>
      <iframe
        src={`https://www.googletagmanager.com/ns.html?id=${GTM_ID}`}
        height="0"
        width="0"
        style={{ display: 'none', visibility: 'hidden' }}
      />
    </noscript>
  );
}
