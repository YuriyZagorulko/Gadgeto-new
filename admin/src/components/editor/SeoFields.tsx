'use client';

import type { ChangeEvent } from 'react';

/**
 * SEO tab fields for the product editor.
 * Fully props-driven: the parent page owns state and persistence.
 */
export interface SeoData {
  seo_title: string;
  seo_description: string;
  focus_keyphrase: string;
  seo_canonical_url: string;
  og_title: string;
  og_description: string;
  og_image_url: string;
}

export const EMPTY_SEO: SeoData = {
  seo_title: '',
  seo_description: '',
  focus_keyphrase: '',
  seo_canonical_url: '',
  og_title: '',
  og_description: '',
  og_image_url: '',
};

const TITLE_LIMIT = 60;
const DESC_LIMIT = 160;

interface SeoFieldsProps {
  value: Partial<SeoData>;
  onChange: (v: SeoData) => void;
}

export default function SeoFields({ value, onChange }: SeoFieldsProps) {
  const v: SeoData = { ...EMPTY_SEO, ...value };

  const set =
    (key: keyof SeoData) =>
    (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      onChange({ ...v, [key]: e.target.value });

  return (
    <div className="space-y-5">
      <div>
        <label className="block text-sm font-medium mb-1">
          SEO заголовок{' '}
          <span className={`text-xs ${v.seo_title.length > TITLE_LIMIT ? 'text-red-500' : 'text-gray-400'}`}>
            {v.seo_title.length}/{TITLE_LIMIT}
          </span>
        </label>
        <input
          type="text"
          className="input-field w-full"
          value={v.seo_title}
          onChange={set('seo_title')}
          placeholder="Використовується в <title> та результатах пошуку"
        />
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">
          Мета-опис{' '}
          <span className={`text-xs ${v.seo_description.length > DESC_LIMIT ? 'text-red-500' : 'text-gray-400'}`}>
            {v.seo_description.length}/{DESC_LIMIT}
          </span>
        </label>
        <textarea
          className="input-field min-h-[80px] w-full"
          value={v.seo_description}
          onChange={set('seo_description')}
          placeholder="Короткий опис сторінки для пошукових систем"
        />
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">Ключова фраза</label>
        <input
          type="text"
          className="input-field w-full"
          value={v.focus_keyphrase}
          onChange={set('focus_keyphrase')}
          placeholder="напр. ноутбук asus vivobook"
        />
      </div>

      <div className="border-t pt-4">
        <h4 className="text-sm font-semibold mb-3">Open Graph / соціальні мережі</h4>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">OG заголовок</label>
            <input
              type="text"
              className="input-field w-full"
              value={v.og_title}
              onChange={set('og_title')}
              placeholder="Якщо порожньо — використовується назва товару"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">OG опис</label>
            <textarea
              className="input-field min-h-[60px] w-full"
              value={v.og_description}
              onChange={set('og_description')}
              placeholder="Якщо порожньо — використовується мета-опис"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">OG зображення (URL)</label>
            <input
              type="url"
              className="input-field w-full"
              value={v.og_image_url}
              onChange={set('og_image_url')}
              placeholder="https://..."
            />
            {v.og_image_url && (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img
                src={v.og_image_url}
                alt="OG preview"
                className="mt-2 h-24 rounded border border-gray-200 object-contain bg-white"
              />
            )}
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Canonical URL</label>
            <input
              type="url"
              className="input-field w-full"
              value={v.seo_canonical_url}
              onChange={set('seo_canonical_url')}
              placeholder="https://gadgeto.ua/product/slug (якщо відрізняється від стандартного)"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
