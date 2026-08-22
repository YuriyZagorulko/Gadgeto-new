'use client';

import { Suspense, useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
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

export default function ProductsPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <ProductsInner />
    </Suspense>
  );
}
function ProductsInner() {
  const toast = useToast();
  const sp = useSearchParams();

  const [search, setSearch] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [brandId, setBrandId] = useState('');
  const [status, setStatus] = useState(sp.get('status') || '');
  const [stock, setStock] = useState(sp.get('stock') || '');
  const [noImage, setNoImage] = useState(sp.get('no_image') === '1');
  const [noPrice, setNoPrice] = useState(sp.get('no_price') === '1');
  const [page, setPage] = useState(1);
  const perPage = 20;

  const [data, setData] = useState<ListResp | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [cats, setCats] = useState<Opt[]>([]);
  const [brands, setBrands] = useState<Opt[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [confirm, setConfirm] = useState<{ kind: 'bulk-archive' | 'delete'; ids: number[] } | null>(null);
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
      page, per_page: perPage, search: search || undefined,
      category_id: categoryId || undefined, brand_id: brandId || undefined,
      status: status || undefined, stock: stock || undefined,
      no_image: noImage || undefined, no_price: noPrice || undefined,
    }))
      .then((d) => { if (!cancelled) { setData(d); setSelected(new Set()); } })
      .catch((e) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [tick]); // eslint-disable-line react-hooks/exhaustive-deps

  const reload = useCallback(() => setTick((t) => t + 1), []);

  const applyFilters = () => { setPage(1); reload(); };
  const resetFilters = () => {
    setSearch(''); setCategoryId(''); setBrandId(''); setStatus('');
    setStock(''); setNoImage(false); setNoPrice(false); setPage(1); reload();
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
      toast.push('success', 'Товар переміщено в архів');
      setConfirm(null); reload();
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally { setBusy(false); }
  };

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
          <Input value={search} onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && applyFilters()} placeholder="Введіть запит..." />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Категорія</label>
          <Select value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
            <option value="">Усі категорії</option>
            {cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </Select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Бренд</label>
          <Select value={brandId} onChange={(e) => setBrandId(e.target.value)}>
            <option value="">Усі бренди</option>
            {brands.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </Select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Статус</label>
          <Select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Усі статуси</option>
            {PRODUCT_STATUSES.map((s) => <option key={s} value={s}>{PRODUCT_STATUS_LABELS[s]}</option>)}
          </Select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Наявність</label>
          <Select value={stock} onChange={(e) => setStock(e.target.value)}>
            <option value="">Будь-яка</option>
            <option value="in_stock">{STOCK_STATUS_LABELS.in_stock}</option>
            <option value="out_of_stock">{STOCK_STATUS_LABELS.out_of_stock}</option>
          </Select>
        </div>
        <div className="flex items-center gap-4 md:col-span-2">
          <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
            <input type="checkbox" checked={noImage} onChange={(e) => setNoImage(e.target.checked)} className="rounded" />
            Без зображень
          </label>
          <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
            <input type="checkbox" checked={noPrice} onChange={(e) => setNoPrice(e.target.checked)} className="rounded" />
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
            <Button size="sm" variant="danger" onClick={() => setConfirm({ kind: 'bulk-archive', ids: [...selected] })}>
              До архіву
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
          <Table
            head={
              <tr>
                <Th className="w-8">
                  <input type="checkbox" className="rounded" checked={selected.size === data.items.length && data.items.length > 0} onChange={toggleAll} />
                </Th>
                <Th>Товар</Th><Th>Артикул</Th><Th>Бренд</Th><Th>Категорії</Th>
                <Th>Ціна</Th><Th>Наявність</Th><Th>Статус</Th><Th>Оновлено</Th><Th className="w-28"></Th>
              </tr>
            }
          >
            {data.items.map((r) => (
              <tr key={r.id} className="hover:bg-gray-50">
                <Td>
                  <input type="checkbox" className="rounded" checked={selected.has(r.id)} onChange={() => toggleOne(r.id)} />
                </Td>
                <Td>
                  <div className="flex items-center gap-3">
                    {r.image ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={r.image} alt="" className="w-10 h-10 rounded object-cover bg-gray-100 flex-shrink-0" />
                    ) : (
                      <div className="w-10 h-10 rounded bg-gray-100 text-gray-400 flex items-center justify-center text-[10px] flex-shrink-0">немає</div>
                    )}
                    <div className="min-w-0">
                      <Link href={`/products/${r.id}`} className="font-medium text-blue-600 hover:underline line-clamp-1">{r.name}</Link>
                      <div className="text-xs text-gray-400 truncate max-w-[240px]">{r.slug}</div>
                    </div>
                  </div>
                </Td>
                <Td className="text-xs text-gray-500">{r.sku || '—'}</Td>
                <Td className="text-sm">{r.brand_name || '—'}</Td>
                <Td className="text-xs text-gray-500 line-clamp-2 max-w-[180px]">{r.categories || '—'}</Td>
                <Td className="whitespace-nowrap">
                  <div className="font-medium">{r.price ? formatPrice(r.price) : '—'}</div>
                  {r.old_price ? <div className="text-xs text-gray-400 line-through">{formatPrice(r.old_price)}</div> : null}
                </Td>
                <Td>
                  <Badge tone={r.stock_status === 'in_stock' ? 'green' : r.stock_status === 'pre_order' ? 'blue' : 'red'}>
                    {STOCK_STATUS_LABELS[r.stock_status] || r.stock_status}
                  </Badge>
                  {r.stock_qty !== null && <div className="text-xs text-gray-400 mt-0.5">{r.stock_qty} шт.</div>}
                </Td>
                <Td><Badge tone={r.status === 'PUBLISHED' ? 'green' : r.status === 'ARCHIVED' ? 'gray' : 'yellow'}>{PRODUCT_STATUS_LABELS[r.status] || r.status}</Badge></Td>
                <Td className="whitespace-nowrap text-xs text-gray-500">{formatDateTime(r.updated_at)}</Td>
                <Td>
                  <div className="flex gap-1">
                    <Link href={`/products/${r.id}`}><Button size="sm" variant="secondary">Змінити</Button></Link>
                    <Button size="sm" variant="ghost" className="text-red-600" onClick={() => setConfirm({ kind: 'delete', ids: [r.id] })}>✕</Button>
                  </div>
                </Td>
              </tr>
            ))}
          </Table>
          <div className="mt-4">
            <Pagination page={data.page} pages={data.total_pages} total={data.total} onPage={(p) => { setPage(p); reload(); }} />
          </div>
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
        title="Архівувати товар?"
        message="Товар буде переведено в статус «Архів» і деактивовано. Дані не буде видалено."
        confirmLabel="Архівувати" danger busy={busy}
        onConfirm={() => confirm && deleteProduct(confirm.ids[0])}
        onCancel={() => setConfirm(null)}
      />
    </div>
  );
}




