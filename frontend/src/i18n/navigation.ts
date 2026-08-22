import {createNavigation} from 'next-intl/navigation';
import {routing} from './routing';

/**
 * Locale-aware navigation utilities.
 *
 * Use these instead of `next/link` / `next/navigation` so that internal
 * links and programmatic navigations automatically stay consistent with
 * the active locale configuration (relevant once more than one locale
 * is enabled in `routing.ts`).
 */
export const {Link, redirect, usePathname, useRouter, getPathname} =
  createNavigation(routing);
