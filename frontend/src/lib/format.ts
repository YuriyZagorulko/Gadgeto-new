/** Formats a minor-unit amount (kopiykas) as a UAH price string for the locale. */
export function formatPrice(amountMinor: number, locale: string): string {
  const value = (amountMinor || 0) / 100;
  return new Intl.NumberFormat(locale === 'en' ? 'en' : 'uk-UA', {
    style: 'currency',
    currency: 'UAH',
    currencyDisplay: 'narrowSymbol',
  }).format(value);
}

/** Formats a date string according to the active locale. */
export function formatDate(value: string | number | Date, locale: string): string {
  return new Date(value).toLocaleDateString(locale === 'en' ? 'en-GB' : 'uk-UA');
}
