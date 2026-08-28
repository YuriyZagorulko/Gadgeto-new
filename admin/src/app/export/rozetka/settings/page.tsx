'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { api, qs } from '@/lib/api';
import {
  PageHeader, Button, Select, Input, LoadingState, ErrorState, useToast, Badge,
} from '@/components/ui';

type Setting = { id: number; key: string; value: string | null; is_secret: boolean };
type SettingsResp = { items: Setting[] };
type TabName = 'general' | 'export';

const TABS: { key: TabName; label: string }[] = [
  { key: 'general', label: 'Основні' },
  { key: 'export', label: 'Експорт' },
];

/* ───── Product Selection Modal ───── */

type ProductRow = { id: number; sku: string; name: string; category_name: string | null; price: number; stock_qty: number; stock_status: string; status: string; publication_status: string; sync_status: string; };
type ProductsResp = { items: ProductRow[]; total: number; page: number; per_page: number };

function ProductSelectionModal({
  open, onClose, onExport, running,
}: {
  open: boolean; onClose: () => void; onExport: (ids: number[]) => void; running: boolean;
}) {
  const [rows, setRows] = useState<ProductRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [q, setQ] = useState('');
  const [appliedQ, setAppliedQ] = useState('');
  const [catFilter, setCatFilter] = useState('');
  const [stockFilter, setStockFilter] = useState('');
  const [categories, setCategories] = useState<{ id: number; name: string }[]>([]);
  const [catLoaded, setCatLoaded] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const pages = Math.max(1, Math.ceil(total / perPage));

  useEffect(() => {
    if (!open) { setSelectedIds(new Set()); setPage(1); setQ(''); setAppliedQ(''); return; }
  }, [open]);

  useEffect(() => {
    if (!open || catLoaded) return;
    api.get<{ items: { id: number; name: string }[] }>('/categories?per_page=500')
      .then((d) => { setCategories(d.items); setCatLoaded(true); })
      .catch(() => setCatLoaded(true));
  }, [open, catLoaded]);

  useEffect(() => {
    if (!open) return;
    setLoading(true); setError('');
    const params: Record<string, string | number | undefined> = { page, per_page: perPage };
    if (appliedQ) params.q = appliedQ;
    if (catFilter) params.category_id = Number(catFilter);
    if (stockFilter) params.stock_status = stockFilter;
    api.get<ProductsResp>('/export/channels/rozetka/products' + qs(params))
      .then((d) => { setRows(d.items); setTotal(d.total); })
      .catch((e) => setError(e.message || 'Не вдалось завантажити товари'))
      .finally(() => setLoading(false));
  }, [open, page, perPage, appliedQ, catFilter, stockFilter]);

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

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-12">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative z-10 w-full max-w-4xl bg-white rounded-xl shadow-2xl max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold">Експорт обраних товарів</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">&times;</button>
        </div>
        <div className="px-6 py-3 flex flex-wrap gap-3 items-end border-b border-gray-100">
          <div><label className="block text-xs text-gray-500 mb-1">Пошук</label>
            <Input value={q} onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') { setAppliedQ(q); setPage(1); } }}
              placeholder="SKU / назва" className="w-48" /></div>
          <div><label className="block text-xs text-gray-500 mb-1">Категорія</label>
            <Select value={catFilter} onChange={(e) => { setCatFilter(e.target.value); setPage(1); }}>
              <option value="">Всі</option>
              {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </Select></div>
          <div><label className="block text-xs text-gray-500 mb-1">Наявність</label>
            <Select value={stockFilter} onChange={(e) => { setStockFilter(e.target.value); setPage(1); }}>
              <option value="">Всі</option><option value="in_stock">В наявності</option>
              <option value="out_of_stock">Немає</option></Select></div>
        </div>
        <div className="flex items-center gap-3 px-6 py-2 border-b border-gray-100">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={allPageSelected}
              ref={(el) => { if (el) el.indeterminate = !allPageSelected && somePageSelected; }}
              onChange={toggleSelectAllPage} className="rounded border-gray-300" />
            Вибрати всі на сторінці</label>
          <span className="text-sm text-gray-600">Вибрано: <strong>{selectedIds.size}</strong></span>
          {selectedIds.size > 0 && <button onClick={() => setSelectedIds(new Set())} className="text-xs text-gray-500 hover:underline">Очистити вибір</button>}
        </div>
        <div className="flex-1 overflow-y-auto px-6">
          {loading ? <LoadingState label="Завантаження..." /> :
           error ? <ErrorState message={error} /> : (
            <table className="w-full text-sm">
              <thead className="text-xs text-gray-500 uppercase border-b border-gray-200">
                <tr><th className="w-8 p-2"></th><th className="w-28 p-2 text-left">SKU</th>
                  <th className="p-2 text-left">Назва</th><th className="w-24 p-2 text-right">Ціна</th>
                  <th className="w-16 p-2 text-right">Зал.</th><th className="w-36 p-2 text-left">Категорія</th></tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {rows.length === 0 ? <tr><td colSpan={6} className="p-4 text-center text-gray-400">Немає товарів</td></tr> :
                  rows.map((r) => (
                    <tr key={r.id} className="hover:bg-gray-50">
                      <td className="p-2"><input type="checkbox" checked={selectedIds.has(r.id)}
                        onChange={() => toggleSelect(r.id)} className="rounded border-gray-300" /></td>
                      <td className="p-2 text-xs font-mono max-w-28 truncate">{r.sku || '—'}</td>
                      <td className="p-2 max-w-xs truncate">{r.name || '—'}</td>
                      <td className="p-2 text-right text-xs font-mono">{r.price ? r.price.toLocaleString('uk-UA') : '—'}</td>
                      <td className="p-2 text-right text-xs">{r.stock_qty}</td>
                      <td className="p-2 text-xs max-w-36 truncate">{r.category_name || '—'}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          )}
        </div>
        <div className="px-6 py-3 border-t border-gray-200 flex items-center justify-between">
          <div className="text-sm text-gray-600">Сторінка {page} з {pages} ({total} товарів)</div>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={() => setPage(Math.max(1, page - 1))} disabled={page <= 1}>{'< '}Назад</Button>
            <Button variant="ghost" onClick={() => setPage(Math.min(pages, page + 1))} disabled={page >= pages}>Вперед{' >'}</Button>
          </div>
        </div>
        <div className="px-6 py-3 border-t border-gray-200 flex items-center justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Скасувати</Button>
          <Button onClick={() => onExport([...selectedIds])} disabled={selectedIds.size === 0 || running}>
            {running ? 'Експорт...' : 'Експортувати обрані товари (' + selectedIds.size + ')'}
          </Button>
        </div>
      </div>
    </div>
  );
}

/* ───── Confirmation dialog ───── */

function ConfirmDialog({ open, title, message, confirmLabel, busy, onConfirm, onCancel }: {
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
  const [showProductModal, setShowProductModal] = useState(false);
  const [confirmAll, setConfirmAll] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportRunId, setExportRunId] = useState<number | null>(null);
  const [exportStatus, setExportStatus] = useState<any>(null);
  const [exportErr, setExportErr] = useState('');
  const pollRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);

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
      setShowProductModal(false);
      setConfirmAll(false);
      toast.push('success', `Експорт запущено: ${data.total} товарів (run #${data.run_id})`);
    } catch (e: any) {
      setExportErr(e.message || 'Помилка запуску експорту');
      setExporting(false);
    }
  };

  const SettingRow = ({
    label, hint, skey, type = 'text',
  }: {
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
            <Input type={type} value={draft}
              onChange={(e) => { setDraft(e.target.value); setChanged(true); }}
              className="w-32 text-right" />
          )}
          <Button size="sm" onClick={save} disabled={!changed || saving}
            variant={changed ? 'primary' : 'ghost'}>
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

  return (
    <div>
      <PageHeader title="Налаштування Rozetka" />

      {/* ── Управління експортом ── */}
      <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
        <h2 className="text-base font-semibold text-gray-900 mb-4">Управління експортом</h2>
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="primary" onClick={() => setConfirmAll(true)} disabled={!!exportRunId}>
            Експортувати всі товари
          </Button>
          <Button variant="secondary" onClick={() => setShowProductModal(true)} disabled={!!exportRunId}>
            Експортувати обрані товари
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
                <div className="text-sm text-blue-800 mb-1">
                  Оброблено: {processedProg} / {totalProg}
                </div>
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
              <div className="text-xs text-blue-600 mt-1 truncate">
                {exportStatus.current_operation}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Existing tabs ── */}
      <div className="flex gap-1 mb-6 border-b border-gray-200">
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition -mb-px ${tab === t.key ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'general' && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <p className="text-gray-600 text-sm">Загальні налаштування каналу Rozetka.</p>
          {Object.keys(settings).length > 0 && (
            <div className="mt-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">Збережені параметри</h3>
              <div className="space-y-1">
                {Object.entries(settings).map(([k, v]) => (
                  <div key={k} className="flex items-center gap-3 text-sm">
                    <span className="font-mono text-xs text-gray-500 w-48 truncate">{k}</span>
                    <span className="text-gray-700">{v || '—'}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
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
              <div className="bg-gray-50 rounded px-3 py-2">
                <span className="text-gray-500 text-xs">Тип націнки</span>
                <div className="font-medium">{settings.price_markup_type === 'fixed' ? 'Фіксована' : 'Відсоток'}</div>
              </div>
              <div className="bg-gray-50 rounded px-3 py-2">
                <span className="text-gray-500 text-xs">Розмір націнки</span>
                <div className="font-medium">{settings.price_markup_value || '0'}{settings.price_markup_type === 'fixed' ? ' грн' : '%'}</div>
              </div>
              <div className="bg-gray-50 rounded px-3 py-2">
                <span className="text-gray-500 text-xs">Округлення</span>
                <div className="font-medium">{settings.price_rounding ? `до ${settings.price_rounding}` : '—'}</div>
              </div>
              <div className="bg-gray-50 rounded px-3 py-2">
                <span className="text-gray-500 text-xs">Мін. залишок</span>
                <div className="font-medium">{settings.min_stock_for_export ? `≥ ${settings.min_stock_for_export}` : '—'}</div>
              </div>
              <div className="bg-gray-50 rounded px-3 py-2">
                <span className="text-gray-500 text-xs">Експорт без залишку</span>
                <div className="font-medium">{settings.export_out_of_stock === 'true' ? 'Так' : 'Ні'}</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modals */}
      <ProductSelectionModal
        open={showProductModal}
        onClose={() => setShowProductModal(false)}
        onExport={(ids) => executeExport(ids)}
        running={exporting}
      />
      <ConfirmDialog
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
