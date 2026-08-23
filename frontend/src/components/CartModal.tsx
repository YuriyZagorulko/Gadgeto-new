'use client';

import { useEffect, useRef } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { Link } from '@/i18n/navigation';
import { formatPrice } from '@/lib/format';
import { useCartStore, useCartTotalItems, useCartSubtotal } from '@/lib/cart-store';

interface CartModalProps {
  open: boolean;
  onClose: () => void;
}

export default function CartModal({ open, onClose }: CartModalProps) {
  const t = useTranslations('cart');
  const tProducts = useTranslations('products');
  const locale = useLocale();
  const overlayRef = useRef<HTMLDivElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);

  const items = useCartStore((s) => s.items);
  const updateQuantity = useCartStore((s) => s.updateQuantity);
  const removeItem = useCartStore((s) => s.removeItem);
  const totalItems = useCartTotalItems();
  const subtotal = useCartSubtotal();

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, onClose]);

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [open]);

  if (!open) return null;

  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === overlayRef.current) onClose();
  };

  return (
    <div
      ref={overlayRef}
      onClick={handleOverlayClick}
      className="fixed inset-0 z-[100] flex items-start justify-center sm:items-start"
      style={{ backgroundColor: 'rgba(0,0,0,0.4)' }}
    >
      <div
        ref={modalRef}
        className="relative mt-16 sm:mt-20 w-full max-w-lg bg-white rounded-lg shadow-2xl border border-gray-200 mx-2 sm:mx-4 flex flex-col"
        style={{ maxHeight: 'calc(100vh - 5rem)' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold">
            {t('title')}
            {totalItems > 0 && (
              <span className="ml-2 text-sm font-normal text-gray-500">
                ({totalItems} {t('items')})
              </span>
            )}
          </h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-gray-100 transition text-gray-500 hover:text-gray-700"
            aria-label={t('close')}
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {items.length === 0 ? (
            <div className="text-center py-12">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-16 w-16 mx-auto text-gray-300 mb-4" viewBox="0 0 20 20" fill="currentColor">
                <path d="M3 1a1 1 0 000 2h1.22l.305 1.222a.997.997 0 00.01.042l1.358 5.43-.893.892C3.74 11.846 4.632 14 6.414 14H15a1 1 0 000-2H6.414l1-1H14a1 1 0 00.894-.553l3-6A1 1 0 0017 3H6.28l-.31-1.243A1 1 0 005 1H3zM16 16.5a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0zM6.5 18a1.5 1.5 0 100-3 1.5 1.5 0 000 3z" />
              </svg>
              <p className="text-gray-500 mb-4">{t('empty')}</p>
              <Link
                href="/catalog"
                onClick={onClose}
                className="btn-primary inline-block"
              >
                {t('continueShopping')}
              </Link>
            </div>
          ) : (
            <ul className="space-y-4">
              {items.map((item) => (
                <li key={item.product_id} className="flex gap-3 pb-4 border-b border-gray-100 last:border-0">
                  {/* Image */}
                  <div className="w-16 h-16 flex-shrink-0 rounded-md overflow-hidden bg-gray-100">
                    {item.image ? (
                      <img src={item.image} alt={item.name} className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-xs text-gray-400">
                        {tProducts('noImage')}
                      </div>
                    )}
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <Link
                      href={`/product/${item.slug}`}
                      onClick={onClose}
                      className="text-sm font-medium text-gray-800 hover:text-blue-600 transition line-clamp-2"
                    >
                      {item.name}
                    </Link>
                    {item.sku && (
                      <div className="text-xs text-gray-400 mt-0.5">{t('sku', { sku: item.sku })}</div>
                    )}
                    <div className="text-sm font-semibold mt-1">{formatPrice(item.price, locale)}</div>
                  </div>

                  {/* Quantity + Remove */}
                  <div className="flex flex-col items-end gap-1 flex-shrink-0">
                    <div className="flex items-center border border-gray-200 rounded-md">
                      <button
                        onClick={() => updateQuantity(item.product_id, item.qty - 1)}
                        className="px-2 py-1 text-sm text-gray-500 hover:text-gray-700 hover:bg-gray-50 transition rounded-l-md"
                        aria-label={t('decreaseQty')}
                      >
                        −
                      </button>
                      <span className="px-2 py-1 text-sm font-medium min-w-[2rem] text-center">
                        {item.qty}
                      </span>
                      <button
                        onClick={() => updateQuantity(item.product_id, item.qty + 1)}
                        className="px-2 py-1 text-sm text-gray-500 hover:text-gray-700 hover:bg-gray-50 transition rounded-r-md"
                        aria-label={t('increaseQty')}
                      >
                        +
                      </button>
                    </div>
                    <button
                      onClick={() => removeItem(item.product_id)}
                      className="text-xs text-red-500 hover:text-red-700 transition"
                    >
                      {t('remove')}
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Footer */}
        {items.length > 0 && (
          <div className="border-t border-gray-200 px-5 py-4 space-y-3">
            <div className="flex items-center justify-between text-base">
              <span className="text-gray-600">{t('totalLabel')}</span>
              <span className="text-xl font-bold">{formatPrice(subtotal, locale)}</span>
            </div>
            <div className="flex gap-2">
              <Link
                href="/checkout"
                onClick={onClose}
                className="flex-1 btn-primary text-center text-sm py-2.5"
              >
                {t('proceedToCheckout')}
              </Link>
              <Link
                href="/cart"
                onClick={onClose}
                className="flex-1 btn-outline text-center text-sm py-2.5"
              >
                {t('viewCart')}
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
