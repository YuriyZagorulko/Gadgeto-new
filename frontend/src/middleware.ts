import createMiddleware from 'next-intl/middleware';
import {routing} from './i18n/routing';

/**
 * Locale negotiation & routing middleware:
 * - serves unprefixed URLs in the default locale (uk), keeping the existing
 *   URL structure intact;
 * - remembers the visitor's choice via the NEXT_LOCALE cookie;
 * - detects the initial locale from the Accept-Language header.
 * When a new locale is added to `routing.ts`, prefixed routes (e.g. /en/*)
 * start working automatically with no further changes here.
 */
export default createMiddleware(routing);

export const config = {
  // Skip API routes, Next.js internals and all static files.
  matcher: '/((?!api|_next|_vercel|.*\\..*).*)',
};
