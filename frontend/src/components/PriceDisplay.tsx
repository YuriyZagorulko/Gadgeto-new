'use client';

import { useLocale } from 'next-intl';
import { formatPrice } from '@/lib/format';

interface PriceDisplayProps {
  /** Price in minor units (kopiykas). */
  price: number;
  /** Original/old price in minor units, or null/undefined when there is no discount. */
  oldPrice?: number | null;
  /** Additional classes for the outer wrapper element. */
  className?: string;
  /**
   * Rendering context that controls text size.
   * - `'card'`  → product card / grid (default)
   * - `'detail'` → product detail page
   * - `'inline'` → small inline (search suggestions etc.)
   */
  variant?: 'card' | 'detail' | 'inline';
}

/**
 * Storefront product-price display.
 *
 * **Normal price** (no valid old price):
 *   dark/black text, bold, prominent.
 *
 * **Discounted price** (valid old price > current price):
 *   old price crossed out in gray, current price in red.
 *
 * This component uses `useLocale()` from next-intl, so it MUST be rendered
 * inside a `NextIntlClientProvider` (already present in the layout).
 */
export default function PriceDisplay({
  price,
  oldPrice,
  className = '',
  variant = 'card',
}: PriceDisplayProps) {
  const locale = useLocale();

  const formatted = formatPrice(price, locale);
  const hasDiscount =
    oldPrice != null && oldPrice > 0 && oldPrice > price;
  const formattedOld = hasDiscount ? formatPrice(oldPrice!, locale) : null;

  const sizeClasses: Record<string, string> = {
    card: 'text-sm',
    detail: 'text-3xl',
    inline: 'text-xs',
  };
  const size = sizeClasses[variant] || sizeClasses.card;

  if (!hasDiscount) {
    return (
      <span className={`${size} font-bold text-gray-900 ${className}`}>
        {formatted}
      </span>
    );
  }

  return (
    <span className={`${size} flex items-center gap-2 flex-wrap ${className}`}>
      {variant === 'detail' ? (
        <>
          <span className="text-lg text-gray-400 line-through">{formattedOld}</span>
          <span className="font-bold text-red-600">{formatted}</span>
        </>
      ) : (
        <>
          <span className="text-gray-400 line-through">{formattedOld}</span>
          <span className="font-bold text-red-600">{formatted}</span>
        </>
      )}
    </span>
  );
}