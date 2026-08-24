/** Shared formatting helpers and Ukrainian label maps (admin UI). */

export function formatPrice(amountMinor?: number | null): string {
  const v = (amountMinor || 0) / 100;
  return new Intl.NumberFormat('uk-UA', {
    style: 'currency',
    currency: 'UAH',
    currencyDisplay: 'narrowSymbol',
    maximumFractionDigits: v % 1 === 0 ? 0 : 2,
  }).format(v);
}

export function formatDateTime(value?: string | null): string {
  if (!value) return '—';
  const d = new Date(value);
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleString('uk-UA', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

export function formatDate(value?: string | null): string {
  if (!value) return '—';
  const d = new Date(value);
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleDateString('uk-UA');
}

export const PRODUCT_STATUS_LABELS: Record<string, string> = {
  DRAFT: 'Чернетка',
  PUBLISHED: 'Опубліковано',
  HIDDEN: 'Приховано',
  ARCHIVED: 'Архів',
};
export const PRODUCT_STATUSES = Object.keys(PRODUCT_STATUS_LABELS);

export const STOCK_STATUS_LABELS: Record<string, string> = {
  in_stock: 'В наявності',
  out_of_stock: 'Немає в наявності',
  pre_order: 'Під замовлення',
};
export const STOCK_STATUSES = Object.keys(STOCK_STATUS_LABELS);

export const ORDER_STATUS_LABELS: Record<string, string> = {
  PENDING: 'Очікує підтвердження',
  PROCESSING: 'В обробці',
  PAID: 'Оплачено',
  SHIPPED: 'Відправлено',
  DELIVERED: 'Доставлено',
  CANCELLED: 'Скасовано',
  REFUNDED: 'Повернуто',
};
export const ORDER_STATUSES = Object.keys(ORDER_STATUS_LABELS);

export const PAYMENT_STATUS_LABELS: Record<string, string> = {
  pending: 'Очікує оплати',
  paid: 'Оплачено',
  failed: 'Помилка оплати',
  refunded: 'Повернено',
};

export const USER_ROLE_LABELS: Record<string, string> = {
  CUSTOMER: 'Покупець',
  STAFF: 'Персонал',
  ADMIN: 'Адміністратор',
};

export const USER_STATUS_LABELS: Record<string, string> = {
  ACTIVE: 'Активний',
  INACTIVE: 'Неактивний',
  PENDING: 'Очікує підтвердження',
  BANNED: 'Заблокований',
};

export const IMPORT_STATUS_LABELS: Record<string, string> = {
  queued: 'У черзі',
  running: 'Виконується',
  succeeded: 'Завершено',
  failed: 'Помилка',
  aborted: 'Перервано',
  stale: 'Зависло',
  cancelled: 'Скасовано',
};

export type BadgeTone = 'green' | 'red' | 'gray' | 'blue' | 'yellow';

export function orderStatusTone(s: string): BadgeTone {
  switch (s) {
    case 'PENDING': return 'yellow';
    case 'PROCESSING': return 'blue';
    case 'PAID': case 'SHIPPED': case 'DELIVERED': return 'green';
    case 'CANCELLED': case 'REFUNDED': return 'red';
    default: return 'gray';
  }
}

export function importStatusTone(s: string): BadgeTone {
  switch (s) {
    case 'succeeded': return 'green';
    case 'running': case 'queued': return 'blue';
    case 'stale': return 'yellow';
    case 'failed': case 'aborted': return 'red';
    case 'cancelled': return 'gray';
    default: return 'gray';
  }
}
