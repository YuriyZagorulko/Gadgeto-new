/**
 * API client for Gadgeto storefront.
 * Communicates with the FastAPI backend.
 */
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

interface FetchOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
}

async function request(path: string, base: string, options: FetchOptions = {}) {
  const { params, ...fetchOpts } = options;
  let url = `${base}${path}`;

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

async function fetchAPI(path: string, options: FetchOptions = {}) {
  return request(path, API_BASE, options);
}

/**
 * Same contract as fetchAPI, but always uses a relative `/api/...` URL that
 * goes through the Next.js rewrite (`/api/:path*` →
 * `${NEXT_PUBLIC_API_URL}/api/v1/:path*`). The rewrite target is resolved
 * server-side, inside the docker network, where the backend hostname is
 * reachable — so this works in the browser even when NEXT_PUBLIC_API_URL
 * points at a docker-internal hostname. cart-store uses the same pattern.
 */
async function fetchAPIViaRewrite(path: string, options: FetchOptions = {}) {
  return request(path, "/api", options);
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

export interface NPCity {
  ref: string;
  name: string;
  area?: string;
  region?: string;
}

export interface NPWarehouse {
  ref: string;
  number: string;
  address: string;
  short_address: string;
  phone: string;
  max_weight: string;
}

export interface NPCitiesResponse {
  items: NPCity[];
  error?: string;
}

export interface NPBranchesResponse {
  items: NPWarehouse[];
  error?: string;
}

export async function getCities(search: string = ""): Promise<NPCitiesResponse> {
  return fetchAPIViaRewrite("/shipping/cities", { params: { search, limit: 50 } });
}

export async function getWarehouses(cityRef: string, search: string = ""): Promise<NPBranchesResponse> {
  return fetchAPIViaRewrite(`/shipping/branches`, { params: { city_ref: cityRef, search } });
}

export interface NPStreet {
  ref: string;
  name: string;
  street_type: string;
}

export interface NPStreetsResponse {
  items: NPStreet[];
  error?: string;
}

export async function getStreets(cityRef: string, search: string = ""): Promise<NPStreetsResponse> {
  return fetchAPIViaRewrite(`/shipping/streets`, { params: { city_ref: cityRef, search } });
}
