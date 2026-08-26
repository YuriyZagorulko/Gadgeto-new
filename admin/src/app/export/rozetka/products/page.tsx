'use client';

import { useEffect, useState, useMemo } from 'react';
import { api, qs } from '@/lib/api';
import {
  PageHeader, Table, Th, Td, Badge, Button, Input, Select,
  LoadingState, ErrorState, Pagination, ConfirmDialog, useToast,
} from '@/components/ui';

type ProductRow = { id: number; sku: string; name: string;
  category_name: string | null; category_id: number | null;
  price: number; stock_qty: number; stock_status: string;
  status: string; publication_status: string; sync_status: string;
  external_id: string | null; has_mapping: boolean;
  validation_summary?: { errors: number; warnings: number };
  last_error?: string; };
type ProductsResp = { items: ProductRow[]; total: number; page: number; per_page: number };
type PreviewResp = { products: any[]; summary: { total: number; exportable: number; errors: number; warnings: number } };
type SettingsResp = { items: { key: string; value: string | null }[] };

const pubBadge: Record<string, { tone: 'gray' | 'green' | 'blue' | 'yellow'; label: string }> = {
  published: { tone: 'green', label: 'Опубліковано' },
  ready: { tone: 'blue', label: 'Готовий' },
  draft: { tone: 'gray', label: 'Чернетка' },
  disabled: { tone: 'yellow', label: 'Вимкнено' },
};

function mappingBadge(hm: boolean, v?: { errors: number; warnings: number }) {
  if (!hm) return { tone: 'red' as const, label: 'Немає мапінгу' };
  if (v && v.errors > 0) return { tone: 'red' as const, label: 'Помилок: ' + v.errors };
  if (v && v.warnings > 0) return { tone: 'yellow' as const, label: 'Попереджень: ' + v.warnings };
  return { tone: 'green' as const, label: 'Готово' };
}

export default function RozetkaExportPage() {
  const toast = useToast();
  const [rows, setRows] = useState<ProductRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [q, setQ] = useState('');
  const [appliedQ, setAppliedQ] = useState('');
  const [catFilter, setCatFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [stockFilter, setStockFilter] = useState('');
  const [mapFilter, setMapFilter] = useState('');
  const [pubStatusFilter, setPubStatusFilter] = useState('');
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [selectAllMatching, setSelectAllMatching] = useState(false);
  const [settings, setSettings] = useState<Record<string, string>>({});
  const [settingsLoaded, setSettingsLoaded] = useState(false);
  const [preview, setPreview] = useState<PreviewResp | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [categories, setCategories] = useState<{ id: number; name: string }[]>([]);
  const [catLoaded, setCatLoaded] = useState(false);
  const pages = useMemo(() => Math.max(1, Math.ceil(total / perPage)), [total, perPage]);

  // Load categories
  useEffect(() => {
    if (catLoaded) return;
    api.get<{ items: { id: number; name: string }[] }>('/categories?per_page=500')
      .then((d) => { setCategories(d.items); setCatLoaded(true); })
      .catch(() => { setCatLoaded(true); });
  }, [catLoaded]);

  // Load settings
  useEffect(() => {
    if (settingsLoaded) return;
    api.get<SettingsResp>('/export/channels/rozetka/settings')
      .then((d) => {
        const m: Record<string, string> = {};
        for (const s of d.items) m[s.key] = s.value ?? '';
        setSettings(m); setSettingsLoaded(true);
      })
      .catch(() => setSettingsLoaded(true));
  }, [settingsLoaded]);

  const filterParams = useMemo(() => {
    const p: Record<string, string | number | undefined> = { page, per_page };
    if (appliedQ) p.q = appliedQ;
    if (catFilter) p.category_id = Number(catFilter);
    if (stockFilter) p.stock_status = stockFilter;
    if (statusFilter) p.status = statusFilter;
    if (pubStatusFilter) p.publication_status = pubStatusFilter;
    if (mapFilter === 'yes') p.has_mapping = 'true';
    else if (mapFilter === 'no') p.has_mapping = 'false';
    return p;
  }, [page, perPage, appliedQ, catFilter, stockFilter, statusFilter, pubStatusFilter, mapFilter]);

  const load = useCallback(() => {
    setLoading(true); setError(''); setPreview(null);
    api.get<ProductsResp>('/export/channels/rozetka/products' + qs(filterParams))
      .then((d) => { setRows(d.items); setTotal(d.total); })
      .catch((e) => setError(e.message || 'Не вдалось завантажити товари'))
      .finally(() => setLoading(false));
  }, [filterParams]);
  useEffect(() => { load(); }, [load]);

  const visibleIds = useMemo(() => rows.map((r) => r.id), [rows]);
  const allPageSelected = useMemo(() => visibleIds.length > 0 && visibleIds.every((i) => selectedIds.has(i)), [visibleIds, selectedIds]);
  const somePageSelected = useMemo(() => visibleIds.some((i) => selectedIds.has(i)), [visibleIds, selectedIds]);

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  };
  const toggleSelectAllPage = () => {
    setSelectedIds((prev) => {
      const n = new Set(prev);
      if (allPageSelected) { for (const i of visibleIds) n.delete(i); }
      else { for (const i of visibleIds) n.add(i); }
      return n;
    });
  };
  const selectAllMatchingAction = () => { setSelectAllMatching(true); };
  const clearSelection = () => { setSelectedIds(new Set()); setSelectAllMatching(false); };
  const selectionCount = useMemo(() => selectAllMatching ? total : selectedIds.size, [selectAllMatching, selectedIds, total]);

  const runPreview = async () => {
    setPreviewLoading(true); setPreview(null);
    try {
      const body: any = {};
      if (selectAllMatching) {
        body.selection = { all_matching_filters: true,
          filters: { q: appliedQ || undefined, category_id: catFilter ? Number(catFilter) : undefined,
            publication_status: pubStatusFilter || undefined,
            stock_status: stockFilter || undefined,
            has_mapping: mapFilter === 'yes' ? true : mapFilter === 'no' ? false : undefined } };
      } else {
        body.selection = { all_matching_filters: false, product_ids: [...selectedIds] };
      }
      const data = await api.post<PreviewResp>('/export/channels/rozetka/export/preview', body);
      setPreview(data);
    } catch (e: any) { toast.push('error', e.message || 'Помилка попереднього перегляду'); }
    finally { setPreviewLoading(false); }
  };

  const markupLabel = useMemo(() => {
    const t = settings.price_markup_type; const v = settings.price_markup_value || '0';
    return t === 'fixed' ? '+' + v + ' ₴' : '+' + v + '%';
  }, [settings]);
  const [confirmMode, setConfirmMode] = useState<'all' | 'selected' | null>(null);
  const [exporting, setExporting] = useState(false);

  const handleExportAll = () => setConfirmMode('all');
  const handleExportSelected = () => { if (selectionCount > 0) setConfirmMode('selected'); };

  const executeExport = async () => {
    setExporting(true);
    try {
      const body: any = {};
      if (confirmMode === 'all') {
        body.selection = { all_matching_filters: true,
          filters: { q: appliedQ || undefined, category_id: catFilter ? Number(catFilter) : undefined,
            publication_status: pubStatusFilter || undefined,
            stock_status: stockFilter || undefined,
            has_mapping: mapFilter === 'yes' ? true : mapFilter === 'no' ? false : undefined } };
      } else {
        body.selection = { all_matching_filters: false, product_ids: [...selectedIds] };
      }
      const data = await api.post<{ run_id: number; status: string; total: number }>(
        '/export/channels/rozetka/export', body);
      toast.push('success',
        `Експорт запущено: ${data.total} товарів (run #${data.run_id}, статус: ${data.status})`);
      setConfirmMode(null);
      setPreview(null);
      // Auto-refresh the listing after export
      load();
    } catch (e: any) {
      toast.push('error', e.message || 'Помилка запуску експорту');
    } finally {
      setExporting(false);
      setConfirmMode(null);
    }
  };

  const roundingLabel = useMemo(() => {
    const v = settings.price_rounding; return v && v !== '0' ? 'до ' + v + ' ₴' : null;
  }, [settings]);

  return (
    <div>
      <PageHeader title="Експорт товарів у Rozetka" />

      <div className="flex flex-wrap items-center gap-3 mb-4">
        <Button variant="primary" onClick={() => handleExportAll()}>Експортувати всі товари на Rozetka</Button>
        <Button disabled={selectionCount === 0} variant="secondary" onClick={() => handleExportSelected()}>
          Експортувати вибрані товари на Rozetka ({selectionCount})</Button>
      </div>

      <div className="flex flex-wrap gap-4 mb-4 text-xs text-gray-600">
        <span>Націнка Rozetka: <strong>{markupLabel}</strong></span>
        {roundingLabel && <span>Округлення: <strong>{roundingLabel}</strong></span>}
        <a href="/export/rozetka/settings" className="text-blue-600 hover:underline">Налаштування →</a>
      </div>

      <div className="flex flex-wrap items-end gap-3 mb-4">
        <div><label className="block text-xs text-gray-500 mb-1">Пошук</label>
          <Input value={q} onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { setAppliedQ(q); setPage(1); } }}
            placeholder="SKU / назва" className="w-48" /></div>
        <div><label className="block text-xs text-gray-500 mb-1">Категорія</label>
          <Select value={catFilter} onChange={(e) => { setCatFilter(e.target.value); setPage(1); }}>
            <option value="">Всі</option>
            {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </Select></div>
        <div><label className="block text-xs text-gray-500 mb-1">Статус</label>
          <Select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}>
            <option value="">Всі</option><option value="PUBLISHED">Опубліковано</option>
            <option value="DRAFT">Чернетка</option><option value="ARCHIVED">Архів</option>
          </Select></div>
        <div><label className="block text-xs text-gray-500 mb-1">Наявність</label>
          <Select value={stockFilter} onChange={(e) => { setStockFilter(e.target.value); setPage(1); }}>
            <option value="">Всі</option><option value="in_stock">В наявності</option>
            <option value="out_of_stock">Немає</option></Select></div>
        <div><label className="block text-xs text-gray-500 mb-1">Мапінг</label>
          <Select value={mapFilter} onChange={(e) => { setMapFilter(e.target.value); setPage(1); }}>
            <option value="">Всі</option><option value="yes">Є мапінг</option>
            <option value="no">Немає мапінгу</option></Select></div>
        <div><label className="block text-xs text-gray-500 mb-1">Статус експорту</label>
          <Select value={pubStatusFilter} onChange={(e) => { setPubStatusFilter(e.target.value); setPage(1); }}>
            <option value="">Всі</option><option value="ready">Готовий</option>
            <option value="published">Опубліковано</option>
            <option value="draft">Чернетка</option></Select></div>
      </div>

      <div className="flex items-center gap-3 mb-3 px-1">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={allPageSelected}
            ref={(el) => { if (el) el.indeterminate = !allPageSelected && somePageSelected; }}
            onChange={toggleSelectAllPage} className="rounded border-gray-300" />
          Вибрати всі на сторінці</label>
        <span className="text-sm text-gray-600">Вибрано: <strong>{selectionCount}</strong></span>
        {!selectAllMatching && selectedIds.size > 0 && total > selectedIds.size && (
          <button onClick={selectAllMatchingAction}
            className="text-xs text-blue-600 hover:underline">
            Вибрати всі {total} товарів за поточними фільтрами</button>
        )}
        {selectAllMatching && <span className="text-xs text-green-700 font-medium">✓ Вибрано всі товари за поточними фільтрами</span>}
        {selectionCount > 0 && <button onClick={clearSelection} className="text-xs text-gray-500 hover:underline">Очистити вибір</button>}
      </div>

      {loading ? <LoadingState label="Завантаження товарів..." /> :
       error ? <ErrorState message={error} onRetry={load} /> : (
        <div className="overflow-x-auto"><Table head={<><Th className="w-8"></Th><Th className="w-28">SKU</Th>
          <Th>Назва</Th><Th className="w-36">Категорія</Th>
          <Th className="w-20 text-right">Ціна</Th><Th className="w-16 text-right">Зал.</Th>
          <Th className="w-28">Мапінг</Th><Th className="w-28">Експорт</Th></>}>
            {rows.length === 0 ? <tr><td colSpan={8} className="p-6 text-center text-gray-400">Немає товарів</td></tr> :
              rows.map((r) => { const mb = mappingBadge(r.has_mapping, r.validation_summary);
                const pb = pubBadge[r.publication_status] || { tone: 'gray' as const, label: r.publication_status };
                return (<tr key={r.id} className="hover:bg-gray-50">
                  <Td><input type="checkbox" checked={selectedIds.has(r.id)}
                    onChange={() => toggleSelect(r.id)} className="rounded border-gray-300" /></Td>
                  <Td className="text-xs font-mono max-w-28 truncate" title={r.sku}>{r.sku || '—'}</Td>
                  <Td className="max-w-xs truncate" title={r.name}>{r.name || '—'}</Td>
                  <Td className="text-xs max-w-36 truncate">{r.category_name || '—'}</Td>
                  <Td className="text-right text-xs font-mono">{r.price ? r.price.toLocaleString('uk-UA') : '—'}</Td>
                  <Td className="text-right text-xs">{r.stock_qty}</Td>
                  <Td><Badge tone={mb.tone}>{mb.label}</Badge></Td>
                  <Td><Badge tone={pb.tone}>{pb.label}</Badge></Td>
                </tr>); }))}</Table></div>
      )}
      <Pagination page={page} pages={pages} total={total} onPage={setPage}
        onGoToPage={(p) => setPage(Math.min(Math.max(p, 1), pages))}
        pageSize={perPage} onPageSizeChange={(n) => { setPerPage(n); setPage(1); }} />

      <div className="flex gap-2 mt-4 mb-4">
        <Button onClick={runPreview} disabled={selectionCount === 0 || previewLoading} variant="secondary">
          {previewLoading ? 'Завантаження...' : 'Переглянути експорт'}</Button>
      </div>

      {preview && (
        <div className="bg-white rounded-lg border border-gray-200 p-4 mb-4">
          <h3 className="text-sm font-semibold text-gray-900 mb-2">Попередній перегляд експорту</h3>
          <div className="flex flex-wrap gap-4 text-sm mb-3">
            <div className="bg-gray-50 rounded px-3 py-1.5"><span className="text-gray-500 text-xs">Всього</span><div className="font-medium">{preview.summary.total}</div></div>
            <div className="bg-green-50 rounded px-3 py-1.5"><span className="text-green-600 text-xs">Готово</span><div className="font-medium text-green-700">{preview.summary.exportable}</div></div>
            {preview.summary.errors > 0 && <div className="bg-red-50 rounded px-3 py-1.5"><span className="text-red-600 text-xs">Помилки</span><div className="font-medium text-red-700">{preview.summary.errors}</div></div>}
            {preview.summary.warnings > 0 && <div className="bg-yellow-50 rounded px-3 py-1.5"><span className="text-yellow-700 text-xs">Попередження</span><div className="font-medium text-yellow-800">{preview.summary.warnings}</div></div>}
          </div>
          {preview.products && preview.products.length > 0 && (
            <div className="text-xs text-gray-600"><span className="font-medium">Перші {Math.min(preview.products.length, 10)} товарів:</span>
              <ul className="mt-1 space-y-0.5">{preview.products.slice(0, 10).map((p: any) => (
                <li key={p.id} className="flex gap-2"><span className="font-mono w-24 truncate">{p.sku || '—'}</span>
                  <span className="flex-1 truncate">{p.name}</span>
                  {p.exportable ? <Badge tone="green">OK</Badge> : <Badge tone="red">Помилки</Badge>}</li>
              ))}</ul></div>
          )}
          {preview.summary.exportable === 0 && <p className="text-xs text-red-600 mt-2">
            Жоден товар не готовий до експорту. Перевірте мапінг.</p>}
        </div>
      )}
      <ConfirmDialog
        open={!!confirmMode}
        title="Підтвердження експорту"
        message={
          confirmMode === 'all'
            ? `Буде експортовано всі ${total} товарів, що відповідають поточним фільтрам.`
            : `Буде експортовано ${selectionCount} вибраних товарів.`
        }
        confirmLabel="Експортувати"
        busy={exporting}
        onConfirm={executeExport}
        onCancel={() => setConfirmMode(null)}
      />
    </div>
  );
}