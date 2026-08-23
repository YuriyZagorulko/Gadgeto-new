'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { useCartStore } from '@/lib/cart-store';

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
  /** If true, show a compact icon-only button variant */
  compact?: boolean;
}

export default function AddToCartButton({ product, className = '', compact = false }: AddToCartButtonProps) {
  const t = useTranslations('product');
  const addItem = useCartStore((s) => s.addItem);
  const [feedback, setFeedback] = useState<'idle' | 'added' | 'error'>('idle');

  const handleClick = async () => {
    if (product.stock_status === 'out_of_stock') return;
    setFeedback('idle');
    try {
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
      setFeedback('added');
      setTimeout(() => setFeedback('idle'), 2000);
    } catch {
      setFeedback('error');
      setTimeout(() => setFeedback('idle'), 3000);
    }
  };

  if (compact) {
    return (
      <button
        onClick={handleClick}
        disabled={product.stock_status === 'out_of_stock'}
        className={`p-2 rounded-lg transition-colors ${
          product.stock_status === 'out_of_stock'
            ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
            : feedback === 'added'
              ? 'bg-green-100 text-green-700'
              : 'bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-600'
        } ${className}`}
        title={t('addToCart')}
        aria-label={t('addToCart')}
      >
        {feedback === 'added' ? (
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
          </svg>
        ) : (
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path d="M3 1a1 1 0 000 2h1.22l.305 1.222a.997.997 0 00.01.042l1.358 5.43-.893.892C3.74 11.846 4.632 14 6.414 14H15a1 1 0 000-2H6.414l1-1H14a1 1 0 00.894-.553l3-6A1 1 0 0017 3H6.28l-.31-1.243A1 1 0 005 1H3zM16 16.5a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0zM6.5 18a1.5 1.5 0 100-3 1.5 1.5 0 000 3z" />
          </svg>
        )}
      </button>
    );
  }

  return (
    <div className="relative">
      <button
        onClick={handleClick}
        disabled={product.stock_status === 'out_of_stock'}
        className={`w-full text-lg py-3 rounded-lg transition font-medium ${
          product.stock_status === 'out_of_stock'
            ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
            : feedback === 'added'
              ? 'bg-green-600 text-white hover:bg-green-700'
              : feedback === 'error'
                ? 'bg-red-600 text-white'
                : 'bg-blue-600 text-white hover:bg-blue-700'
        } ${className}`}
      >
        {feedback === 'added'
          ? '✓ ' + t('addedToCart')
          : feedback === 'error'
            ? t('addToCartError')
            : t('addToCart')}
      </button>
    </div>
  );
}
