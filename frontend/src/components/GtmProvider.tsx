'use client';

import { useEffect } from 'react';
import { usePathname, useSearchParams } from 'next/navigation';
import { trackPageview } from '@/lib/analytics';
import { captureAttribution } from '@/lib/attribution';

/**
 * Loads GTM once (gtm.js) + pushes a deduped `virtual_pageview` and
 * captures first-party attribution on every SPA navigation.
 * Assumes the <noscript> fallback + dataLayer init live in the layout.
 * NOTE: `NEXT_PUBLIC_*` vars are baked into the client bundle at build
 * time. They must be present as build args AND runtime env when the
 * frontend container starts (`docker-compose.yml` passes
 * `NEXT_PUBLIC_GTM_ID`, default `GTM-TFC47QZW`); otherwise the GTM
 * script is absent from served HTML until the frontend is restarted
 * with the variable set.
 */
export default function GtmProvider() {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  useEffect(() => {
    const qs = searchParams?.toString();
    const path = qs ? `${pathname}?${qs}` : pathname || '/';
    try {
      captureAttribution();
    } catch { /* ignore */ }
    trackPageview(path);
  }, [pathname, searchParams]);

  return null;
}
