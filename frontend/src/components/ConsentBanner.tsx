'use client';

import { useEffect, useState } from 'react';

const CONSENT_KEY = 'gadgeto_consent';
const CONSENT_EVENT = 'gadgeto-consent-changed';

export type ConsentState = 'accepted' | 'declined' | null;

export function getConsent(): ConsentState {
  if (typeof window === 'undefined') return null;
  try {
    const v = localStorage.getItem(CONSENT_KEY);
    return v === 'accepted' || v === 'declined' ? v : null;
  } catch { return null; }
}

function pushConsentUpdate(state: 'accepted' | 'declined'): void {
  if (typeof window === 'undefined') return;
  window.dataLayer = window.dataLayer || [];
  window.dataLayer.push({
    event: 'consent_update',
    analytics_consent: state === 'accepted' ? 'granted' : 'denied',
  });
  window.dispatchEvent(new CustomEvent(CONSENT_EVENT, { detail: state }));
}

function saveConsent(state: 'accepted' | 'declined'): void {
  try { localStorage.setItem(CONSENT_KEY, state); } catch { /* ignore */ }
  pushConsentUpdate(state);
}

/**
 * Single cookie/consent banner for the storefront. No other consent
 * mechanism exists — integrate tracking consent here, not elsewhere.
 * GTM Consent Mode defaults to denied until the visitor chooses.
 */
export default function ConsentBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    setVisible(getConsent() === null);
    const onChange = () => setVisible(false);
    window.addEventListener(CONSENT_EVENT, onChange);
    return () => window.removeEventListener(CONSENT_EVENT, onChange);
  }, []);

  if (!visible) return null;

  return (
    <div
      role="dialog"
      aria-live="polite"
      aria-label="Cookie consent"
      className="fixed bottom-0 inset-x-0 z-[90] px-4 pb-4"
    >
      <div className="max-w-3xl mx-auto bg-white border border-gray-200 rounded-lg shadow-xl p-4 flex flex-col sm:flex-row gap-3 items-start sm:items-center">
        <p className="text-sm text-gray-600 flex-1">
          Ми використовуємо файли cookie для аналітики та покращення сервісу.
        </p>
        <div className="flex gap-2 shrink-0">
          <button
            type="button"
            onClick={() => saveConsent('declined')}
            className="px-4 py-2 text-sm rounded-lg border border-gray-300 text-gray-700 hover:border-gray-400"
          >
            Відхилити
          </button>
          <button
            type="button"
            onClick={() => saveConsent('accepted')}
            className="px-4 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700"
          >
            Прийняти
          </button>
        </div>
      </div>
    </div>
  );
}

export { saveConsent };
