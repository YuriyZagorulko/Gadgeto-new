/**
 * Zustand cart store — single source of truth for cart state.
 *
 * Persisted to localStorage so the cart survives page refreshes.
 * Syncs with the backend API so checkout / order creation works.
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface CartItem {
  /** cart_items.id from backend (0 if not yet synced) */
  id: number;
  product_id: number;
  name: string;
  slug: string;
  sku: string;
  price: number;
  old_price: number | null;
  image: string;
  qty: number;
  stock_status: string;
}

export interface CartState {
  items: CartItem[];
  sessionToken: string;
  syncing: boolean;
  /** True once refreshFromAPI has completed at least once */
  initialized: boolean;
  error: string | null;
  cartModalOpen: boolean;
  openCartModal: () => void;
  closeCartModal: () => void;
  /** Adds product ONLY if not already in cart. Never creates duplicates. */
  addItem: (product: {
    id: number; name: string; slug: string;
    sku?: string; price: number; old_price?: number | null;
    image?: string; stock_status?: string;
  }) => Promise<void>;
  updateQuantity: (productId: number, qty: number) => Promise<void>;
  removeItem: (productId: number) => Promise<void>;
  clearCart: () => Promise<void>;
  refreshFromAPI: () => Promise<void>;
  initSession: () => void;
}

// ── Local helpers ──

function getSessionToken(): string {
  if (typeof window === 'undefined') return '';
  let tok = localStorage.getItem('cart_session_token');
  if (!tok) {
    tok = 'guest_' + crypto.randomUUID();
    localStorage.setItem('cart_session_token', tok);
  }
  return tok;
}

async function apiCart(path: string, options: RequestInit = {}): Promise<any> {
  const token = getSessionToken();
  const url = `/api/cart${path}${path.includes('?') ? '&' : '?'}session_token=${encodeURIComponent(token)}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(options.headers as Record<string, string>) },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Store ──

export const useCartStore = create<CartState>()(
  persist(
    (set, get) => ({
      items: [],
      sessionToken: '',
      syncing: false,
      initialized: false,
      error: null,
      cartModalOpen: false,

      openCartModal: () => set({ cartModalOpen: true }),
      closeCartModal: () => set({ cartModalOpen: false }),

      initSession: () => {
        const tok = getSessionToken();
        set({ sessionToken: tok });
      },

      addItem: async (product) => {
        const { items } = get();
        // ENSURE: never duplicate — if product already in cart, do nothing
        const existing = items.find((i) => i.product_id === product.id);
        if (existing) {
          // Already in cart — just open the modal, do not touch quantity
          get().openCartModal();
          return;
        }

        // Fresh add: create new cart line with qty 1
        const newItem: CartItem = {
          id: 0,
          product_id: product.id,
          name: product.name,
          slug: product.slug,
          sku: product.sku || '',
          price: product.price,
          old_price: product.old_price ?? null,
          image: product.image || '',
          qty: 1,
          stock_status: product.stock_status || 'in_stock',
        };
        set({ items: [...items, newItem], error: null });

        try {
          await apiCart('/items', {
            method: 'POST',
            body: JSON.stringify({ product_id: product.id, qty: 1 }),
          });
          await get().refreshFromAPI();
        } catch (e: any) {
          set({ error: e.message, items: items.filter((i) => i.product_id !== product.id) });
        }

        // Open cart modal after successful add
        get().openCartModal();
      },

      updateQuantity: async (productId, qty) => {
        const { items } = get();
        if (qty < 1) return get().removeItem(productId);
        const item = items.find((i) => i.product_id === productId);
        if (!item) return;
        const updated = items.map((i) =>
          i.product_id === productId ? { ...i, qty } : i,
        );
        set({ items: updated, error: null });
        try {
          if (item.id > 0) {
            await apiCart(`/items/${item.id}`, {
              method: 'PUT',
              body: JSON.stringify({ qty }),
            });
          } else {
            await apiCart('/items', {
              method: 'POST',
              body: JSON.stringify({ product_id: productId, qty }),
            });
          }
          await get().refreshFromAPI();
        } catch (e: any) {
          set({ error: e.message, items });
        }
      },

      removeItem: async (productId) => {
        const { items } = get();
        const item = items.find((i) => i.product_id === productId);
        if (!item) return;
        set({ items: items.filter((i) => i.product_id !== productId), error: null });
        try {
          if (item.id > 0) {
            await apiCart(`/items/${item.id}`, { method: 'DELETE' });
          }
        } catch (e: any) {
          set({ error: e.message, items });
        }
      },

      clearCart: async () => {
        const { items } = get();
        set({ items: [], error: null });
        try {
          for (const item of items) {
            if (item.id > 0) {
              await apiCart(`/items/${item.id}`, { method: 'DELETE' });
            }
          }
        } catch (e: any) {
          set({ error: e.message });
        }
      },

      refreshFromAPI: async () => {
        set({ syncing: true });
        try {
          const data = await apiCart('');
          const mapped: CartItem[] = (data.items || []).map((i: any) => ({
            id: i.id,
            product_id: i.product_id,
            name: i.name || '',
            slug: i.slug || '',
            sku: i.sku || '',
            price: i.price_at_addition ?? i.price ?? 0,
            old_price: i.old_price ?? null,
            image: i.image || '',
            qty: i.qty,
            stock_status: i.stock_status || 'in_stock',
          }));
          set({ items: mapped, sessionToken: data.session_token || get().sessionToken, syncing: false, initialized: true, error: null });
        } catch (e: any) {
          set({ syncing: false, initialized: true, error: e.message });
        }
      },
    }),
    {
      name: 'gadgeto-cart',
      partialize: (state) => ({
        items: state.items,
        sessionToken: state.sessionToken,
      }),
    },
  ),
);

// ── Selectors ──

export function useCartTotalItems(): number {
  const items = useCartStore((s) => s.items);
  return items.reduce((sum, i) => sum + i.qty, 0);
}

export function useCartSubtotal(): number {
  const items = useCartStore((s) => s.items);
  return items.reduce((sum, i) => sum + i.qty * i.price, 0);
}

/** Check if a given product is already in the cart (by product_id). */
export function useIsInCart(productId: number): boolean {
  return useCartStore((s) => s.items.some((i) => i.product_id === productId));
}

/** True while the cart is syncing with the backend (prevents button flicker). */
export function useCartSyncing(): boolean {
  return useCartStore((s) => s.syncing);
}

/** True once the cart has been fully initialized (hydrated + refreshed from API). */
export function useCartInitialized(): boolean {
  return useCartStore((s) => s.initialized);
}
