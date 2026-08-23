'use client';

import { useState } from 'react';

export interface ReviewRow {
  key: string;
  id?: number;
  authorName: string;
  authorEmail?: string;
  rating: number;
  text: string;
  status: string;
  createdAt?: string | null;
}

const STATUSES = [
  { value: 'published', label: 'Опубліковано' },
  { value: 'pending', label: 'На розгляді' },
  { value: 'hidden', label: 'Приховано' },
];

export default function ReviewsEditor({
  reviews,
  onChange,
  productId,
}: {
  reviews: ReviewRow[];
  onChange: (rows: ReviewRow[]) => void;
  productId?: number;
}) {
  const [moderating, setModerating] = useState<Record<string, boolean>>({});

  const moderate = async (key: string, id: number | undefined, status: string) => {
    if (!productId || !id) return;
    setModerating((m) => ({ ...m, [key]: true }));
    try {
      const t = localStorage.getItem('admin_token') || localStorage.getItem('auth_token') || '';
      await fetch('/api/products/' + productId + '/reviews/' + id + '/moderate', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + t },
        body: JSON.stringify({ status }),
      });
      onChange(reviews.map((r) => (r.key === key ? { ...r, status } : r)));
    } catch { /* ignore */ } finally {
      setModerating((m) => ({ ...m, [key]: false }));
    }
  };

  const update = (key: string, patch: Partial<ReviewRow>) =>
    onChange(reviews.map((r) => (r.key === key ? { ...r, ...patch } : r)));

  const remove = (key: string, id?: number) => {
    if (productId && id) {
      const t = localStorage.getItem('admin_token') || localStorage.getItem('auth_token') || '';
      fetch('/api/products/' + productId + '/reviews/' + id, { method: 'DELETE', headers: { Authorization: 'Bearer ' + t } }).catch(() => {});
    }
    onChange(reviews.filter((r) => r.key !== key));
  };

  return (
    <div className="space-y-4">
      {reviews.length === 0 && <p className="text-gray-500 text-sm">Відгуків ще не надходило.</p>}

      {reviews.map((r) => {
        const isPending = r.status === 'pending';
        return (
          <div key={r.key} className="rounded-lg border border-gray-700 bg-gray-900 p-4 space-y-3">
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <div className="flex items-center gap-2">
                <span className="text-yellow-400 text-sm">{'★'.repeat(r.rating)}{'☆'.repeat(5 - r.rating)}</span>
                <span className="text-sm font-medium text-gray-200">{r.authorName}</span>
                {r.createdAt && <span className="text-xs text-gray-500">{new Date(r.createdAt).toLocaleDateString('uk-UA')}</span>}
              </div>
              <div className="flex items-center gap-2">
                {isPending && (
                  <>
                    <button type="button" disabled={moderating[r.key]} onClick={() => moderate(r.key, r.id, 'published')}
                      className="rounded bg-green-700 px-2 py-1 text-xs text-white hover:bg-green-600 disabled:opacity-40">
                      {moderating[r.key] ? '…' : 'Схвалити'}
                    </button>
                    <button type="button" disabled={moderating[r.key]} onClick={() => moderate(r.key, r.id, 'hidden')}
                      className="rounded bg-red-700 px-2 py-1 text-xs text-white hover:bg-red-600 disabled:opacity-40">
                      {moderating[r.key] ? '…' : 'Відхилити'}
                    </button>
                  </>
                )}
                {!isPending && (
                  <select className="rounded border border-gray-600 bg-gray-800 px-2 py-1 text-xs text-gray-300"
                    value={r.status} onChange={(e) => moderate(r.key, r.id, e.target.value)}>
                    {STATUSES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
                  </select>
                )}
                <button type="button" onClick={() => remove(r.key, r.id)}
                  className="rounded px-2 py-1 text-xs text-red-400 hover:bg-red-900/30" title="Видалити">
                  ✕
                </button>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Ім'я автора</label>
                <input className="input-field w-full" value={r.authorName}
                  onChange={(e) => update(r.key, { authorName: e.target.value })} />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Email</label>
                <input className="input-field w-full" value={r.authorEmail ?? ''}
                  onChange={(e) => update(r.key, { authorEmail: e.target.value })} />
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Оцінка</label>
                <select className="input-field w-full" value={r.rating}
                  onChange={(e) => update(r.key, { rating: Number(e.target.value) })}>
                  {[5,4,3,2,1].map((n) => <option key={n} value={n}>{'★'.repeat(n)} ({n})</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Статус</label>
                <div className="text-sm text-gray-300 pt-1.5">{STATUSES.find(s => s.value === r.status)?.label ?? r.status}</div>
              </div>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Текст відгуку</label>
              <textarea className="input-field w-full" rows={2} value={r.text}
                onChange={(e) => update(r.key, { text: e.target.value })} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
