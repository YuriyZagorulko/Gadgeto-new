'use client';

import React, { createContext, useCallback, useContext, useState } from 'react';

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

export function Table({ head, children }: { head: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-x-auto">
      <table className="w-full text-sm min-w-[640px]">
        <thead>
          <tr className="text-left text-xs uppercase tracking-wide text-gray-500 border-b border-gray-200 bg-gray-50">
            {head}
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

export function Pagination({
  page,
  pages,
  total,
  onPage,
}: {
  page: number;
  pages: number;
  total?: number;
  onPage: (p: number) => void;
}) {
  if (pages <= 1) {
    return total !== undefined ? (
      <div className="text-sm text-gray-500 mt-3">Всього: {total}</div>
    ) : null;
  }
  const win = 2;
  const nums: number[] = [];
  for (let p = Math.max(1, page - win); p <= Math.min(pages, page + win); p++) nums.push(p);
  return (
    <div className="flex items-center justify-between mt-3 flex-wrap gap-2">
      <div className="text-sm text-gray-500">
        Сторінка {page} з {pages}
        {total !== undefined ? ` · Всього: ${total}` : ''}
      </div>
      <div className="flex items-center gap-1">
        <Button size="sm" variant="secondary" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          Назад
        </Button>
        {nums.map((n) => (
          <button
            key={n}
            type="button"
            onClick={() => onPage(n)}
            className={`min-w-[32px] px-2 py-1.5 text-xs rounded-md border transition ${
              n === page
                ? 'bg-blue-600 text-white border-blue-600'
                : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
            }`}
          >
            {n}
          </button>
        ))}
        <Button size="sm" variant="secondary" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Далі
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

