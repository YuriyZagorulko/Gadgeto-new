'use client';

import { useState } from 'react';

export interface EditorImage {
  id?: number;
  url: string;
  is_primary?: boolean;
  sort_order?: number;
}

/**
 * WooCommerce-style gallery manager (controlled).
 * Drag & drop to reorder, click to set featured, paste URL to add.
 */
export default function ImageManager({
  images,
  onChange,
}: {
  images: EditorImage[];
  onChange: (next: EditorImage[]) => void;
}) {
  const [url, setUrl] = useState('');
  const [dragIdx, setDragIdx] = useState<number | null>(null);

  const add = () => {
    const u = url.trim();
    if (!u) return;
    const next = [...images, { url: u, is_primary: images.length === 0 }];
    onChange(next);
    setUrl('');
  };

  const remove = (i: number) => {
    const next = images.filter((_, idx) => idx !== i);
    if (images[i]?.is_primary && next.length > 0) next[0] = { ...next[0], is_primary: true };
    onChange(next);
  };

  const makePrimary = (i: number) => {
    onChange(images.map((im, idx) => ({ ...im, is_primary: idx === i })));
  };

  const moveTo = (from: number, to: number) => {
    if (to < 0 || to >= images.length || from === to) return;
    const next = [...images];
    const [item] = next.splice(from, 1);
    next.splice(to, 0, item);
    onChange(next);
  };

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), add())}
          placeholder="https://… URL зображення"
          className="flex-1 rounded border border-gray-300 bg-white px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        />
        <button type="button" onClick={add} className="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700">
          Додати
        </button>
      </div>

      {images.length === 0 ? (
        <p className="text-sm text-gray-500">Зображень немає. Додайте перше за URL.</p>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-5">
          {images.map((img, i) => (
            <div
              key={`${img.url}-${i}`}
              draggable
              onDragStart={() => setDragIdx(i)}
              onDragOver={(e) => e.preventDefault()}
              onDrop={() => { if (dragIdx !== null) moveTo(dragIdx, i); setDragIdx(null); }}
              className={`group relative overflow-hidden rounded border-2 bg-gray-100 ${
                img.is_primary ? 'border-blue-600' : 'border-transparent'
              }`}
              title={img.url}
            >
              <img src={img.url} alt="" className="aspect-square w-full object-cover" loading="lazy" />
              <div className="absolute inset-x-0 bottom-0 flex items-center justify-between bg-black/60 px-1 py-0.5 opacity-0 transition group-hover:opacity-100">
                <div className="flex gap-1">
                  <button type="button" onClick={() => moveTo(i, i - 1)} disabled={i === 0}
                    className="px-1 text-xs text-white disabled:opacity-30">←</button>
                  <button type="button" onClick={() => moveTo(i, i + 1)} disabled={i === images.length - 1}
                    className="px-1 text-xs text-white disabled:opacity-30">→</button>
                </div>
                <div className="flex gap-1">
                  {!img.is_primary && (
                    <button type="button" onClick={() => makePrimary(i)}
                      className="px-1 text-xs text-yellow-300" title="Зробити головним">★</button>
                  )}
                  <button type="button" onClick={() => remove(i)}
                    className="px-1 text-xs text-red-400" title="Видалити">✕</button>
                </div>
              </div>
              {img.is_primary && (
                <span className="absolute left-1 top-1 rounded bg-blue-600 px-1 text-[10px] font-semibold text-white">
                  Головне
                </span>
              )}
            </div>
          ))}
        </div>
      )}
      <p className="text-xs text-gray-400">Перетягніть, щоб змінити порядок. ★ — головне зображення.</p>
    </div>
  );
}
