'use client';

import { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { api, qs } from '@/lib/api';
import { formatPrice, formatDateTime, PRODUCT_STATUSES, PRODUCT_STATUS_LABELS, STOCK_STATUS_LABELS } from '@/lib/format';
import {
  PageHeader, Table, Th, Td, Badge, Button, Input, Select, Pagination,
  LoadingState, ErrorState, EmptyState, ConfirmDialog, useToast,
} from '@/components/ui';

type Row = {
  id: number; sku: string | null; name: string; slug: string;
  price: number | null; old_price: number | null; stock_status: string;
  stock_qty: number | null; status: string; is_active: boolean;
  updated_at: string; brand_name: string | null; image: string | null;
  categories: string | null;
};
type ListResp = { items: Row[]; total: number; page: number; per_page: number; total_pages: number };
type Opt = { id: number; name: string };

/* Sortable columns — keys must match the backend SORT_COLUMNS whitelist. */
const SORT_KEYS = ['name', 'sku', 'category', 'brand', 'price', 'stock', 'status', 'updated'] as const;
type SortKey = (typeof SORT_KEYS)[number];
const PER_PAGE_OPTIONS = [25, 50, 100];
const DEFAULT_PER_PAGE = 25;

function parsePositiveInt(v: string | null, fallback: number): number {
  const n = v ? parseInt(v, 10) : NaN;
  return Number.isFinite(n) && n >= 1 ? n : fallback;
}

export default function ProductsPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <ProductsInner />
    </Suspense>
  );
}
/** Sortable column header with ↑ / ↓ / ↕ indicator. */
function SortableTh({
  label, sortKey, active, order, onSort, className = '',
}: {
  label: string; sortKey: SortKey; active: boolean; order: 'asc' | 'desc';
  onSort: (k: SortKey) => void; className?: string;
}) {
  return (
    <th
      scope="col"
      aria-sort={active ? (order === 'asc' ? 'ascending' : 'descending') : 'none'}
      className={`px-3 py-2.5 font-medium ${className}`}
    >
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        title={`Сортувати за «${label}»`}
        className={`inline-flex items-center gap-1 uppercase tracking-wide transition-colors ${
          active ? 'text-blue-600' : 'text-gray-500 hover:text-gray-900'
        }`}
      >
        <span>{label}</span>
        <span aria-hidden className="text-[15px] leading-[15px]">{active ? (order === 'asc' ? '↑' : '↓') : '↕'}</span>
      </button>
    </th>
  );
}

function ProductsInner() {
  const toast = useToast();
  const sp = useSearchParams();
  const router = useRouter();
  const spString = sp.toString();

  /* ---------------------------------------------------------------- */
  /* Table state lives in the URL (?page=&per_page=&sort=&order=…),    */
  /* so refresh / back-forward / sharing keep exactly the same view.   */
  /* ---------------------------------------------------------------- */
  const q = useMemo(() => {
    const perPage = Number(sp.get('per_page'));
    const sort = sp.get('sort');
    return {
      page: parsePositiveInt(sp.get('page'), 1),
      perPage: PER_PAGE_OPTIONS.includes(perPage) ? perPage : DEFAULT_PER_PAGE,
      sort: (SORT_KEYS as readonly string[]).includes(sort || '') ? (sort as SortKey) : ('' as const),
      order: (sp.get('order') === 'asc' ? 'asc' : 'desc') as 'asc' | 'desc',
      search: sp.get('search') || '',
      categoryId: sp.get('category_id') || '',
      brandId: sp.get('brand_id') || '',
      status: sp.get('status') || '',
      stock: sp.get('stock') || '',
      noImage: sp.get('no_image') === '1',
      noPrice: sp.get('no_price') === '1',
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [spString]);

  /** Commit a partial state change to the URL. All other params stay intact. */
  const commit = useCallback(
    (updates: Record<string, string | number | boolean | undefined>, resetPage = false) => {
      const next = new URLSearchParams(spString);
      for (const [k, v] of Object.entries(updates)) {
        if (v === undefined || v === null || v === '' || v === false) next.delete(k);
        else next.set(k, String(v));
      }
      if (resetPage) next.delete('page');
      const query = next.toString();
      router.push(query ? `/products?${query}` : '/products', { scroll: false });
    },
    [spString, router],
  );

  /* Draft filter inputs — committed only on «Застосувати» / Enter. */
  const [searchDraft, setSearchDraft] = useState(q.search);
  const [categoryDraft, setCategoryDraft] = useState(q.categoryId);
  const [brandDraft, setBrandDraft] = useState(q.brandId);
  const [statusDraft, setStatusDraft] = useState(q.status);
  const [stockDraft, setStockDraft] = useState(q.stock);
  const [noImageDraft, setNoImageDraft] = useState(q.noImage);
  const [noPriceDraft, setNoPriceDraft] = useState(q.noPrice);

  /* Re-sync drafts when committed filters change (e.g. browser back/forward). */
  const committedFiltersKey = JSON.stringify([q.search, q.categoryId, q.brandId, q.status, q.stock, q.noImage, q.noPrice]);
  useEffect(() => {
    setSearchDraft(q.search);
    setCategoryDraft(q.categoryId);
    setBrandDraft(q.brandId);
    setStatusDraft(q.status);
    setStockDraft(q.stock);
    setNoImageDraft(q.noImage);
    setNoPriceDraft(q.noPrice);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [committedFiltersKey]);

  const [data, setData] = useState<ListResp | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [cats, setCats] = useState<Opt[]>([]);
  const [brands, setBrands] = useState<Opt[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [confirm, setConfirm] = useState<{ kind: 'bulk-archive' | 'delete' | 'bulk-delete'; ids: number[] } | null>(null);
  const [busy, setBusy] = useState(false);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    api.get<{ items: Opt[] }>('/categories').then((d) => setCats(d.items || [])).catch(() => {});
    api.get<ListResp & { items: Opt[] }>('/brands' + qs({ per_page: 100 }))
      .then((d) => setBrands((d.items as unknown as Opt[]) || [])).catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.get<ListResp>('/products' + qs({
      page: q.page, per_page: q.perPage, search: q.search || undefined,
      category_id: q.categoryId || undefined, brand_id: q.brandId || undefined,
      status: q.status || undefined, stock: q.stock || undefined,
      no_image: q.noImage || undefined, no_price: q.noPrice || undefined,
      sort: q.sort || undefined, order: q.sort ? q.order : undefined,
    }))
      .then((d) => { if (!cancelled) { setData(d); setSelected(new Set()); } })
      .catch((e) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [q, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);

  /* A stale/deep page can return zero rows — silently fall back to the
     last valid page instead of showing an empty table or an API error. */
  useEffect(() => {
    if (!data || data.items.length > 0 || data.total <= 0 || q.page <= 1) return;
    const last = Math.max(1, data.total_pages);
    if (last >= q.page) return;
    const next = new URLSearchParams(spString);
    next.set('page', String(last));
    router.replace(`/products?${next.toString()}`, { scroll: false });
  }, [data, q.page, spString, router]);

  const applyFilters = () => {
    commit({
      search: searchDraft.trim() || undefined,
      category_id: categoryDraft || undefined,
      brand_id: brandDraft || undefined,
      status: statusDraft || undefined,
      stock: stockDraft || undefined,
      no_image: noImageDraft || undefined,
      no_price: noPriceDraft || undefined,
    }, true);
  };
  const resetFilters = () => {
    setSearchDraft(''); setCategoryDraft(''); setBrandDraft(''); setStatusDraft('');
    setStockDraft(''); setNoImageDraft(false); setNoPriceDraft(false);
    commit({
      search: undefined, category_id: undefined, brand_id: undefined,
      status: undefined, stock: undefined, no_image: undefined, no_price: undefined,
    }, true);
  };

  /* Two-state sorting: first click ascending, second descending.
     The current page is kept — only the row order changes. */
  const toggleSort = (k: SortKey) => {
    commit({ sort: k, order: q.sort === k && q.order === 'asc' ? 'desc' : 'asc' });
  };

  const toggleAll = () => {
    if (!data) return;
    setSelected((prev) =>
      prev.size === data.items.length ? new Set() : new Set(data.items.map((r) => r.id)),
    );
  };
  const toggleOne = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const runBulk = async (action: string, ids: number[]) => {
    setBusy(true);
    try {
      const res = await api.post<{ updated: number }>('/products/bulk', { ids, action });
      toast.push('success', `Оновлено товарів: ${res.updated}`);
      setConfirm(null); reload();
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally { setBusy(false); }
  };

  const deleteProduct = async (id: number) => {
    setBusy(true);
    try {
      await api.delete(`/products/${id}`);
      toast.push('success', 'Товар остаточно видалено');
      setConfirm(null); reload();
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally { setBusy(false); }
  };

  const runBulkDelete = async (ids: number[]) => {
    setBusy(true);
    try {
      await api.post('/products/bulk-delete', { ids });
      toast.push('success', `Видалено товарів: ${ids.length}`);
      setSelected(new Set());
      setConfirm(null); reload();
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally { setBusy(false); }
  };

  /* Soft loading: keep the rendered table visible (dimmed) while refetching. */
  const softLoading = loading && !!data;

  return (
    <div>
      <PageHeader
        title="Товари"
        actions={<Link href="/products/new"><Button>＋ Додати товар</Button></Link>}
      />

      {/* Filters */}
      <div className="bg-white border border-gray-200 rounded-lg p-4 mb-4 grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-3 items-end">
        <div className="lg:col-span-2">
          <label className="block text-xs text-gray-500 mb-1">Пошук (назва / артикул)</label>
          <Input value={searchDraft} onChange={(e) => setSearchDraft(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && applyFilters()} placeholder="Введіть запит..." />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Категорія</label>
          <Select value={categoryDraft} onChange={(e) => setCategoryDraft(e.target.value)}>
            <option value="">Усі категорії</option>
            {cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </Select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Бренд</label>
          <Select value={brandDraft} onChange={(e) => setBrandDraft(e.target.value)}>
            <option value="">Усі бренди</option>
            {brands.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </Select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Статус</label>
          <Select value={statusDraft} onChange={(e) => setStatusDraft(e.target.value)}>
            <option value="">Усі статуси</option>
            {PRODUCT_STATUSES.map((s) => <option key={s} value={s}>{PRODUCT_STATUS_LABELS[s]}</option>)}
          </Select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Наявність</label>
          <Select value={stockDraft} onChange={(e) => setStockDraft(e.target.value)}>
            <option value="">Будь-яка</option>
            <option value="in_stock">{STOCK_STATUS_LABELS.in_stock}</option>
            <option value="out_of_stock">{STOCK_STATUS_LABELS.out_of_stock}</option>
          </Select>
        </div>
        <div className="flex items-center gap-4 md:col-span-2">
          <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
            <input type="checkbox" checked={noImageDraft} onChange={(e) => setNoImageDraft(e.target.checked)} className="rounded" />
            Без зображень
          </label>
          <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
            <input type="checkbox" checked={noPriceDraft} onChange={(e) => setNoPriceDraft(e.target.checked)} className="rounded" />
            Без ціни
          </label>
        </div>
        <div className="flex gap-2 md:col-span-2 lg:col-span-2 justify-end">
          <Button variant="secondary" onClick={resetFilters}>Скинути</Button>
          <Button onClick={applyFilters}>Застосувати</Button>
        </div>
      </div>

      {/* Bulk bar */}
      {selected.size > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-2 mb-3 flex items-center gap-2 flex-wrap">
          <span className="text-sm text-blue-800 font-medium">Вибрано: {selected.size}</span>
          <div className="ml-auto flex gap-2 flex-wrap">
            <Button size="sm" variant="secondary" onClick={() => runBulk('publish', [...selected])}>Опублікувати</Button>
            <Button size="sm" variant="secondary" onClick={() => runBulk('hide', [...selected])}>Приховати</Button>
            <Button size="sm" variant="secondary" onClick={() => runBulk('activate', [...selected])}>Активувати</Button>
            <Button size="sm" variant="secondary" onClick={() => runBulk('deactivate', [...selected])}>Деактивувати</Button>
            <Button size="sm" variant="secondary" onClick={() => setConfirm({ kind: 'bulk-archive', ids: [...selected] })}>
              До архіву
            </Button>
            <Button size="sm" variant="danger" onClick={() => setConfirm({ kind: 'bulk-delete', ids: [...selected] })}>
              🗑️ Видалити
            </Button>
          </div>
        </div>
      )}

      {error && <ErrorState message={error} onRetry={reload} />}
      {!error && loading && !data && <LoadingState label="Завантаження товарів..." />}
      {!error && data && data.items.length === 0 && (
        <EmptyState title="Товарів не знайдено" hint="Спробуйте змінити умови фільтрації." />
      )}
      {data && data.items.length > 0 && (
        <>
          <div className={`transition-opacity duration-150 ${softLoading ? 'opacity-50 pointer-events-none select-none' : ''}`}>
            {/* Fixed layout + explicit column widths keep header/body aligned;
                horizontal scrolling stays inside this card, not the page. */}
            <Table tableClassName="table-fixed min-w-[1280px]"
              head={
                <tr>
                  <Th className="w-9 pr-0">
                    <input type="checkbox" aria-label="Вибрати всі" className="rounded"
                      checked={selected.size === data.items.length && data.items.length > 0} onChange={toggleAll} />
                  </Th>
                  <SortableTh label="Товар" sortKey="name" active={q.sort === 'name'} order={q.order} onSort={toggleSort} />
                  <SortableTh label="Артикул" sortKey="sku" active={q.sort === 'sku'} order={q.order} onSort={toggleSort} className="w-28" />
                  <SortableTh label="Категорії" sortKey="category" active={q.sort === 'category'} order={q.order} onSort={toggleSort} className="w-40" />
                  <SortableTh label="Бренд" sortKey="brand" active={q.sort === 'brand'} order={q.order} onSort={toggleSort} className="w-32" />
                  <SortableTh label="Ціна" sortKey="price" active={q.sort === 'price'} order={q.order} onSort={toggleSort} className="w-28" />
                  <SortableTh label="Наявність" sortKey="stock" active={q.sort === 'stock'} order={q.order} onSort={toggleSort} className="w-28" />
                  <SortableTh label="Статус" sortKey="status" active={q.sort === 'status'} order={q.order} onSort={toggleSort} className="w-28" />
                  <SortableTh label="Оновлено" sortKey="updated" active={q.sort === 'updated'} order={q.order} onSort={toggleSort} className="w-36" />
                                    <Th className="w-40">Товар у магазині</Th>
                </tr>
              }
            >
            {data.items.map((r) => (
              <tr key={r.id} className="hover:bg-gray-50">
                <Td className="pr-0">
                  <input type="checkbox" aria-label={`Вибрати: ${r.name}`} className="rounded" checked={selected.has(r.id)} onChange={() => toggleOne(r.id)} />
                </Td>
                <Td>
                  <div className="flex items-center gap-3 min-w-0">
                    {r.image ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={r.image} alt="" className="w-10 h-10 rounded object-cover bg-gray-100 flex-shrink-0" />
                    ) : (
                      <div className="w-10 h-10 rounded bg-gray-100 text-gray-400 flex items-center justify-center text-[10px] flex-shrink-0">немає</div>
                    )}
                    <div className="min-w-0">
                      <Link href={`/products/${r.id}`} className="block truncate font-medium text-blue-600 hover:underline">{r.name}</Link>
                      <div className="text-xs text-gray-400 truncate">{r.slug}</div>
                    </div>
                  </div>
                </Td>
                <Td className="text-xs text-gray-500 truncate">{r.sku || '—'}</Td>
                <Td className="text-xs text-gray-500 line-clamp-2">{r.categories || '—'}</Td>
                <Td className="text-sm truncate">{r.brand_name || '—'}</Td>
                <Td className="whitespace-nowrap text-right tabular-nums">
                  <div className="font-medium">{r.price ? formatPrice(r.price) : '—'}</div>
                  {r.old_price ? <div className="text-xs text-gray-400 line-through">{formatPrice(r.old_price)}</div> : null}
                </Td>
                <Td className="whitespace-nowrap">
                  <Badge tone={r.stock_status === 'in_stock' ? 'green' : r.stock_status === 'pre_order' ? 'blue' : 'red'}>
                    {STOCK_STATUS_LABELS[r.stock_status] || r.stock_status}
                  </Badge>
                  {r.stock_qty !== null && <div className="text-xs text-gray-400 mt-0.5 tabular-nums">{r.stock_qty} шт.</div>}
                </Td>
                <Td><Badge tone={r.status === 'PUBLISHED' ? 'green' : r.status === 'ARCHIVED' ? 'gray' : 'yellow'}>{PRODUCT_STATUS_LABELS[r.status] || r.status}</Badge></Td>
                <Td className="whitespace-nowrap text-xs text-gray-500 tabular-nums">{formatDateTime(r.updated_at)}</Td>
                                                <Td className="whitespace-nowrap">
                  <div className="flex items-center gap-1">
                    {r.slug ? (
                      <a
                        href={process.env.NEXT_PUBLIC_STORE_URL + '/product/' + encodeURIComponent(r.slug)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center justify-center px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50 hover:border-gray-400 transition-colors"
                      >Відкрити</a>
                    ) : (
                      <span className="inline-flex items-center justify-center px-3 py-1.5 text-sm text-gray-400 border border-gray-200 rounded">Недоступно</span>
                    )}
                    <button
                      onClick={() => setConfirm({ kind: 'delete', ids: [r.id] })}
                      className="px-3 py-1.5 text-sm font-medium text-red-600 hover:text-red-800 border border-transparent hover:border-red-200 rounded transition-colors"
                      title="Видалити назавжди"
                    >
                      🗑️
                    </button>
                  </div>
                </Td>
              </tr>
            ))}
          </Table>
          <Pagination
            page={q.page}
            pages={data.total_pages}
            total={data.total}
            onPage={(p) => commit({ page: p })}
            onGoToPage={(p) => commit({ page: p })}
            pageSize={q.perPage}
            onPageSizeChange={(n) => commit({ per_page: n }, true)}
            pageSizeOptions={PER_PAGE_OPTIONS}
          />
          </div>
          {softLoading && (
            <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2 bg-white border border-gray-200 shadow-lg rounded-md px-4 py-2 text-sm text-gray-600">
              <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-solid border-gray-300 border-t-blue-600" aria-hidden />
              Завантаження...
            </div>
          )}
        </>
      )}

      <ConfirmDialog
        open={confirm?.kind === 'bulk-archive'}
        title="Архівувати товари?"
        message={`Вибрані товари (${confirm?.ids.length ?? 0}) буде переведено в статус «Архів» і деактивовано.`}
        confirmLabel="Архівувати" danger busy={busy}
        onConfirm={() => confirm && runBulk('archive', confirm.ids)}
        onCancel={() => setConfirm(null)}
      />
      <ConfirmDialog
        open={confirm?.kind === 'delete'}
        title="Видалити товар?"
        message={`Товар «${confirm?.ids[0] === -1 ? data?.items.find((r) => confirm?.ids.includes(r.id))?.name : data?.items.find((r) => r.id === confirm?.ids[0])?.name || ''}» буде остаточно видалено. Цю дію неможливо скасувати.\n\nУВАГА: історія замовлень не постраждає, але всі пов'язані дані (зображення, характеристики, варіації, кошики) буде видалено.`}
        confirmLabel="Видалити назавжди" danger busy={busy}
        onConfirm={() => confirm && deleteProduct(confirm.ids[0])}
        onCancel={() => setConfirm(null)}
      />
      <ConfirmDialog
        open={confirm?.kind === 'bulk-delete'}
        title="Масове видалення товарів?"
        message={`Вибрані товари (${confirm?.ids.length ?? 0}) буде остаточно видалено. Цю дію неможливо скасувати.\n\nІсторія замовлень не постраждає.`}
        confirmLabel="Видалити назавжди" danger busy={busy}
        onConfirm={() => confirm && runBulkDelete(confirm.ids)}
        onCancel={() => setConfirm(null)}
      />
    </div>
  );
}




