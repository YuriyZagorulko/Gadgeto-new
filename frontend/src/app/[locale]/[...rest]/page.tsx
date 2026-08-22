import {notFound} from 'next/navigation';

/**
 * Catch-all for unknown URLs under a valid locale.
 * Renders the localized [locale]/not-found.tsx screen.
 */
export default function CatchAllPage() {
  notFound();
}
