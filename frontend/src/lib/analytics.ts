/**
 * Google Tag Manager + GA4 ecommerce helpers.
 *
 * GTM (container NEXT_PUBLIC_GTM_ID) is the ONLY tracking layer — GA4 is
 * configured inside GTM, never hardcoded separately. All ecommerce events
 * are pushed to `window.dataLayer`; GTM/GA4 tags consume them.
 *
 * SPA handling: Next.js App Router does client-side navigation, so GTM's
 * built-in History Change trigger observes route changes. We additionally
 * push an explicit `virtual_pageview` event per navigation; the GTM
 * container should use it (not "All Pages" on history) to avoid duplicates.
 */

export const GTM_ID = process.env.NEXT_PUBLIC_GTM_ID || '';

declare global {
  interface Window {
    dataLayer?: Record<string, unknown>[];
    __gtmPagePath?: string;
  }
}

export function dataLayerPush(event: Record<string, unknown>): void {
  if (typeof window === 'undefined') return;
  window.dataLayer = window.dataLayer || [];
  window.dataLayer.push(event);
}

function toMajor(amountMinor: number | null | undefined): number {
  return Math.round(((amountMinor || 0) / 100) * 100) / 100;
}

export interface EcommerceItemInput {
  id: string | number;
  name: string;
  price: number; // minor units (kopiykas)
  quantity: number;
  sku?: string | null;
  category?: string | null;
  brand?: string | null;
}

export function toGaItem(item: EcommerceItemInput): Record<string, unknown> {
  const ga: Record<string, unknown> = {
    item_id: String(item.id),
    item_name: item.name,
    price: toMajor(item.price),
    quantity: item.quantity,
  };
  if (item.sku) ga.sku = item.sku;
  if (item.category) ga.item_category = item.category;
  if (item.brand) ga.item_brand = item.brand;
  return ga;
}

/** Push a pageview for SPA navigations. Dedupes identical consecutive paths. */
export function trackPageview(path: string): void {
  if (typeof window === 'undefined') return;
  if (window.__gtmPagePath === path) return;
  window.__gtmPagePath = path;
  dataLayerPush({
    event: 'virtual_pageview',
    page_path: path,
    page_location: window.location.href,
    page_title: document.title,
  });
}

export function trackViewItem(item: EcommerceItemInput, currency = 'UAH'): void {
  dataLayerPush({
    event: 'view_item',
    ecommerce: {
      currency,
      value: toMajor(item.price) * item.quantity,
      items: [toGaItem(item)],
    },
  });
}

export function trackAddToCart(item: EcommerceItemInput, currency = 'UAH'): void {
  dataLayerPush({
    event: 'add_to_cart',
    ecommerce: {
      currency,
      value: toMajor(item.price) * item.quantity,
      items: [toGaItem(item)],
    },
  });
}

export function trackRemoveFromCart(item: EcommerceItemInput, currency = 'UAH'): void {
  dataLayerPush({
    event: 'remove_from_cart',
    ecommerce: {
      currency,
      value: toMajor(item.price) * item.quantity,
      items: [toGaItem(item)],
    },
  });
}

export function trackViewCart(items: EcommerceItemInput[], currency = 'UAH'): void {
  const value = items.reduce((s, i) => s + toMajor(i.price) * i.quantity, 0);
  dataLayerPush({
    event: 'view_cart',
    ecommerce: { currency, value, items: items.map(toGaItem) },
  });
}

export function trackBeginCheckout(items: EcommerceItemInput[], currency = 'UAH'): void {
  const value = items.reduce((s, i) => s + toMajor(i.price) * i.quantity, 0);
  dataLayerPush({
    event: 'begin_checkout',
    ecommerce: { currency, value, items: items.map(toGaItem) },
  });
}

export interface PurchaseInput {
  transactionId: string | number;
  items: EcommerceItemInput[];
  totalMinor: number;
  currency?: string;
}

/**
 * Fire `purchase` for a successfully created order.
 * MUST be called exactly once per order — callers guard via
 * `gadgeto_purchase_<orderId>` localStorage flag (see trackPurchaseOnce).
 */
export function trackPurchase({ transactionId, items, totalMinor, currency = 'UAH' }: PurchaseInput): void {
  dataLayerPush({
    event: 'purchase',
    ecommerce: {
      transaction_id: String(transactionId),
      currency,
      value: toMajor(totalMinor),
      items: items.map(toGaItem),
    },
  });
}

const purchaseFlagKey = (orderId: string | number) => `gadgeto_purchase_${orderId}`;

/** Idempotent purchase: fires only the first time for a given order ID. */
export function trackPurchaseOnce(input: PurchaseInput): boolean {
  if (typeof window === 'undefined') return false;
  const key = purchaseFlagKey(input.transactionId);
  try {
    if (localStorage.getItem(key)) return false;
    trackPurchase(input);
    localStorage.setItem(key, JSON.stringify({ t: Date.now() }));
    return true;
  } catch {
    // localStorage unavailable (private mode) — still fire once per call site.
    trackPurchase(input);
    return true;
  }
}
