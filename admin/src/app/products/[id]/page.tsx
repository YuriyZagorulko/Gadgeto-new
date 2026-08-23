'use client';

import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import CategorySelect from '@/components/CategorySelect';
import ImageManager from '@/components/editor/ImageManager';
import CustomFieldsEditor from '@/components/editor/CustomFieldsEditor';
import AttributesEditor from '@/components/editor/AttributesEditor';
import VariationsEditor from '@/components/editor/VariationsEditor';
import ReviewsEditor from '@/components/editor/ReviewsEditor';
import SeoFields from '@/components/editor/SeoFields';
import type { CustomField } from '@/components/editor/CustomFieldsEditor';
import type { AttrRow } from '@/components/editor/AttributesEditor';
import type { VariationRow } from '@/components/editor/VariationsEditor';
import type { ReviewRow } from '@/components/editor/ReviewsEditor';
import type { SeoData } from '@/components/editor/SeoFields';
import type { EditorImage } from '@/components/editor/ImageManager';

function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="block text-sm font-medium text-gray-700 mb-1">{label}</span>
      {children}
      {hint && <span className="block text-xs text-gray-500 mt-1">{hint}</span>}
    </label>
  );
}

const inputCls = 'w-full rounded border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500';

function Card({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-4 rounded-lg border border-blue-200/60 bg-blue-50/60 p-5 shadow-sm">
      {title && <h2 className="text-base font-semibold text-gray-800">{title}</h2>}
      {children}
    </div>
  );
}

const TABS: [string, string][] = [
  ['general', 'Загальне'],
  ['attributes', 'Характеристики'],
  ['variations', 'Варіації'],
  ['reviews', 'Відгуки'],
  ['seo', 'SEO'],
];
function getToken(): string {
  if (typeof window === 'undefined') return '';
  return localStorage.getItem('admin_token') || localStorage.getItem('auth_token') || '';
}

function headers(): Record<string, string> {
  const t = getToken();
  const h: Record<string, string> = { 'Content-Type': 'application/json' };
  if (t) h['Authorization'] = 'Bearer ' + t;
  return h;
}

const SECTIONS = ['general', 'pricing', 'inventory', 'categories', 'images', 'attributes', 'variations', 'seo', 'custom'] as const;

export default function ProductEditorPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id;
  const apiBase = id ? `/api/products/${id}` : '';

  const [data, setData] = useState<any>(null);
  const [loadErr, setLoadErr] = useState('');
  const [tab, setTab] = useState('general');
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ ok: boolean; text: string } | null>(null);
  const [dirtySections, setDirtySections] = useState<Set<string>>(new Set());

  const p = data?.product ?? {};

  const markDirty = useCallback((s: string) => {
    setDirtySections((prev) => new Set(prev).add(s));
  }, []);

  const clearDirty = useCallback((s: string) => {
    setDirtySections((prev) => { const n = new Set(prev); n.delete(s); return n; });
  }, []);

  const setP = useCallback((patch: Record<string, unknown>) => {
    setData((d: any) => ({ ...d, product: { ...d.product, ...patch } }));
    markDirty('general');
  }, [markDirty]);

  const saveSection = useCallback(async (section: string, body: unknown) => {
    const res = await fetch(`${apiBase}/${section}`, {
      method: 'PUT',
      headers: headers(),
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const d = await res.json().catch(() => ({}));
      throw new Error(d.detail || `HTTP ${res.status}`);
    }
    clearDirty(section);
  }, [apiBase, clearDirty]);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      setLoadErr('');
      const res = await fetch(`/api/products/${id}/editor`, { headers: headers() });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || `HTTP ${res.status}`);
      }
      setData(await res.json());
      setDirtySections(new Set());
    } catch (e: any) {
      setLoadErr(e.message || 'Помилка завантаження');
    }
  }, [id]);

  useEffect(() => { if (id) load(); }, [id, load]);

  useEffect(() => {
    if (toast) { const t = setTimeout(() => setToast(null), 3000); return () => clearTimeout(t); }
  }, [toast]);

  const handleSave = useCallback(async () => {
    if (!id) return;
    setSaving(true);
    try {
      const dirty = [...dirtySections];
      if (dirty.length === 0) {
        setToast({ ok: true, text: 'Немає змін для збереження.' });
        setSaving(false);
        return;
      }
      for (const section of dirty) {
        let body: unknown = {};
        if (section === 'general') {
          const { name, sku, slug, product_type, status, visibility, short_description, description, brand_id } = p;
          body = { name, sku, slug, product_type, status, visibility, short_description, description, brand_id: brand_id ?? null };
        } else if (section === 'pricing') {
          body = { price: p.price, sale_price: p.sale_price, purchase_cost: p.purchase_cost, sale_start: p.sale_start_at, sale_end: p.sale_end_at };
        } else if (section === 'inventory') {
          body = { stock_qty: p.stock_qty, stock_status: p.stock_status, manage_stock: p.manage_stock, allow_backorders: p.allow_backorders, low_stock_threshold: p.low_stock_threshold, barcode: p.barcode, supplier_sku: p.supplier_sku, supplier_id: p.supplier_id, warehouse: p.warehouse };
        } else if (section === 'categories') {
          body = { category_ids: data.category_ids ?? [] };
        } else if (section === 'images') {
          body = { images: data.imagesEditor ?? data.images ?? [] };
        } else if (section === 'attributes') {
          body = { attributes: data.attributesEditor ?? data.attributes ?? [] };
        } else if (section === 'variations') {
          body = { variations: data.variationsEditor ?? data.variations ?? [] };
        } else if (section === 'seo') {
          body = data.seoEditor ?? {};
        } else if (section === 'custom') {
          const cf = data.customFieldsEditor ?? [];
          body = { custom_fields: cf };
        }
        await saveSection(section, body);
      }
      setToast({ ok: true, text: 'Збережено!' });
      await load();
    } catch (e: any) {
      setToast({ ok: false, text: e.message || 'Помилка збереження' });
    } finally {
      setSaving(false);
    }
  }, [id, data, p, dirtySections, saveSection, load]);
if (!id) return <div className="p-8 text-center text-red-400">ID товару не вказано</div>;
  if (loadErr) return <div className="p-8 text-center text-red-400">{loadErr}</div>;
  if (!data) return <div className="p-8 text-center text-gray-400">Завантаження…</div>;

  const hasDirty = dirtySections.size > 0;

  return (
    <div className="space-y-6 max-w-full">
      <div className="sticky top-0 z-30 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-blue-200/60 bg-white/90 px-4 py-3 shadow-md backdrop-blur">
        <div className="flex items-center gap-3 min-w-0">
          <h1 className="text-lg font-bold truncate text-gray-800">{p.name || 'Новий товар'}</h1>
          {hasDirty && <span className="shrink-0 rounded bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-800">Незбережені зміни</span>}
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {toast && <span className={`text-sm ${toast.ok ? 'text-green-600' : 'text-red-600'}`}>{toast.text}</span>}
          <button onClick={handleSave} disabled={saving}
            className="rounded bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50">
            {saving ? 'Збереження…' : 'Зберегти'}
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-1 border-b border-gray-200">
        {TABS.map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)}
            className={`px-4 py-2.5 text-sm font-medium rounded-t-md border-b-2 transition ${
              tab === key ? 'border-blue-500 text-blue-600 bg-blue-50/60' : 'border-transparent text-gray-600 hover:text-gray-900 hover:bg-gray-50'
            }`}>
            {label}
          </button>
        ))}
      </div>

      <div className="space-y-6">{tab === 'general' && (
          <div className="space-y-6">
            <Card title="Основна інформація">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Field label="Назва товару *"><input className={inputCls} value={p.name ?? ''} onChange={e => setP({ name: e.target.value })} /></Field>
                <Field label="SKU / Артикул"><input className={inputCls} value={p.sku ?? ''} onChange={e => setP({ sku: e.target.value })} /></Field>
                <Field label="Slug / URL"><input className={inputCls} value={p.slug ?? ''} onChange={e => setP({ slug: e.target.value })} /></Field>
                <Field label="Бренд">
                  <select className={inputCls} value={p.brand_id ?? ''} onChange={e => setP({ brand_id: e.target.value ? Number(e.target.value) : null })}>
                    <option value="">— без бренду —</option>
                    {(data?.brands ?? []).map((b: any) => <option key={b.id} value={b.id}>{b.name}</option>)}
                  </select>
                </Field>
                <Field label="Тип товару">
                  <select className={inputCls} value={p.product_type ?? 'simple'} onChange={e => setP({ product_type: e.target.value })}>
                    <option value="simple">Простий товар</option>
                    <option value="variable">Варіативний товар</option>
                  </select>
                </Field>
                <Field label="Статус публікації">
                  <select className={inputCls} value={p.status ?? 'DRAFT'} onChange={e => setP({ status: e.target.value })}>
                    <option value="DRAFT">Чернетка</option>
                    <option value="PUBLISHED">Опубліковано</option>
                    <option value="HIDDEN">Приховано</option>
                    <option value="ARCHIVED">Архівовано</option>
                  </select>
                </Field>
              </div>
            </Card>

            <Card title="Ціни та акції">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <Field label="Звичайна ціна (₴)" hint="Основна ціна товару">
                  <input type="number" min={0} className={inputCls} value={p.price ?? ''} onChange={e => { setP({ price: e.target.value ? Number(e.target.value) : 0 }); markDirty('pricing'); }} />
                </Field>
                <Field label="Ціна за акцією (₴)" hint="Акційна знижкова ціна">
                  <input type="number" min={0} className={inputCls} value={p.sale_price ?? ''} onChange={e => { setP({ sale_price: e.target.value ? Number(e.target.value) : null }); markDirty('pricing'); }} />
                </Field>
                <Field label="Собівартість (₴)">
                  <input type="number" min={0} className={inputCls} value={p.purchase_cost ?? ''} onChange={e => { setP({ purchase_cost: e.target.value ? Number(e.target.value) : null }); markDirty('pricing'); }} />
                </Field>
                <Field label="Початок акції"><input type="date" className={inputCls} value={p.sale_start_at ?? ''} onChange={e => { setP({ sale_start_at: e.target.value || null }); markDirty('pricing'); }} /></Field>
                <Field label="Закінчення акції"><input type="date" className={inputCls} value={p.sale_end_at ?? ''} onChange={e => { setP({ sale_end_at: e.target.value || null }); markDirty('pricing'); }} /></Field>
              </div>
            </Card>
<Card title="Залишок та склад">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <Field label="Кількість на складі"><input type="number" min={0} className={inputCls} value={p.stock_qty ?? ''} onChange={e => { setP({ stock_qty: e.target.value ? Number(e.target.value) : 0 }); markDirty('inventory'); }} /></Field>
                <Field label="Статус наявності">
                  <select className={inputCls} value={p.stock_status ?? 'in_stock'} onChange={e => { setP({ stock_status: e.target.value }); markDirty('inventory'); }}>
                    <option value="in_stock">В наявності</option>
                    <option value="out_of_stock">Немає в наявності</option>
                    <option value="backorder">Під замовлення</option>
                  </select>
                </Field>
                <Field label="Поріг низького залишку"><input type="number" min={0} className={inputCls} value={p.low_stock_threshold ?? ''} onChange={e => { setP({ low_stock_threshold: e.target.value ? Number(e.target.value) : null }); markDirty('inventory'); }} /></Field>
                <Field label="Штрихкод / EAN"><input className={inputCls} value={p.barcode ?? ''} onChange={e => { setP({ barcode: e.target.value }); markDirty('inventory'); }} /></Field>
                <Field label="SKU постачальника"><input className={inputCls} value={p.supplier_sku ?? ''} onChange={e => { setP({ supplier_sku: e.target.value }); markDirty('inventory'); }} /></Field>
                <Field label="Постачальник">
                  <select className={inputCls} value={p.supplier_id ?? ''} onChange={e => { setP({ supplier_id: e.target.value ? Number(e.target.value) : null }); markDirty('inventory'); }}>
                    <option value="">—</option>
                    {(data?.suppliers ?? []).map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                </Field>
                <Field label="Розташування на складі"><input className={inputCls} value={p.warehouse ?? ''} onChange={e => { setP({ warehouse: e.target.value }); markDirty('inventory'); }} /></Field>
              </div>
              <div className="flex flex-wrap gap-4 mt-3">
                <label className="flex items-center gap-2 text-sm text-gray-700"><input type="checkbox" checked={!!p.manage_stock} onChange={e => { setP({ manage_stock: e.target.checked }); markDirty('inventory'); }} className="rounded border-gray-300 bg-white" /> Управляти залишком</label>
                <label className="flex items-center gap-2 text-sm text-gray-700"><input type="checkbox" checked={!!p.allow_backorders} onChange={e => { setP({ allow_backorders: e.target.checked }); markDirty('inventory'); }} className="rounded border-gray-300 bg-white" /> Дозволити передзамовлення</label>
              </div>
            </Card>

            <Card title="Опис">
              <Field label="Короткий опис">
                <textarea className={inputCls + ' min-h-[60px]'} value={p.short_description ?? ''} onChange={e => setP({ short_description: e.target.value })} placeholder="Короткий опис для карток товару в категоріях" />
              </Field>
              <Field label="Повний опис">
                <textarea className={inputCls + ' min-h-[150px]'} value={p.description ?? ''} onChange={e => setP({ description: e.target.value })} placeholder="Детальний опис товару. Підтримується HTML." />
              </Field>
            </Card>

            <Card title="Категорії">
              <CategorySelect value={data?.category_ids ?? []}
                options={data?.categories_tree ?? data?.categories ?? []}
                onChange={(ids) => { setData((d: any) => ({ ...d, category_ids: ids })); markDirty('categories'); }} />
            </Card>

            <Card title="Зображення товару">
              <ImageManager images={(data?.imagesEditor ?? data?.images ?? []) as EditorImage[]}
                productId={Number(id)}
                onChange={(next) => { setData((d: any) => ({ ...d, imagesEditor: next })); markDirty('images'); }} />
            </Card>

            <Card title="Додаткові поля">
              <CustomFieldsEditor
                fields={(data?.customFieldsEditor ?? (() => { try { return JSON.parse(p.meta_json ?? '{}')?.custom_fields ?? []; } catch { return []; } })()) as CustomField[]}
                onChange={(next) => { setData((d: any) => ({ ...d, customFieldsEditor: next })); markDirty('custom'); }} />
            </Card>
          </div>
        )}

        {tab === 'attributes' && (
          <Card title="Характеристики">
            <AttributesEditor rows={(data?.attributesEditor ?? data?.attributes ?? []) as AttrRow[]}
              allAttributes={data?.attribute_definitions ?? []}
              attrValuesByAttribute={data?.attribute_values_by_id ?? {}}
              onChange={(rows) => { setData((d: any) => ({ ...d, attributesEditor: rows })); markDirty('attributes'); }} />
          </Card>
        )}

        {tab === 'variations' && (
          <Card title="Варіації">
            {p.product_type !== 'variable' ? (
              <p className="text-sm text-gray-400">Доступно лише для варіативних товарів. Змініть тип на «Варіативний товар» у вкладці «Загальне».</p>
            ) : (
              <VariationsEditor
                attributes={(data?.attribute_definitions ?? []).filter((a: any) => data?.variation_attr_ids?.includes(a.id)).map((a: any) => ({ name: a.name, values: a.values?.map((v: any) => typeof v === 'string' ? v : v.value) ?? [] }))}
                rows={(data?.variationsEditor ?? data?.variations ?? []) as VariationRow[]}
                onChange={(rows) => { setData((d: any) => ({ ...d, variationsEditor: rows })); markDirty('variations'); }} />
            )}
          </Card>
        )}
{tab === 'reviews' && (
          <Card title="Відгуки">
            <ReviewsEditor
              reviews={(data?.reviewsEditor ?? data?.reviews ?? []) as ReviewRow[]}
              onChange={(rows) => { setData((d: any) => ({ ...d, reviewsEditor: rows })); markDirty('reviews'); }}
              productId={Number(id)}
            />
          </Card>
        )}

        {tab === 'seo' && (
          <Card title="SEO">
            <SeoFields
              value={(data?.seoEditor ?? { seo_title: p.seo_title ?? '', seo_description: p.seo_description ?? '', focus_keyphrase: p.focus_keyphrase ?? '', seo_canonical_url: p.seo_canonical_url ?? '', og_title: p.og_title ?? '', og_description: p.og_description ?? '', og_image_url: p.og_image_url ?? '' }) as Partial<SeoData>}
              onChange={(v: SeoData) => { setData((d: any) => ({ ...d, seoEditor: v })); markDirty('seo'); }} />
          </Card>
        )}
      </div>
    </div>
  );
}
