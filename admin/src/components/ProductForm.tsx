'use client';

import { useEffect, useState } from 'react';
import { api, qs } from '@/lib/api';
import { PRODUCT_STATUSES, PRODUCT_STATUS_LABELS, STOCK_STATUSES, STOCK_STATUS_LABELS } from '@/lib/format';
import { Button, Field, Input, Select, Textarea, LoadingState, ErrorState } from '@/components/ui';

type CatOpt = { id: number; name: string; parent_id: number | null };
type BrandOpt = { id: number; name: string };

export type ProductFormValues = {
  name: string; slug: string; sku: string;
  price: string; old_price: string; stock_qty: string;
  stock_status: string; status: string; brand_id: string;
  short_description: string; description: string;
  seo_title: string; seo_description: string; focus_keyphrase: string;
  category_ids: number[];
};

const EMPTY: ProductFormValues = {
  name: '', slug: '', sku: '', price: '', old_price: '', stock_qty: '0',
  stock_status: 'in_stock', status: 'DRAFT', brand_id: '',
  short_description: '', description: '', seo_title: '', seo_description: '',
  focus_keyphrase: '', category_ids: [],
};

const money = (kop: number | null | undefined) => (kop === null || kop === undefined ? '' : String(kop / 100));

/**
 * Create/edit product form.
 * Prices are entered in hryvnyas and stored as integer kopiykas.
 */
export function useProductForm(id?: number) {
  const [values, setValues] = useState<ProductFormValues>(EMPTY);
  const [cats, setCats] = useState<CatOpt[]>([]);
  const [brands, setBrands] = useState<BrandOpt[]>([]);
  const [loading, setLoading] = useState(!!id);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get<{ items: CatOpt[] }>('/categories').then((d) => setCats(d.items || [])).catch(() => {});
    api.get<{ items: BrandOpt[] }>('/brands' + qs({ per_page: 100 })).then((d) => setBrands(d.items || [])).catch(() => {});
    if (!id) return;
    api.get<Record<string, unknown>>(`/products/${id}`)
      .then((p) => {
        const prod = (p.product ?? p) as Record<string, unknown>;
        const linked = ((p.categories ?? p.cats ?? []) as Array<{ id: number }>).map((c) => c.id);
        setValues((v) => ({
          ...v,
          name: String(prod.name ?? ''), slug: String(prod.slug ?? ''), sku: String(prod.sku ?? ''),
          price: money(prod.price as number), old_price: money(prod.old_price as number),
          stock_qty: String(prod.stock_qty ?? 0), stock_status: String(prod.stock_status ?? 'in_stock'),
          status: String(prod.status ?? 'DRAFT'), brand_id: prod.brand_id ? String(prod.brand_id) : '',
          short_description: String(prod.short_description ?? ''), description: String(prod.description ?? ''),
          seo_title: String(prod.seo_title ?? ''), seo_description: String(prod.seo_description ?? ''),
          focus_keyphrase: String(prod.focus_keyphrase ?? ''),
          category_ids: linked,
        }));
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  const set = <K extends keyof ProductFormValues>(key: K, value: ProductFormValues[K]) =>
    setValues((v) => ({ ...v, [key]: value }));

  const toggleCategory = (cid: number) =>
    setValues((v) => ({
      ...v,
      category_ids: v.category_ids.includes(cid)
        ? v.category_ids.filter((c) => c !== cid)
        : [...v.category_ids, cid],
    }));

  /** Serializes the form into the API payload (kopiykas, nulls trimmed). */
  const payload = () => {
    const num = (s: string) => (s.trim() === '' ? null : Math.round(parseFloat(s.replace(',', '.')) * 100));
    return {
      name: values.name.trim(),
      slug: values.slug.trim() || undefined,
      sku: values.sku.trim() || null,
      price: num(values.price),
      old_price: num(values.old_price),
      stock_qty: values.stock_qty === '' ? null : parseInt(values.stock_qty, 10),
      stock_status: values.stock_status,
      status: values.status,
      brand_id: values.brand_id === '' ? null : Number(values.brand_id),
      short_description: values.short_description.trim() || null,
      description: values.description.trim() || null,
      seo_title: values.seo_title.trim() || null,
      seo_description: values.seo_description.trim() || null,
      focus_keyphrase: values.focus_keyphrase.trim() || null,
      category_ids: values.category_ids,
    };
  };

  return { values, set, toggleCategory, cats, brands, loading, error, payload };
}

/** Visual form bound to {@link useProductForm} state. */
export function ProductFormFields({
  values, set, toggleCategory, cats, brands,
}: ReturnType<typeof useProductForm>) {
  const catLabel = (c: CatOpt, all: CatOpt[]): string => {
    const parent = c.parent_id ? all.find((p) => p.id === c.parent_id) : null;
    return parent ? `${parent.name} → ${c.name}` : c.name;
  };
  const sortedCats = [...cats].sort((a, b) => catLabel(a, cats).localeCompare(catLabel(b, cats), 'uk'));

  return (
    <div className="space-y-4">
      <div className="bg-white border border-gray-200 rounded-lg p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
        <Field label="Назва товару *" >
          <Input value={values.name} onChange={(e) => set('name', e.target.value)} required />
        </Field>
        <Field label="Артикул (SKU)">
          <Input value={values.sku} onChange={(e) => set('sku', e.target.value)} />
        </Field>
        <Field label="Slug (URL)" hint="Залиште порожнім — згенерується автоматично">
          <Input value={values.slug} onChange={(e) => set('slug', e.target.value)} />
        </Field>
        <Field label="Бренд">
          <Select value={values.brand_id} onChange={(e) => set('brand_id', e.target.value)}>
            <option value="">— Без бренду —</option>
            {brands.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </Select>
        </Field>
        <Field label="Ціна, ₴">
          <Input type="number" step="0.01" min="0" value={values.price} onChange={(e) => set('price', e.target.value)} />
        </Field>
        <Field label="Стара ціна, ₴">
          <Input type="number" step="0.01" min="0" value={values.old_price} onChange={(e) => set('old_price', e.target.value)} />
        </Field>
        <Field label="Залишок, шт.">
          <Input type="number" min="0" value={values.stock_qty} onChange={(e) => set('stock_qty', e.target.value)} />
        </Field>
        <Field label="Статус наявності">
          <Select value={values.stock_status} onChange={(e) => set('stock_status', e.target.value)}>
            {STOCK_STATUSES.map((s) => <option key={s} value={s}>{STOCK_STATUS_LABELS[s]}</option>)}
          </Select>
        </Field>
        <Field label="Статус публікації">
          <Select value={values.status} onChange={(e) => set('status', e.target.value)}>
            {PRODUCT_STATUSES.map((s) => <option key={s} value={s}>{PRODUCT_STATUS_LABELS[s]}</option>)}
          </Select>
        </Field>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-4">
        <Field label="Короткий опис">
          <Textarea rows={2} value={values.short_description} onChange={(e) => set('short_description', e.target.value)} />
        </Field>
        <Field label="Повний опис">
          <Textarea rows={6} value={values.description} onChange={(e) => set('description', e.target.value)} />
        </Field>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <div className="text-sm font-medium text-gray-700 mb-2">Категорії</div>
        {sortedCats.length === 0 && <p className="text-sm text-gray-400">Категорії не завантажено</p>}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-1 max-h-56 overflow-y-auto">
          {sortedCats.map((c) => (
            <label key={c.id} className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer hover:bg-gray-50 rounded px-1 py-0.5">
              <input type="checkbox" className="rounded" checked={values.category_ids.includes(c.id)} onChange={() => toggleCategory(c.id)} />
              <span className="truncate">{catLabel(c, cats)}</span>
            </label>
          ))}
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-4 grid grid-cols-1 md:grid-cols-3 gap-4">
        <Field label="SEO заголовок"><Input value={values.seo_title} onChange={(e) => set('seo_title', e.target.value)} /></Field>
        <Field label="SEO опис"><Textarea rows={2} value={values.seo_description} onChange={(e) => set('seo_description', e.target.value)} /></Field>
        <Field label="Ключова фраза"><Input value={values.focus_keyphrase} onChange={(e) => set('focus_keyphrase', e.target.value)} /></Field>
      </div>
    </div>
  );
}
/* PART3 */

