/**
 * Human-readable traffic-source labels for order attribution.
 * Latest/session attribution is shown; falls back to first-touch.
 */

interface Attributed {
  first_source?: string | null; first_medium?: string | null; first_campaign?: string | null;
  last_source?: string | null; last_medium?: string | null; last_campaign?: string | null;
}

function label(source?: string | null, medium?: string | null, campaign?: string | null): string {
  const s = (source || '').toLowerCase();
  const m = (medium || '').toLowerCase();
  if (!s) return '—';
  let base: string;
  if (s === 'direct' && (m === 'none' || !m)) base = 'Direct';
  else if (s === 'google' && m === 'cpc') base = 'Google / CPC';
  else if (s === 'google' && m === 'organic') base = 'Google / Organic';
  else if (s === 'facebook' && m === 'social') base = 'Facebook / Social';
  else if (m === 'referral') base = `${s} / Referral`;
  else if (m === 'social') base = `${s} / Social`;
  else if (m === 'organic') base = `${s} / Organic`;
  else if (m) base = `${s} / ${m}`;
  else base = s;
  // Title-case short labels for readability.
  base = base.replace(/^([a-z])/, (c) => c.toUpperCase());
  if (campaign) return `${base} · ${campaign}`;
  return base;
}

/** Latest/session label with first-touch fallback. */
export function formatAttribution(o: Attributed): string {
  const latest = label(o.last_source, o.last_medium, o.last_campaign);
  if (latest !== '—') return latest;
  return label(o.first_source, o.first_medium, o.first_campaign);
}

/** Full first-touch vs latest detail lines for the order detail page. */
export function attributionDetails(o: Attributed & Record<string, unknown>): { label: string; value: string }[] {
  const fields: [string, string][] = [
    ['First source', [o.first_source, o.first_medium].filter(Boolean).join(' / ') || '—'],
    ['First campaign', (o.first_campaign as string) || '—'],
    ['First term', (o.first_term as string) || '—'],
    ['First content', (o.first_content as string) || '—'],
    ['First landing page', (o.first_landing_page as string) || '—'],
    ['First gclid', (o.first_gclid as string) || '—'],
    ['Last source', [o.last_source, o.last_medium].filter(Boolean).join(' / ') || '—'],
    ['Last campaign', (o.last_campaign as string) || '—'],
    ['Last term', (o.last_term as string) || '—'],
    ['Last content', (o.last_content as string) || '—'],
    ['Last landing page', (o.last_landing_page as string) || '—'],
    ['Last gclid', (o.last_gclid as string) || '—'],
  ];
  return fields.map(([label, value]) => ({ label, value: String(value) }));
}
