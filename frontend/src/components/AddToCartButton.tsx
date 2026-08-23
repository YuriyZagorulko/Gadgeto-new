'use client';

import { useTranslations } from 'next-intl';
import { useCartStore, useIsInCart } from '@/lib/cart-store';

interface AddToCartButtonProps {
  product: {
    id: number;
    name: string;
    slug: string;
    sku?: string;
    price: number;
    old_price?: number | null;
    image?: string;
    stock_status?: string;
  };
  className?: string;
  /** If true, show a compact button variant suitable for cards */
  compact?: boolean;
}

export default function AddToCartButton({ product, className = '', compact = false }: AddToCartButtonProps) {
  const t = useTranslations('product');
  const addItem = useCartStore((s) => s.addItem);
  const openCartModal = useCartStore((s) => s.openCartModal);
  const isInCart = useIsInCart(product.id);

  const handleBuy = async () => {
    if (product.stock_status === 'out_of_stock') return;
    if (isInCart) {
      // Already in cart — just open the modal, never add again
      openCartModal();
      return;
    }
    // Add once and open cart
    await addItem({
      id: product.id,
      name: product.name,
      slug: product.slug,
      sku: product.sku,
      price: product.price,
      old_price: product.old_price,
      image: product.image,
      stock_status: product.stock_status,
    });
    // addItem already opens the modal automatically
  };

  if (product.stock_status === 'out_of_stock') {
    return (
      <button
        disabled
        className={`w-full text-lg py-3 rounded-lg font-medium bg-gray-300 text-gray-500 cursor-not-allowed ${className}`}
      >
        {t('outOfStock')}
      </button>
    );
  }

  if (isInCart) {
    // ── "В кошику" — product already in cart, open modal on click ──
    if (compact) {
      return (
        <button
          onClick={handleBuy}
          className={`p-2 rounded-lg transition-colors bg-green-100 text-green-700 hover:bg-green-200 ${className}`}
          title={t('inCart')}
          aria-label={t('inCart')}
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
          </svg>
        </button>
      );
    }
    return (
      <button
        onClick={handleBuy}
        className={`w-full text-lg py-3 rounded-lg font-medium bg-green-600 text-white hover:bg-green-700 transition flex items-center justify-center gap-2 ${className}`}
      >
        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
          <path d="M3 1a1 1 0 000 2h1.22l.305 1.222a.997.997 0 00.01.042l1.358 5.43-.893.892C3.74 11.846 4.632 14 6.414 14H15a1 1 0 000-2H6.414l1-1H14a1 1 0 00.894-.553l3-6A1 1 0 0017 3H6.28l-.31-1.243A1 1 0 005 1H3zM16 16.5a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0zM6.5 18a1.5 1.5 0 100-3 1.5 1.5 0 000 3z" />
        </svg>
        {t('inCart')}
      </button>
    );
  }

  // ── "Купити" — product not yet in cart ──
  if (compact) {
    return (
      <button
        onClick={handleBuy}
        className={`p-2 rounded-lg transition-colors bg-blue-600 text-white hover:bg-blue-700 ${className}`}
        title={t('buy')}
        aria-label={t('buy')}
      >
        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
          <path d="M3 1a1 1 0 000 2h1.22l.305 1.222a.997.997 0 00.01.042l1.358 5.43-.893.892C3.74 11.846 4.632 14 6.414 14H15a1 1 0 000-2H6.414l1-1H14a1 1 0 00.894-.553l3-6A1 1 0 0017 3H6.28l-.31-1.243A1 1 0 005 1H3zM16 16.5a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0zM6.5 18a1.5 1.5 0 100-3 1.5 1.5 0 000 3z" />
        </svg>
      </button>
    );
  }

  return (
    <button
      onClick={handleBuy}
      className={`w-full text-lg py-3 rounded-lg font-medium bg-blue-600 text-white hover:bg-blue-700 transition flex items-center justify-center gap-2 ${className}`}
    >
      <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
        <path d="M3 1a1 1 0 000 2h1.22l.305 1.222a.997.997 0 00.01.042l1.358 5.43-.893.892C3.74 11.846 4.632 14 6.414 14H15a1 1 0 000-2H6.414l1-1H14a1 1 0 00.894-.553l3-6A1 1 0 0017 3H6.28l-.31-1.243A1 1 0 005 1H3zM16 16.5a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0zM6.5 18a1.5 1.5 0 100-3 1.5 1.5 0 000 3z" />
      </svg>
      {t('buy')}
    </button>
  );
}
