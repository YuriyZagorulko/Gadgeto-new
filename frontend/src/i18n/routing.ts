import {defineRouting} from 'next-intl/routing';

/**
 * Central i18n routing configuration.
 *
 * Currently Ukrainian-only: `uk` is served WITHOUT a URL prefix, so the
 * existing URL structure (/catalog, /product/..., ...) is untouched.
 *
 * To launch English later:
 *   1. add `messages/en.json`;
 *   2. add 'en' to `locales` below;
 *   3. re-add the language switcher component to the header.
 * The middleware, routing and typed hooks pick everything up automatically.
 */
export const routing = defineRouting({
  locales: ['uk'],
  defaultLocale: 'uk',
  localePrefix: 'as-needed',
});

export type Locale = (typeof routing.locales)[number];
