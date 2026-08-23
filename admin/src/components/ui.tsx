'use client';

import React, { createContext, isValidElement, useCallback, useContext, useState } from 'react';

/* ------------------------------------------------------------------ */
/* Toast notifications                                                 */
/* ------------------------------------------------------------------ */

type ToastType = 'success' | 'error' | 'info';
type ToastItem = { id: number; type: ToastType; message: string };

const ToastCtx = createContext<{ push: (type: ToastType, message: string) => void }>({
  push: () => {},
});

export function useToast() {
  return useContext(ToastCtx);
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const push = useCallback((type: ToastType, message: string) => {
    const id = Date.now() + Math.random();
    setItems((prev) => [...prev, { id, type, message }]);
    setTimeout(() => setItems((prev) => prev.filter((t) => t.id !== id)), 4500);
  }, []);

  return (
    <ToastCtx.Provider value={{ push }}>
      {children}
      <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2 max-w-sm pointer-events-none">
        {items.map((t) => (
          <div
            key={t.id}
            className={`pointer-events-auto rounded-md px-4 py-3 text-sm shadow-lg border ${
              t.type === 'success'
                ? 'bg-green-50 border-green-200 text-green-800'
                : t.type === 'error'
                  ? 'bg-red-50 border-red-200 text-red-800'
                  : 'bg-gray-50 border-gray-200 text-gray-800'
            }`}
            role="status"
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

/* ------------------------------------------------------------------ */
/* Buttons                                                             */
/* ------------------------------------------------------------------ */

type BtnProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md';
  loading?: boolean;
};

export function Button({
  variant = 'primary',
  size = 'md',
  loading,
  className = '',
  children,
  disabled,
  ...rest
}: BtnProps) {
  const base =
    'inline-flex items-center justify-center gap-2 font-medium rounded-md transition disabled:opacity-50 disabled:cursor-not-allowed';
  const variants = {
    primary: 'bg-blue-600 text-white hover:bg-blue-700',
    secondary: 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50',
    danger: 'bg-red-600 text-white hover:bg-red-700',
    ghost: 'text-gray-600 hover:text-gray-900 hover:bg-gray-100',
  } as const;
  const sizes = { sm: 'px-2.5 py-1.5 text-xs', md: 'px-4 py-2 text-sm' } as const;
  return (
    <button
      className={`${base} ${variants[variant]} ${sizes[size]} ${className}`}
      disabled={disabled || loading}
      {...rest}
    >
      {loading && <Spinner size="sm" />}
      {children}
    </button>
  );
}

/* ------------------------------------------------------------------ */
/* Form controls                                                       */
/* ------------------------------------------------------------------ */

export function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: React.ReactNode;
  hint?: string;
}) {
  return (
    <label className="block">
      <span className="block text-xs font-medium text-gray-600 mb-1">{label}</span>
      {children}
      {hint && <span className="block text-xs text-gray-400 mt-1">{hint}</span>}
    </label>
  );
}

export const inputCls =
  'w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white';

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  const { className = '', ...rest } = props;
  return <input className={`${inputCls} ${className}`} {...rest} />;
}

export function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const { className = '', ...rest } = props;
  return <textarea className={`${inputCls} ${className}`} {...rest} />;
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  const { className = '', children, ...rest } = props;
  return (
    <select className={`${inputCls} ${className}`} {...rest}>
      {children}
    </select>
  );
}

/* ------------------------------------------------------------------ */
/* Spinner & page states                                               */
/* ------------------------------------------------------------------ */

export function Spinner({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const cls =
    size === 'sm'
      ? 'h-3.5 w-3.5 border-2'
      : size === 'lg'
        ? 'h-10 w-10 border-4'
        : 'h-6 w-6 border-2';
  return (
    <span
      className={`inline-block animate-spin rounded-full border-solid border-gray-300 border-t-blue-600 ${cls}`}
      aria-hidden
    />
  );
}

export function LoadingState({ label = 'Завантаження...' }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3 text-gray-500">
      <Spinner size="lg" />
      <span className="text-sm">{label}</span>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3 text-center">
      <div className="text-red-600 text-sm bg-red-50 border border-red-200 rounded-md px-4 py-3" role="alert">
        {message}
      </div>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Спробувати ще раз
        </Button>
      )}
    </div>
  );
}

export function EmptyState({
  title,
  hint,
  action,
}: {
  title: string;
  hint?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-2 text-center text-gray-500">
      <div className="text-3xl" aria-hidden>
        🗂️
      </div>
      <div className="font-medium text-gray-700">{title}</div>
      {hint && <div className="text-sm max-w-md">{hint}</div>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

const badgeTones = {
  gray: 'bg-gray-100 text-gray-700',
  green: 'bg-green-100 text-green-700',
  red: 'bg-red-100 text-red-700',
  blue: 'bg-blue-100 text-blue-700',
  yellow: 'bg-yellow-100 text-yellow-800',
} as const;

export function Badge({
  tone = 'gray',
  children,
}: {
  tone?: keyof typeof badgeTones;
  children: React.ReactNode;
}) {
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap ${badgeTones[tone]}`}>
      {children}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Table primitives                                                    */
/* ------------------------------------------------------------------ */

export function Table({
  head,
  children,
  tableClassName = '',
}: {
  head: React.ReactNode;
  children: React.ReactNode;
  /** Extra classes for the <table> element, e.g. "table-fixed min-w-[1280px]". */
  tableClassName?: string;
}) {
  // Callers pass a full <tr> here. Render its cells inside the single styled
  // header row so <thead> never ends up with nested <tr> elements — nested
  // rows produce invalid DOM and break header/body column alignment.
  const headIsRow =
    isValidElement<{ className?: string; children?: React.ReactNode }>(head) && head.type === 'tr';
  const headProps = headIsRow ? head.props : undefined;
  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-x-auto">
      <table className={`w-full text-sm ${tableClassName || 'min-w-[640px]'}`}>
        <thead>
          <tr
            className={`text-left text-xs uppercase tracking-wide text-gray-500 border-b border-gray-200 bg-gray-50 ${headProps?.className ?? ''}`}
          >
            {headProps ? headProps.children : head}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">{children}</tbody>
      </table>
    </div>
  );
}

export function Th({ children, className = '' }: { children?: React.ReactNode; className?: string }) {
  return <th className={`px-3 py-2.5 font-medium ${className}`}>{children}</th>;
}

export function Td({ children, className = '' }: { children?: React.ReactNode; className?: string }) {
  return <td className={`px-3 py-2.5 align-middle ${className}`}>{children}</td>;
}

/* ------------------------------------------------------------------ */
/* Pagination                                                          */
/* ------------------------------------------------------------------ */

type PageItem = number | '…';

/**
 * Builds the visible page list with an ellipsis strategy, e.g. for
 * page=15, pages=47 -> [1, '…', 13, 14, 15, 16, 17, '…', 47].
 */
function buildPageItems(page: number, pages: number): PageItem[] {
  const delta = 2;
  const wanted = new Set<number>([1, pages]);
  for (let p = page - delta; p <= page + delta; p++) {
    if (p >= 1 && p <= pages) wanted.add(p);
  }
  const items: PageItem[] = [];
  let prev = 0;
  for (const p of [...wanted].sort((a, b) => a - b)) {
    if (prev && p - prev > 1) items.push('…');
    items.push(p);
    prev = p;
  }
  return items;
}

export function Pagination({
  page,
  pages,
  total,
  onPage,
  onGoToPage,
  pageSize,
  onPageSizeChange,
  pageSizeOptions = [25, 50, 100],
}: {
  page: number;
  pages: number;
  total?: number;
  onPage: (p: number) => void;
  /** When provided, renders a compact "go to page" input (Enter submits). */
  onGoToPage?: (p: number) => void;
  /** When provided (with onPageSizeChange), renders a page-size selector. */
  pageSize?: number;
  onPageSizeChange?: (n: number) => void;
  pageSizeOptions?: number[];
}) {
  const [gotoValue, setGotoValue] = useState('');
  const [gotoInvalid, setGotoInvalid] = useState(false);

  const submitGoto = (e: React.FormEvent) => {
    e.preventDefault();
    if (!onGoToPage) return;
    const n = parseInt(gotoValue.trim(), 10);
    if (!Number.isFinite(n)) {
      setGotoInvalid(true); // non-numeric input — show error, don't navigate
      return;
    }
    // Clamp to the valid range so an out-of-range request never hits the API.
    onGoToPage(Math.min(Math.max(n, 1), pages));
    setGotoValue('');
    setGotoInvalid(false);
  };

  const info = (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-gray-500">
      <span>
        Сторінка {page} з {pages}
        {total !== undefined ? <> · Всього: {total.toLocaleString('uk-UA')}</> : null}
      </span>
      {onPageSizeChange && (
        <label className="flex items-center gap-1.5">
          Показувати:
          <select
            value={pageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
            className="px-2 py-1 text-xs border border-gray-300 rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {pageSizeOptions.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
      )}
      {onGoToPage && pages > 1 && (
        <form onSubmit={submitGoto} className="flex items-center gap-1.5">
          <label htmlFor="products-goto-page" className="whitespace-nowrap">
            До сторінки:
          </label>
          <input
            id="products-goto-page"
            type="text"
            inputMode="numeric"
            value={gotoValue}
            placeholder={String(page)}
            onChange={(e) => {
              setGotoValue(e.target.value.replace(/[^0-9]/g, ''));
              setGotoInvalid(false);
            }}
            className={`w-16 px-2 py-1 text-xs border rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 ${
              gotoInvalid ? 'border-red-400' : 'border-gray-300'
            }`}
          />
          <Button size="sm" variant="secondary" type="submit">
            Перейти
          </Button>
        </form>
      )}
    </div>
  );

  if (pages <= 1) {
    if (total === undefined && !onPageSizeChange && !onGoToPage) return null;
    return <div className="mt-3">{info}</div>;
  }

  return (
    <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
      {info}
      <div className="flex flex-wrap items-center gap-1">
        <Button size="sm" variant="secondary" disabled={page <= 1} onClick={() => onPage(1)}>
          Перша
        </Button>
        <Button size="sm" variant="secondary" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          Назад
        </Button>
        {buildPageItems(page, pages).map((it, i) =>
          it === '…' ? (
            <span key={`ellipsis-${i}`} className="px-1.5 text-xs text-gray-400 select-none" aria-hidden>
              …
            </span>
          ) : (
            <button
              key={it}
              type="button"
              onClick={() => onPage(it)}
              aria-current={it === page ? 'page' : undefined}
              className={`min-w-[32px] px-2 py-1.5 text-xs rounded-md border transition ${
                it === page
                  ? 'bg-blue-600 text-white border-blue-600 font-medium'
                  : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
              }`}
            >
              {it}
            </button>
          ),
        )}
        <Button size="sm" variant="secondary" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Далі
        </Button>
        <Button size="sm" variant="secondary" disabled={page >= pages} onClick={() => onPage(pages)}>
          Остання
        </Button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Modal & confirmation dialog                                         */
/* ------------------------------------------------------------------ */

export function Modal({
  open,
  title,
  onClose,
  children,
  wide,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  wide?: boolean;
}) {
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 md:p-8"
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div className={`bg-white rounded-lg shadow-xl w-full my-8 ${wide ? 'max-w-3xl' : 'max-w-lg'}`}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
          <h2 className="font-semibold text-gray-900">{title}</h2>
          <button
            onClick={onClose}
            aria-label="Закрити"
            className="text-gray-400 hover:text-gray-700 text-xl leading-none"
          >
            ×
          </button>
        </div>
        <div className="px-5 py-4">{children}</div>
      </div>
    </div>
  );
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Підтвердити',
  danger,
  busy,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  danger?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <Modal open={open} title={title} onClose={onCancel}>
      <p className="text-sm text-gray-600">{message}</p>
      <div className="flex justify-end gap-2 mt-5">
        <Button variant="secondary" onClick={onCancel}>
          Скасувати
        </Button>
        <Button variant={danger ? 'danger' : 'primary'} loading={busy} onClick={onConfirm}>
          {confirmLabel}
        </Button>
      </div>
    </Modal>
  );
}

export function PageHeader({ title, actions }: { title: string; actions?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
      <h2 className="text-xl font-bold text-gray-900">{title}</h2>
      {actions && <div className="flex items-center gap-2 flex-wrap">{actions}</div>}
    </div>
  );
}

