/**
 * First-party traffic-source attribution (first-touch + latest/session).
 * Persists to cookie `gadgeto_attr` (1y) + localStorage mirror.
 * UTM / gclid params take precedence over referrer inference.
 */

export interface TouchAttribution {
  source: string; medium: string; campaign: string; term: string;
  content: string; landing_page: string; gclid: string;
}

export interface OrderAttribution {
  first_source: string; first_medium: string; first_campaign: string;
  first_term: string; first_content: string; first_landing_page: string;
  first_gclid: string; last_source: string; last_medium: string;
  last_campaign: string; last_term: string; last_content: string;
  last_landing_page: string; last_gclid: string;
}

export const ATTRIBUTION_COOKIE = 'gadgeto_attr';
export const LS_FIRST_KEY = 'gadgeto_attr_first';
export const LS_LAST_KEY = 'gadgeto_attr_last';

const KNOWN_SEARCH = ['google.', 'bing.com', 'search.yahoo', 'duckduckgo.', 'ecosia.', 'yandex.', 'baidu.'];
const SOCIAL = ['facebook.', 'instagram.', 't.co', 'twitter.', 'x.com', 'linkedin.', 'tiktok.', 'youtube.', 'pinterest.'];

export function emptyTouch(): TouchAttribution {
  return { source: '', medium: '', campaign: '', term: '', content: '', landing_page: '', gclid: '' };
}

function safeHost(url: string): string {
  try { return new URL(url).hostname.toLowerCase(); } catch { return ''; }
}

export function readCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  for (const p of document.cookie.split(';')) {
    const [k, ...rest] = p.trim().split('=');
    if (k === name) return decodeURIComponent(rest.join('='));
  }
  return null;
}

export function writeCookie(name: string, value: string, days = 365): void {
  if (typeof document === 'undefined') return;
  const expires = new Date(Date.now() + days * 864e5).toUTCString();
  document.cookie = `${name}=${encodeURIComponent(value)}; expires=${expires}; path=/; SameSite=Lax`;
}

export function readLs(key: string): TouchAttribution | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as TouchAttribution) : null;
  } catch { return null; }
}

export function writeLs(key: string, touch: TouchAttribution): void {
  try { localStorage.setItem(key, JSON.stringify(touch)); } catch { /* ignore */ }
}

function isInternal(host: string): boolean {
  try {
    const self = window.location.hostname.toLowerCase();
    return !!host && (!!self && (host === self || host.endsWith(`.${self}`)));
  } catch { return false; }
}

export function classify(t: TouchAttribution): TouchAttribution {
  const out = { ...t };
  if (out.source) {
    if (!out.medium) out.medium = 'cpc';
    return out;
  }
  if (out.gclid) { out.source = 'google'; out.medium = 'cpc'; return out; }
  const ref = safeHost(typeof document !== 'undefined' ? document.referrer : '');
  if (ref && !isInternal(ref)) {
    if (ref.includes('google.')) { out.source = 'google'; out.medium = 'organic'; }
    else if (ref.includes('facebook.') || ref.includes('instagram.')) { out.source = 'facebook'; out.medium = 'social'; }
    else if (SOCIAL.some((h) => ref.includes(h))) { out.source = ref.split('.')[0]; out.medium = 'social'; }
    else if (KNOWN_SEARCH.some((h) => ref.includes(h))) { out.source = ref.split('.')[0]; out.medium = 'organic'; }
    else { out.source = ref; out.medium = 'referral'; }
    return out;
  }
  out.source = 'direct'; out.medium = 'none';
  return out;
}

/** Build the current-visit touch from URL params + referrer. */
export function currentTouch(): TouchAttribution {
  const t = emptyTouch();
  if (typeof window === 'undefined') return t;
  const params = new URLSearchParams(window.location.search);
  const get = (k: string) => (params.get(k) || '').trim().slice(0, 255);
  const utmSource = get('utm_source');
  const utmMedium = get('utm_medium');
  t.campaign = get('utm_campaign');
  t.term = get('utm_term');
  t.content = get('utm_content');
  t.gclid = (get('gclid') || get('gclsrc') || '').slice(0, 255);
  if (!t.content) t.content = get('fbclid') || get('msclkid') || get('ttclid') || get('yclid') || '';
  if (utmSource) t.source = utmSource.toLowerCase();
  if (utmMedium) t.medium = utmMedium.toLowerCase();
  if (!t.source && t.gclid) { t.source = 'google'; t.medium = t.medium || 'cpc'; }
  t.landing_page = (window.location.pathname + window.location.search).slice(0, 500);
  return classify(t);
}

function hasSignal(t: TouchAttribution): boolean {
  // Only paid/campaign/click signals refresh the session ("last") touch.
  // Plain same-site SPA navigations classify as direct/none and must NOT
  // overwrite the session touch — that is what preserves attribution
  // across product browsing, cart and checkout.
  if (t.gclid || t.campaign || t.term || t.content) return true;
  if (!t.source) return false;
  const s = t.source.toLowerCase();
  const m = (t.medium || '').toLowerCase();
  if (s === 'direct' && (m === 'none' || !m)) return false;
  return true;
}

export function toOrderAttribution(first: TouchAttribution, last: TouchAttribution): OrderAttribution {
  return {
    first_source: first.source, first_medium: first.medium,
    first_campaign: first.campaign, first_term: first.term,
    first_content: first.content, first_landing_page: first.landing_page,
    first_gclid: first.gclid, last_source: last.source,
    last_medium: last.medium, last_campaign: last.campaign,
    last_term: last.term, last_content: last.content,
    last_landing_page: last.landing_page, last_gclid: last.gclid,
  };
}

/** Capture attribution for this page view (see module docs). */
export function captureAttribution(): OrderAttribution | null {
  if (typeof window === 'undefined') return null;
  let first = readLs(LS_FIRST_KEY);
  if (!first) {
    const raw = readCookie(ATTRIBUTION_COOKIE);
    if (raw) { try { first = JSON.parse(raw) as TouchAttribution; } catch { first = null; } }
  }
  let last = readLs(LS_LAST_KEY);
  const now = currentTouch();
  const signal = hasSignal(now);
  if (!first) {
    first = now;
    writeLs(LS_FIRST_KEY, first);
    writeCookie(ATTRIBUTION_COOKIE, JSON.stringify(first));
  }
  if (!last || signal) {
    last = signal ? now : last || now;
    writeLs(LS_LAST_KEY, last as TouchAttribution);
  }
  return toOrderAttribution(first, last as TouchAttribution);
}

/** Snapshot sent with the order-create request. Never throws. */
export function getAttribution(): OrderAttribution {
  if (typeof window === 'undefined') {
    const e = emptyTouch();
    return toOrderAttribution(e, e);
  }
  try { captureAttribution(); } catch { /* ignore */ }
  const first = readLs(LS_FIRST_KEY) || emptyTouch();
  const last = readLs(LS_LAST_KEY) || first;
  return toOrderAttribution(first, last);
}
