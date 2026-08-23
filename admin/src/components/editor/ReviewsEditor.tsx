'use client';

export interface ReviewRow {
  key: string;
  id?: number; // existing product_reviews.id
  authorName: string;
  authorEmail?: string;
  rating: number;
  text: string;
  status: string; // published | pending | hidden
  createdAt?: string | null;
}

const STATUSES = [
  { value: 'published', label: 'Опубліковано' },
  { value: 'pending', label: 'На розгляді' },
  { value: 'hidden', label: 'Приховано' },
];

/** Product reviews manager: create/edit/delete reviews, change status & rating. */
export default function ReviewsEditor({
  reviews,
  onChange,
}: {
  reviews: ReviewRow[];
  onChange: (rows: ReviewRow[]) => void;
}) {
  const update = (key: string, patch: Partial<ReviewRow>) =>
    onChange(reviews.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  const remove = (key: string) => onChange(reviews.filter((r) => r.key !== key));
  const add = () =>
    onChange([
      {
        key: 'rev-' + Math.random().toString(36).slice(2),
        authorName: '',
        authorEmail: '',
        rating: 5,
        text: '',
        status: 'published',
        createdAt: null,
      },
      ...reviews,
    ]);

  return (
    <div className="space-y-4">
      <button type="button" onClick={add} className="btn-outline text-sm">
        + Додати відгук
      </button>

      {reviews.length === 0 && <p className="text-gray-500 text-sm">Відгуків ще немає.</p>}

      {reviews.map((r) => (
        <div key={r.key} className="card p-4 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Автор</label>
              <input
                className="input-field w-full"
                value={r.authorName}
                onChange={(e) => update(r.key, { authorName: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Електронна пошта</label>
              <input
                className="input-field w-full"
                value={r.authorEmail ?? ''}
                onChange={(e) => update(r.key, { authorEmail: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Оцінка</label>
              <select
                className="input-field w-full"
                value={r.rating}
                onChange={(e) => update(r.key, { rating: Number(e.target.value) })}
              >
                {[5, 4, 3, 2, 1].map((n) => (
                  <option key={n} value={n}>
                    {'★'.repeat(n)} ({n})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Статус</label>
              <select
                className="input-field w-full"
                value={r.status}
                onChange={(e) => update(r.key, { status: e.target.value })}
              >
                {STATUSES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Текст відгуку</label>
            <textarea
              className="input-field w-full"
              rows={2}
              value={r.text}
              onChange={(e) => update(r.key, { text: e.target.value })}
            />
          </div>
          <div className="text-right">
            <button type="button" onClick={() => remove(r.key)} className="text-red-400 hover:text-red-300 text-sm">
              Видалити
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
