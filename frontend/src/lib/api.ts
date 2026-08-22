/**
 * API client for Gadgeto storefront.
 * Communicates with the FastAPI backend.
 */
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

interface FetchOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
}

async function fetchAPI(path: string, options: FetchOptions = {}) {
  const { params, ...fetchOpts } = options;
  let url = `${API_BASE}${path}`;
  
  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null) {
        searchParams.set(key, String(val));
      }
    });
    const qs = searchParams.toString();
    if (qs) url += `?${qs}`;
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(fetchOpts.headers as Record<string, string>),
  };

  // Include auth token if available
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("auth_token");
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(url, { ...fetchOpts, headers });
  
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `HTTP ${res.status}`);
  }
  
  return res.json();
}

// ── Catalog ──

export async function getCategoryTree() {
  return fetchAPI("/categories");
}

export async function getCategory(slug: string) {
  return fetchAPI(`/categories/${encodeURIComponent(slug)}`);
}

export async function getCategoryFilters(slug: string) {
  return fetchAPI(`/categories/${encodeURIComponent(slug)}/filters`);
}

export async function getProducts(params: Record<string, any> = {}) {
  return fetchAPI("/products", { params });
}

export async function getProduct(slug: string) {
  return fetchAPI(`/products/${encodeURIComponent(slug)}`);
}

export async function searchProducts(params: Record<string, any> = {}) {
  return fetchAPI("/search", { params });
}

// ── Cart ──

export async function getCart() {
  return fetchAPI("/cart");
}

export async function addToCart(productId: number, qty: number = 1) {
  return fetchAPI("/cart/items", {
    method: "POST",
    body: JSON.stringify({ product_id: productId, qty }),
  });
}

export async function updateCartItem(itemId: number, qty: number) {
  return fetchAPI(`/cart/items/${itemId}`, {
    method: "PUT",
    body: JSON.stringify({ qty }),
  });
}

export async function removeCartItem(itemId: number) {
  return fetchAPI(`/cart/items/${itemId}`, { method: "DELETE" });
}

// ── Auth ──

export async function register(data: { email: string; password: string; full_name: string }) {
  return fetchAPI("/auth/register", { method: "POST", body: JSON.stringify(data) });
}

export async function login(data: { email: string; password: string }) {
  return fetchAPI("/auth/login", { method: "POST", body: JSON.stringify(data) });
}

export async function getMe() {
  return fetchAPI("/auth/me");
}

// ── Orders ──

export async function createOrder(data: any) {
  return fetchAPI("/orders", { method: "POST", body: JSON.stringify(data) });
}

export async function getOrders(params: Record<string, any> = {}) {
  return fetchAPI("/orders", { params });
}

export async function getOrder(id: number) {
  return fetchAPI(`/orders/${id}`);
}

// ── Shipping ──

export async function getCities() {
  return fetchAPI("/shipping/cities");
}

export async function getWarehouses(cityRef: string) {
  return fetchAPI(`/shipping/branches`, { params: { city_ref: cityRef } });
}