'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { api, qs } from '@/lib/api';
import {
  PageHeader, Button, Select, Input, LoadingState, ErrorState, useToast, Badge,
} from '@/components/ui';
import RozetkaPricingTab from '../components/RozetkaPricingTab';

type Setting = { id: number; key: string; value: string | null; is_secret: boolean };
type SettingsResp = { items: Setting[] };
type TabName = 'general' | 'export' | 'products';

type ProductRow = { id: number; sku: string; name: string;
  category_name: string | null; price: number; stock_qty: number;
  stock_status: string; status: string; publication_status: string;
  sync_status: string; supplier_name: string; };
type ProductsResp = { items: ProductRow[]; total: number; page: number; per_page: number };
type Supplier = { id: number; code: string; name: string };
type CatOpt = { id: number; name: string; parent_id: number | null };

const TABS: { key: TabName; label: string }[] = [
  { key: 'general', label: 'Основні' },
  { key: 'export', label: 'Експорт' },
  { key: 'products', label: 'Експорт товарів' },
];

const PAGE_SIZE_OPTIONS = [25, 50, 100, 200];

/* ───── Searchable Category Select ───── */

function SearchableCategorySelect({ value, options, onChange }: {
  value: string; options: CatOpt[]; onChange: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handle = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, [open]);

  const byId = new Map(options.map((c) => [c.id, c]));
  const selectedName = value ? byId.get(Number(value))?.name || '' : '';

  const filtered = query.trim()
    ? options.filter((c) => c.name.toLowerCase().includes(query.trim().toLowerCase()))
    : options;

  return (
    <div className="relative" ref={ref}>
      <button type="button" onClick={() => setOpen(!open)}
        className="w-full text-left rounded border border-gray-200 px-2 py-1.5 text-sm flex items-center justify-between bg-white">
        <span className={selectedName ? '' : 'text-gray-400'}>{selectedName || 'Всі'}</span>
        <span className="text-gray-500 ml-1">▾</span>
      </button>
      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 w-64 bg-white border border-gray-200 rounded-lg shadow-lg max-h-72 overflow-y-auto">
          <div className="sticky top-0 p-2 border-b bg-white">
            <input autoFocus value={query} onChange={(e) => setQuery(e.target.value)}
              placeholder="Пошук категорій..."
              className="w-full rounded border border-gray-200 px-2 py-1.5 text-sm" />
          </div>
          <button onClick={() => { onChange(''); setOpen(false); setQuery(''); }}
            className={'block w-full text-left px-3 py-1.5 text-sm hover:bg-gray-50 ' + (!value ? 'bg-blue-50 font-semibold' : '')}>
            Всі категорії
          </button>
          {filtered.slice(0, 100).map((c) => (
            <button key={c.id} onClick={() => { onChange(String(c.id)); setOpen(false); setQuery(''); }}
              className={'block w-full text-left px-3 py-1.5 text-sm hover:bg-gray-50 ' + (value === String(c.id) ? 'bg-blue-50 font-semibold' : '')}>
              {c.name}
            </button>
          ))}
          {filtered.length === 0 && <div className="px-3 py-2 text-sm text-gray-400">Нічого не знайдено</div>}
        </div>
      )}
    </div>
  );
}

/* ───── Confirm dialog ───── */

function ConfirmModal({ open, title, message, confirmLabel, busy, onConfirm, onCancel }: {
  open: boolean; title: string; message: string; confirmLabel: string; busy: boolean;
  onConfirm: () => void; onCancel: () => void;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onCancel} />
      <div className="relative z-10 w-full max-w-sm bg-white rounded-xl shadow-2xl p-6">
        <h3 className="text-lg font-semibold mb-2">{title}</h3>
        <p className="text-sm text-gray-600 mb-6">{message}</p>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onCancel}>Скасувати</Button>
          <Button onClick={onConfirm} disabled={busy}>{busy ? 'Експорт...' : confirmLabel}</Button>
        </div>
      </div>
    </div>
  );
}

/* ───── Main page ───── */

export default function RozetkaSettingsPage() {
  const toast = useToast();
  const [tab, setTab] = useState<TabName>('general');
  const [settings, setSettings] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [confirmAll, setConfirmAll] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportRunId, setExportRunId] = useState<number | null>(null);
  const [exportStatus, setExportStatus] = useState<any>(null);
  const [exportErr, setExportErr] = useState('');
  const pollRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);

  // Product table state
  const [rows, setRows] = useState<ProductRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(25);
  const [tableLoading, setTableLoading] = useState(false);
  const [tableError, setTableError] = useState('');
  const [q, setQ] = useState('');
  const [appliedQ, setAppliedQ] = useState('');
  const [catFilter, setCatFilter] = useState('');
  const [stockFilter, setStockFilter] = useState('');
  const [supFilter, setSupFilter] = useState('');
  const [sort, setSort] = useState('');
  const [categories, setCategories] = useState<CatOpt[]>([]);
  const [catLoaded, setCatLoaded] = useState(false);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [supLoaded, setSupLoaded] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [pageInput, setPageInput] = useState('');

  const pages = Math.max(1, Math.ceil(total / perPage));
  const from = total === 0 ? 0 : (page - 1) * perPage + 1;
  const to = Math.min(page * perPage, total);

  // Load suppliers
  useEffect(() => {
    if (supLoaded || tab !== 'products') return;
    api.get<{ items: Supplier[] }>('/suppliers?per_page=100')
      .then((d) => { setSuppliers(d.items || []); setSupLoaded(true); })
      .catch(() => setSupLoaded(true));
  }, [tab, supLoaded]);

  // Load categories
  useEffect(() => {
    if (catLoaded || tab !== 'products') return;
    api.get<{ items: CatOpt[] }>('/categories?per_page=500')
      .then((d) => { setCategories(d.items); setCatLoaded(true); })
      .catch(() => { setCatLoaded(true); });
  }, [tab, catLoaded]);

  // Load products
  useEffect(() => {
    if (tab !== 'products') return;
    setTableLoading(true); setTableError('');
    const params: Record<string, string | number | undefined> = { page, per_page: perPage };
    if (appliedQ) params.q = appliedQ;
    if (catFilter) params.category_id = Number(catFilter);
    if (stockFilter) params.stock_status = stockFilter;
    if (supFilter) params.supplier_id = Number(supFilter);
    if (sort) params.sort = sort;
    api.get<ProductsResp>('/export/channels/rozetka/products' + qs(params))
      .then((d) => { setRows(d.items); setTotal(d.total); })
      .catch((e) => setTableError(e.message || 'Помилка завантаження'))
      .finally(() => setTableLoading(false));
  }, [tab, page, perPage, appliedQ, catFilter, stockFilter, supFilter, sort]);

  const visibleIds = rows.map((r) => r.id);
  const allPageSelected = visibleIds.length > 0 && visibleIds.every((i) => selectedIds.has(i));
  const somePageSelected = visibleIds.some((i) => selectedIds.has(i));

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

  const toggleSort = (field: string) => {
    setSort((prev) => {
      if (prev === field) return field + '_desc';
      if (prev === field + '_desc') return '';
      return field;
    });
    setPage(1);
  };

  const resetFilters = () => {
    setQ(''); setAppliedQ(''); setCatFilter(''); setStockFilter(''); setSupFilter(''); setSort(''); setPage(1);
  };

  const hasActiveFilters = !!(appliedQ || catFilter || stockFilter || supFilter || sort);
  const selectionCount = selectedIds.size;

  const executeExport = async (ids?: number[]) => {
    setExportErr('');
    setExporting(true);
    try {
      const body: any = ids
        ? { selection: { all_matching_filters: false, product_ids: ids } }
        : { selection: { all_matching_filters: true } };
      const data = await api.post<{ run_id: number; status: string; total: number }>(
        '/export/channels/rozetka/export', body);
      setExportRunId(data.run_id);
      setConfirmAll(false);
      toast.push('success', `Експорт запущено: ${data.total} товарів (run #${data.run_id})`);
    } catch (e: any) {
      setExportErr(e.message || 'Помилка запуску експорту');
      setExporting(false);
    }
  };

  // Poll export status
  useEffect(() => {
    if (!exportRunId) {
      setExportStatus(null);
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = undefined; }
      return;
    }
    const poll = async () => {
      try {
        const d = await api.get<any>(`/export/channels/rozetka/export/status/${exportRunId}`);
        setExportStatus(d);
        if (['completed', 'completed_with_errors', 'failed', 'cancelled'].includes(d.ui_status)) {
          clearInterval(pollRef.current!);
          pollRef.current = undefined;
          setExportRunId(null);
          setExporting(false);
          toast.push(d.ui_status === 'completed' ? 'success' : 'error',
            `Експорт завершено: ${d.progress.created} створено, ${d.progress.updated} оновлено, ${d.progress.failed} помилок`);
        }
      } catch { /* retry */ }
    };
    poll();
    pollRef.current = setInterval(poll, 2000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [exportRunId, toast]);

  const load = useCallback(() => {
    setLoading(true); setError('');
    api.get<SettingsResp>('/export/channels/rozetka/settings')
      .then((d) => {
        const map: Record<string, string> = {};
        for (const s of d.items) map[s.key] = s.value ?? '';
        setSettings(map);
      })
      .catch((e: any) => setError(e.message || 'Не вдалось завантажити налаштування'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const updateSetting = async (key: string, value: string) => {
    setSaving(true);
    try {
      await api.put('/export/channels/rozetka/settings', { key, value, is_secret: false });
      setSettings((prev) => ({ ...prev, [key]: value }));
      toast.push('success', 'Збережено');
    } catch (e: any) {
      toast.push('error', e.message || 'Помилка збереження');
    } finally {
      setSaving(false);
    }
  };

  const SettingRow = ({ label, hint, skey, type = 'text' }: {
    label: string; hint?: string; skey: string; type?: 'text' | 'number' | 'select';
  }) => {
    const val = settings[skey] ?? '';
    const [draft, setDraft] = useState(val);
    const [changed, setChanged] = useState(false);
    useEffect(() => { setDraft(val); setChanged(false); }, [val]);
    const save = () => {
      if (draft === val) return;
      updateSetting(skey, draft);
      setChanged(false);
    };
    return (
      <div className="flex items-start justify-between py-4 border-b border-gray-100 last:border-0">
        <div className="flex-1 mr-4">
          <label className="block text-sm font-medium text-gray-900">{label}</label>
          {hint && <p className="text-xs text-gray-500 mt-0.5">{hint}</p>}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {type === 'select' ? (
            <Select value={draft} onChange={(e) => { setDraft(e.target.value); setChanged(true); }} className="w-40">
              <option value="percentage">Відсоток</option>
              <option value="fixed">Фіксована</option>
            </Select>
          ) : (
            <Input type={type} value={draft} onChange={(e) => { setDraft(e.target.value); setChanged(true); }} className="w-32 text-right" />
          )}
          <Button size="sm" onClick={save} disabled={!changed || saving} variant={changed ? 'primary' : 'ghost'}>
            {saving ? '…' : 'Зберегти'}
          </Button>
        </div>
      </div>
    );
  };

  if (loading) return <LoadingState label="Завантаження налаштувань..." />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  const progress = exportStatus?.progress || {};
  const totalProg = progress.total || 0;
  const processedProg = progress.processed || 0;
  const pct = totalProg > 0 ? Math.round((processedProg / totalProg) * 100) : 0;

  const SortHeader = ({ field, label, className = '' }: { field: string; label: string; className?: string }) => {
    const active = sort === field || sort === field + '_desc';
    const dir = sort === field ? 'asc' : sort === field + '_desc' ? 'desc' : null;
    return (
      <th className={'p-2 text-left text-xs text-gray-500 uppercase cursor-pointer hover:text-gray-700 select-none ' + className} onClick={() => toggleSort(field)}>
        {label} {dir ? (dir === 'asc' ? '↑' : '↓') : ''}
      </th>
    );
  };

  return (
    <div>
      <PageHeader title="Налаштування Rozetka" />

      {/* Export management */}
      <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
        <h2 className="text-base font-semibold text-gray-900 mb-4">Управління експортом</h2>
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="primary" onClick={() => setConfirmAll(true)} disabled={!!exportRunId}>
            Експортувати всі товари
          </Button>
          {exportErr && <span className="text-sm text-red-600">{exportErr}</span>}
        </div>
        {exportRunId && (
          <div className="mt-4 p-4 bg-blue-50 border border-blue-100 rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <span className="font-medium text-blue-900">Експорт виконується</span>
              <Badge tone="blue">#{exportRunId}</Badge>
            </div>
            {totalProg > 0 && (
              <>
                <div className="text-sm text-blue-800 mb-1">Оброблено: {processedProg} / {totalProg}</div>
                <div className="w-full bg-blue-200 rounded-full h-2">
                  <div className="bg-blue-600 h-2 rounded-full transition-all duration-500" style={{ width: pct + '%' }} />
                </div>
                <div className="flex gap-4 mt-2 text-xs text-blue-700">
                  <span>✓ {progress.created || 0} створено</span>
                  <span>↻ {progress.updated || 0} оновлено</span>
                  <span>— {progress.skipped || 0} пропущено</span>
                  <span>✗ {progress.failed || 0} помилок</span>
                </div>
              </>
            )}
            {exportStatus?.current_operation && (
              <div className="text-xs text-blue-600 mt-1 truncate">{exportStatus.current_operation}</div>
            )}
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-gray-200">
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition -mb-px ${tab === t.key ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'general' && (
        <div className="space-y-6">
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h2 className="text-base font-semibold text-gray-900 mb-4">Основні налаштування</h2>
            <p className="text-xs text-gray-500 mb-4">Загальні налаштування каналу Rozetka.</p>
            {Object.keys(settings).length > 0 && (
              <div className="space-y-1">
                {Object.entries(settings).map(([k, v]) => (
                  <div key={k} className="flex items-center gap-3 text-sm">
                    <span className="font-mono text-xs text-gray-500 w-48 truncate">{k}</span>
                    <span className="text-gray-700">{v || '—'}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <RozetkaPricingTab />
        </div>
      )}

      {tab === 'export' && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-base font-semibold text-gray-900 mb-4">Налаштування експорту товарів</h2>
          <p className="text-xs text-gray-500 mb-6">Ці налаштування застосовуються під час експорту товарів до Rozetka.</p>
          <div className="divide-y divide-gray-100">
            <SettingRow skey="price_markup_type" label="Тип націнки" hint="Відсоток від ціни або фіксована сума" type="select" />
            <SettingRow skey="price_markup_value" label="Розмір націнки" hint="15 = 15% або 15 грн" type="number" />
            <SettingRow skey="price_rounding" label="Округлення ціни" hint="До найближчого X (0 = без округлення)" type="number" />
            <SettingRow skey="min_stock_for_export" label="Мінімальний залишок" hint="Не експортувати товари з кількістю менше" type="number" />
            <SettingRow skey="export_out_of_stock" label="Експорт без залишку" hint="Експортувати товари з нульовою кількістю" type="select" />
          </div>
          <div className="mt-6 pt-4 border-t border-gray-100">
            <h3 className="text-sm font-semibold text-gray-700 mb-2">Поточні значення</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
              <div className="bg-gray-50 rounded px-3 py-2"><span className="text-gray-500 text-xs">Тип націнки</span><div className="font-medium">{settings.price_markup_type === 'fixed' ? 'Фіксована' : 'Відсоток'}</div></div>
              <div className="bg-gray-50 rounded px-3 py-2"><span className="text-gray-500 text-xs">Розмір націнки</span><div className="font-medium">{settings.price_markup_value || '0'}{settings.price_markup_type === 'fixed' ? ' грн' : '%'}</div></div>
              <div className="bg-gray-50 rounded px-3 py-2"><span className="text-gray-500 text-xs">Округлення</span><div className="font-medium">{settings.price_rounding ? `до ${settings.price_rounding}` : '—'}</div></div>
              <div className="bg-gray-50 rounded px-3 py-2"><span className="text-gray-500 text-xs">Мін. залишок</span><div className="font-medium">{settings.min_stock_for_export ? `≥ ${settings.min_stock_for_export}` : '—'}</div></div>
              <div className="bg-gray-50 rounded px-3 py-2"><span className="text-gray-500 text-xs">Експорт без залишку</span><div className="font-medium">{settings.export_out_of_stock === 'true' ? 'Так' : 'Ні'}</div></div>
            </div>
          </div>
        </div>
      )}

      {tab === 'products' && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-base font-semibold text-gray-900 mb-4">Товари для вибіркового експорту</h2>

          <div className="flex flex-wrap gap-3 items-end mb-4">
            <div><label className="block text-xs text-gray-500 mb-1">Пошук</label>
              <Input value={q} onChange={(e) => setQ(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { setAppliedQ(q); setPage(1); } }}
                placeholder="SKU / назва" className="w-48" /></div>
            <div><label className="block text-xs text-gray-500 mb-1">Постачальник</label>
              <Select value={supFilter} onChange={(e) => { setSupFilter(e.target.value); setPage(1); }}>
                <option value="">Усі</option>
                {suppliers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </Select></div>
            <div><label className="block text-xs text-gray-500 mb-1">Категорія</label>
              <SearchableCategorySelect value={catFilter} options={categories} onChange={(id) => { setCatFilter(id); setPage(1); }} />
            </div>
            <div><label className="block text-xs text-gray-500 mb-1">Наявність</label>
              <Select value={stockFilter} onChange={(e) => { setStockFilter(e.target.value); setPage(1); }}>
                <option value="">Всі</option>
                <option value="in_stock">В наявності</option>
                <option value="out_of_stock">Немає</option>
              </Select></div>
            {hasActiveFilters && <Button variant="ghost" size="sm" onClick={resetFilters}>Скинути фільтри</Button>}
          </div>

          <div className="flex items-center gap-3 py-2 border-b border-gray-200">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={allPageSelected}
                ref={(el) => { if (el) el.indeterminate = !allPageSelected && somePageSelected; }}
                onChange={toggleSelectAllPage} className="rounded border-gray-300" />
              Вибрати всі на сторінці
            </label>
            <span className="text-sm text-gray-600">Вибрано: <strong>{selectionCount}</strong></span>
            {selectionCount > 0 && (
              <button onClick={() => setSelectedIds(new Set())} className="text-xs text-blue-600 hover:underline">Очистити</button>
            )}
          </div>

          {tableLoading ? <LoadingState label="Завантаження..." /> :
           tableError ? <ErrorState message={tableError} /> : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-xs text-gray-500 uppercase bg-gray-50">
                  <tr>
                    <th className="w-8 p-2"></th>
                    <SortHeader field="name" label="Назва" />
                    <SortHeader field="sku" label="SKU" />
                    <SortHeader field="category" label="Категорія" />
                    <SortHeader field="supplier" label="Постачальник" />
                    <SortHeader field="price" label="Ціна" className="text-right" />
                    <SortHeader field="stock" label="Наявність" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {rows.length === 0 ? (
                    <tr><td colSpan={8} className="p-4 text-center text-gray-400">Немає товарів</td></tr>
                  ) : rows.map((r) => (
                    <tr key={r.id} className="hover:bg-gray-50">
                      <td className="p-2"><input type="checkbox" checked={selectedIds.has(r.id)}
                        onChange={() => toggleSelect(r.id)} className="rounded border-gray-300" /></td>
                      <td className="p-2 max-w-xs truncate" title={r.name}>{r.name || '—'}</td>
                      <td className="p-2 text-xs font-mono max-w-24 truncate" title={r.sku}>{r.sku || '—'}</td>
                      <td className="p-2 text-xs max-w-36 truncate">{r.category_name || '—'}</td>
                      <td className="p-2 text-xs">{r.supplier_name || '—'}</td>
                      <td className="p-2 text-right text-xs font-mono">{r.price ? r.price.toLocaleString('uk-UA') : '—'}</td>
                      <td className="p-2">
                        {r.stock_status === 'in_stock' ? <Badge tone="green">В наявності</Badge> : <Badge tone="red">Немає</Badge>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-4 mt-4">
            <div className="text-sm text-gray-600">Показано {from}–{to} із {total.toLocaleString('uk-UA')}</div>
            <div className="flex items-center gap-2">
              <label className="text-xs text-gray-500">Показувати:</label>
              <Select value={String(perPage)} onChange={(e) => { setPerPage(Number(e.target.value)); setPage(1); }}
                className="w-20 text-sm">
                {PAGE_SIZE_OPTIONS.map((n) => <option key={n} value={n}>{n}</option>)}
              </Select>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-2 mt-2">
            <button onClick={() => setPage(1)} disabled={page <= 1}
              className="px-2 py-1 text-xs rounded border border-gray-200 hover:bg-gray-50 disabled:opacity-40">‹ Перша</button>
            <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page <= 1}
              className="px-2 py-1 text-xs rounded border border-gray-200 hover:bg-gray-50 disabled:opacity-40">Попередня</button>
            <span className="text-sm text-gray-600 mx-2">Сторінка</span>
            <input type="text" inputMode="numeric" value={pageInput}
              onChange={(e) => setPageInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  const p = Math.max(1, Math.min(pages, parseInt(pageInput, 10) || 1));
                  setPage(p);
                  setPageInput('');
                }
              }}
              onFocus={() => setPageInput(String(page))}
              className="w-16 text-center rounded border border-gray-200 px-2 py-1 text-sm"
              placeholder={String(page)} />
            <span className="text-sm text-gray-600">з {pages}</span>
            <button onClick={() => setPage(Math.min(pages, page + 1))} disabled={page >= pages}
              className="px-2 py-1 text-xs rounded border border-gray-200 hover:bg-gray-50 disabled:opacity-40">Наступна</button>
            <button onClick={() => setPage(pages)} disabled={page >= pages}
              className="px-2 py-1 text-xs rounded border border-gray-200 hover:bg-gray-50 disabled:opacity-40">Остання ›</button>
          </div>

          <div className="flex justify-end mt-4 pt-4 border-t border-gray-200">
            <Button onClick={() => executeExport([...selectedIds])}
              disabled={selectionCount === 0 || exporting || !!exportRunId}>
              {exporting || exportRunId ? 'Експорт...' : `Експортувати обрані товари (${selectionCount})`}
            </Button>
          </div>
        </div>
      )}

      <ConfirmModal
        open={confirmAll}
        title="Підтвердження експорту"
        message="Буде запущено експорт усіх доступних для експорту товарів у Rozetka."
        confirmLabel="Експортувати"
        busy={exporting}
        onConfirm={() => executeExport()}
        onCancel={() => setConfirmAll(false)}
      />
    </div>
  );
}
