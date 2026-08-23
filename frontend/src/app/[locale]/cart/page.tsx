'use client';

import { useEffect } from 'react';
import { useRouter } from '@/i18n/navigation';

/**
 * Cart page has been replaced by the cart modal/drawer.
 * Any direct navigation to /cart is redirected to /catalog.
 */
export default function CartPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/catalog');
  }, [router]);

  return null;
}
