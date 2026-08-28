'use client';

import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';

/**
 * Catalog sorting select. URL-driven: sets/replaces `sort`, resets `page`,
 * keeps every other filter parameter.
 */
export default function SortSelect({
  basePath,
  params,
  value,
}: {
  basePath: string;
  params: Record<string, string>;
  value: string;
}) {
  const t = useTranslations('filters');
  const router = useRouter();

  const options: [string, string][] = [
    ['', t('sortDefault')],
    ['price_asc', t('sortPriceAsc')],
    ['price_desc', t('sortPriceDesc')],
    ['name', t('sortName')],
    ['newest', t('sortNewest')],
  ];

  return (
    <label className="flex items-center gap-2 text-sm text-gray-600">
      {t('sort')}
      <select
        className="input-field w-auto py-1.5"
        value={value}
        onChange={(e) => {
          const sp = new URLSearchParams(params);
          if (e.target.value) sp.set('sort', e.target.value);
          else sp.delete('sort');
          sp.delete('page');
          const qs = sp.toString();
          router.push(qs ? `${basePath}?${qs}` : basePath, { scroll: false });
        }}
      >
        {options.map(([v, label]) => (
          <option key={v || 'default'} value={v}>
            {label}
          </option>
        ))}
      </select>
    </label>
  );
}
