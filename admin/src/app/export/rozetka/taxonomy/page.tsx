'use client';

import { useEffect, useState, useCallback } from 'react';
import { api, qs } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import {
  PageHeader, Button, Input, Table, Th, Td,
  Badge, LoadingState, ErrorState, Pagination, Spinner, useToast, Modal,
} from '@/components/ui';

type TabName = 'categories' | 'attributes' | 'values' | 'history';
const TABS: { key: TabName; label: string }[] = [
  { key: 'categories', label: 'Категорії' },
  { key: 'attributes', label: 'Атрибути' },
  { key: 'values', label: 'Значення' },
  { key: 'history', label: 'Історія оновлень' },
];

type TaxonomyStats = { categories: number; attributes: number; values: number };
type RunStatus = {
  run_id: number | null;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  categories: { processed: number; total: number; created: number; updated: number };
  attributes: { categories_processed: number; categories_total: number; total: number; created: number; updated: number };
  values: { total: number; created: number; updated: number };
  errors: number;
  current_operation: string | null;
  logs: { message: string; level: string }[];
  taxonomy: TaxonomyStats;
};

type ExtCatRow = {
  id: number; external_id: string; name: string;
  parent_external_id: string | null; path: string | null;
  attributes_count: number;
};
type ExtAttrRow = {
  id: number; category_external_id: string; category_name: string;
  external_id: string; name: string;
  param_type: string | null; unit: string | null;
  is_required: boolean | null; fetched_at: string;
};
type ExtValRow = {
  id: number; attribute_external_id: string; attribute_name: string;
  external_id: string; value: string; category_external_id: string;
  category_name: string | null; fetched_at: string;
};
type ListResp<T> = { items: T[]; total: number; page: number; per_page: number };

function fmtDuration(seconds?: number | null): string {
  if (seconds == null || seconds < 0) return '—';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  const parts: string[] = [];
  if (h > 0) parts.push(`${h}г`);
  if (m > 0 || h > 0) parts.push(`${m}хв`);
  parts.push(`${s}с`);
  return parts.join(' ');
}

const badgeTone: Record<string, 'gray' | 'green' | 'blue' | 'yellow' | 'red'> = {
  succeeded: 'green', running: 'blue', queued: 'gray',
  failed: 'red', partial: 'yellow',
};

function fmtStatus(s: string): { tone: 'gray' | 'green' | 'blue' | 'yellow' | 'red'; label: string } {
  const labels: Record<string, string> = {
    succeeded: 'Успішно', running: 'Виконується', queued: 'У черзі',
    failed: 'Помилка', partial: 'Частково', never: 'Не запускалось',
  };
  return { tone: badgeTone[s] || 'gray', label: labels[s] || s };
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="text-2xl font-bold">
        {typeof value === 'number' ? value.toLocaleString('uk-UA') : value}
      </div>
      <div className="text-xs text-gray-500 mt-1">{label}</div>
    </div>
  );
}

function ProgressBar({ pct }: { pct: number }) {
  return (
    <div className="h-2 bg-gray-200 rounded mt-1 overflow-hidden">
      <div className="h-full bg-blue-600 transition-all" style={{ width: `${Math.min(100, pct)}%` }} />
    </div>
  );
}

type RunHistoryRow = {
  id: number; status: string; total_count: number;
  processed_count: number; created_count: number;
  updated_count: number; failed_count: number;
  started_at: string | null; finished_at: string | null;
  created_at: string; errors: number;
};

function HistoryTable({ refreshTrigger }: { refreshTrigger: number | null }) {
  const [runs, setRuns] = useState<RunHistoryRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedRun, setSelectedRun] = useState<RunHistoryRow | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<RunStatus | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    api.get<{ items: RunHistoryRow[]; total: number }>('/export/channels/rozetka/taxonomy/runs?per_page=50')
      .then((d) => {
        const items = (d.items || []).map((r) => ({
          ...r, status: (r.status || '').toLowerCase(),
        }));
        setRuns(items);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load, refreshTrigger]);

  const openDetail = async (run: RunHistoryRow) => {
    setSelectedRun(run);
    setDetailLoading(true);
    try {
      const d = await api.get<RunStatus>(`/export/channels/rozetka/taxonomy/runs/${run.id}`);
      if (d && d.status) d.status = d.status.toLowerCase();
      setSelectedDetail(d);
    } catch { setSelectedDetail(null); }
    setDetailLoading(false);
  };

  if (loading) return <LoadingState label="Завантаження історії..." />;
  if (runs.length === 0) return <p className="text-gray-400 italic text-sm py-6 text-center">Ще не було оновлень таксономії</p>;

  return (
    <>
      <Modal open={!!selectedRun} onClose={() => { setSelectedRun(null); setSelectedDetail(null); }}
        title={`Оновлення #${selectedRun?.id}`}>
        {detailLoading ? <LoadingState /> : selectedDetail ? (
          <div className="space-y-3 text-sm">
            <div className="flex items-center gap-2">
              <Badge tone={badgeTone[selectedDetail.status] || 'gray'}>{fmtStatus(selectedDetail.status).label}</Badge>
            </div>
            {selectedDetail.started_at && <div>Початок: {formatDateTime(selectedDetail.started_at)}</div>}
            {selectedDetail.finished_at && <div>Завершення: {formatDateTime(selectedDetail.finished_at)}</div>}
            {selectedDetail.duration_seconds != null && <div>Тривалість: {fmtDuration(selectedDetail.duration_seconds)}</div>}
            <div className="grid grid-cols-2 gap-3 bg-gray-50 p-3 rounded-lg">
              <div>
                <span className="text-gray-500">Категорії:</span>{' '}
                {selectedDetail.categories.total} (оброблено: {selectedDetail.categories.processed})
              </div>
              <div>
                <span className="text-gray-500">Створено:</span>{' '}
                {selectedDetail.categories.created}
              </div>
              <div>
                <span className="text-gray-500">Атрибути:</span>{' '}
                {selectedDetail.attributes.total}
              </div>
              <div>
                <span className="text-gray-500">Значення:</span>{' '}
                {selectedDetail.values.total}
              </div>
              <div>
                <span className="text-gray-500">Помилки:</span>{' '}
                <span className={selectedDetail.errors > 0 ? 'text-red-600 font-medium' : ''}>{selectedDetail.errors}</span>
              </div>
            </div>
            {selectedDetail.logs && selectedDetail.logs.length > 0 && (
              <details>
                <summary className="cursor-pointer text-sm font-medium text-gray-700">Журнал ({selectedDetail.logs.length})</summary>
                <div className="mt-2 max-h-40 overflow-y-auto text-xs font-mono space-y-0.5">
                  {selectedDetail.logs.map((l, i) => (
                    <div key={i} className="flex gap-2">
                      <span className="text-gray-400 w-16">{l.level}</span>
                      <span className="text-gray-600 break-all">{l.message}</span>
                    </div>
                  ))}
                </div>
              </details>
            )}
          </div>
        ) : <p className="text-gray-400">Деталі недоступні</p>}
      </Modal>

      <Table head={<><Th>#</Th><Th>Статус</Th><Th>Початок</Th><Th>Завершення</Th><Th>Категорії</Th><Th>Атрибути</Th><Th>Значення</Th><Th>Помилки</Th><Th>Дії</Th></>}>
        {runs.map((r) => {
          const st = fmtStatus(r.status);
          return (
            <tr key={r.id} className="hover:bg-gray-50">
              <Td className="text-xs font-mono">{r.id}</Td>
              <Td><Badge tone={st.tone}>{st.label}</Badge></Td>
              <Td className="text-xs">{r.started_at ? formatDateTime(r.started_at) : '—'}</Td>
              <Td className="text-xs">{r.finished_at ? formatDateTime(r.finished_at) : '—'}</Td>
              <Td className="text-xs">{r.total_count ?? 0}</Td>
              <Td className="text-xs">{r.created_count ?? 0}</Td>
              <Td className="text-xs">{r.updated_count ?? 0}</Td>
              <Td className="text-xs"><span className={r.errors > 0 ? 'text-red-600 font-medium' : ''}>{r.errors}</span></Td>
              <Td><button onClick={() => openDetail(r)} className="text-xs text-blue-600 hover:underline">Деталі</button></Td>
            </tr>
          );
        })}
      </Table>
    </>
  );
}

function useTaxonomyStatusPoll() {
  const [status, setStatus] = useState<RunStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(() => {
    api.get<RunStatus>('/export/channels/rozetka/taxonomy/status')
      .then((d) => {
        // Normalize status from DB-uppercase (RUNNING) to frontend-lowercase (running)
        if (d && d.status) d.status = d.status.toLowerCase();
        setStatus(d);
      })
      .catch((e) => setError(e.message || 'Не вдалось завантажити статус'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const isRunning = status?.status === 'running' || status?.status === 'queued';

  useEffect(() => {
    if (!isRunning) return;
    const interval = setInterval(() => load(), 3000);
    return () => clearInterval(interval);
  }, [isRunning, load]);

  return { status, loading, error, reload: load };
}

function useLocalList<T>(url: string, deps: unknown[]) {
  const [items, setItems] = useState<T[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancel = false;
    setLoading(true);
    api.get<ListResp<T>>(url)
      .then((d) => {
        if (!cancel) { setItems(d.items); setTotal(d.total); }
      })
      .catch((e) => { if (!cancel) setError(e.message || 'Не вдалось завантажити'); })
      .finally(() => { if (!cancel) setLoading(false); });
    return () => { cancel = true; };
  }, deps);

  return { items, total, loading, error };
}

export default function RozetkaTaxonomyPage() {
  const toast = useToast();
  const [tab, setTab] = useState<TabName>('categories');

  const { status, loading: statusLoading, error: statusError, reload: reloadStatus } = useTaxonomyStatusPoll();

  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(25);
  const [q, setQ] = useState('');
  const [appliedQ, setAppliedQ] = useState('');

  // MUST be unconditionally called before any early return (Rules of Hooks).
  const catList = useLocalList<ExtCatRow>(
    '/export/channels/rozetka/taxonomy/categories' + qs({ page, per_page: perPage, q: appliedQ || undefined }),
    [page, perPage, appliedQ]);
  const attrList = useLocalList<ExtAttrRow>(
    '/export/channels/rozetka/taxonomy/attributes' + qs({ page, per_page: perPage, q: appliedQ || undefined }),
    [page, perPage, appliedQ]);
  const valList = useLocalList<ExtValRow>(
    '/export/channels/rozetka/taxonomy/values' + qs({ page, per_page: perPage, q: appliedQ || undefined }),
    [page, perPage, appliedQ]);

  useEffect(() => {
    if (statusError) toast.push('error', statusError);
  }, [statusError]);

  if (statusLoading || !status) {
    return <LoadingState label="Завантаження таксономії..." />;
  }

  const isRunning = status.status === 'running' || status.status === 'queued';
  const tax = status.taxonomy;

  const list = tab === 'categories' ? catList : tab === 'attributes' ? attrList : valList;
  const pages = Math.max(1, Math.ceil((list.total || 1) / perPage));

  const handleRefresh = async () => {
    try { await api.post('/export/channels/rozetka/taxonomy/refresh', {}); reloadStatus(); }
    catch (e: any) { toast.push('error', e.message || 'Помилка'); }
  };

  const handleApplySearch = () => { setAppliedQ(q); setPage(1); };

  return (
    <div>
      <PageHeader title="Таксономия Rozetka" actions={
        <Button onClick={handleRefresh} disabled={isRunning} loading={isRunning}>
          {isRunning ? 'Оновлення...' : 'Оновити таксономію'}
        </Button>} />

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard label="Категорій" value={tax.categories} />
        <StatCard label="Атрибутів" value={tax.attributes} />
        <StatCard label="Значень" value={tax.values} />
        <StatCard label="Останнє оновлення"
          value={status.finished_at ? formatDateTime(status.finished_at) : '—'} />
      </div>

      {/* Refresh progress panel */}
      {isRunning && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
          <div className="flex items-center gap-2 mb-2">
            <Spinner size="sm" />
            <span className="font-medium">Оновлення таксономії Rozetka</span>
          </div>
          <div className="space-y-2 text-sm">
            <div>
              <div className="flex justify-between">
                <span>Категорії</span>
                <span>{status.categories.processed} / {status.categories.total}</span>
              </div>
              <ProgressBar pct={status.categories.total ? (status.categories.processed / status.categories.total) * 100 : 0} />
            </div>
            <div>
              <div className="flex justify-between">
                <span>Атрибути</span>
                <span>{status.attributes.categories_processed} / {status.attributes.categories_total} категорій</span>
              </div>
              <ProgressBar pct={status.attributes.categories_total ? (status.attributes.categories_processed / status.attributes.categories_total) * 100 : 0} />
            </div>
            <div>
              <div className="flex justify-between">
                <span>Значення</span>
                <span>{status.values.total} отримано</span>
              </div>
            </div>
            {status.current_operation && (
              <div className="text-xs text-gray-600">Остання операція: {status.current_operation}</div>
            )}
            {status.started_at && (
              <div className="text-xs text-gray-500">
                Тривалість: {fmtDuration(status.finished_at
                  ? (new Date(status.finished_at).getTime() - new Date(status.started_at).getTime()) / 1000
                  : (Date.now() - new Date(status.started_at).getTime()) / 1000)}
              </div>
            )}
            {status.errors > 0 && (<div className="text-sm text-red-600">Помилок: {status.errors}</div>)}
          </div>
        </div>
      )}

      {/* Completion result */}
      {['succeeded', 'partial', 'failed'].includes(status.status) && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 mb-6">
          <div className="flex items-center gap-2">
            <Badge tone={status.status === 'succeeded' ? 'green' : status.status === 'partial' ? 'yellow' : 'red'}>
              {fmtStatus(status.status).label}
            </Badge>
            {status.finished_at && (<span className="text-sm text-gray-600">Завершено: {formatDateTime(status.finished_at)}</span>)}
            {status.duration_seconds != null && (<span className="text-sm text-gray-500">Тривалість: {fmtDuration(status.duration_seconds)}</span>)}
          </div>
          <div className="mt-2 text-sm">
            Категорії: {status.categories.total} | Атрибути: {status.attributes.total} | Значення: {status.values.total}
          </div>
          {status.errors > 0 && (<div className="mt-1 text-sm text-red-600">Помилок: {status.errors}</div>)}
        </div>
      )}

      {/* Logs */}
      {status.logs && status.logs.length > 0 && (
        <details className="bg-gray-50 border border-gray-200 rounded-lg p-3 mb-4">
          <summary className="cursor-pointer text-sm font-medium text-gray-700">
            Журнал оновлення ({status.logs.length})
          </summary>
          <div className="mt-2 max-h-48 overflow-y-auto text-xs font-mono space-y-0.5">
            {status.logs.map((l, i) => (
              <div key={i} className="flex gap-2">
                <span className="text-gray-400 w-16">{l.level}</span>
                <span className="text-gray-600 break-all">{l.message}</span>
              </div>
            ))}
          </div>
        </details>
      )}

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-gray-200">
        {TABS.map((t) => (
          <button key={t.key} onClick={() => { setTab(t.key); setPage(1); }}
            className={`px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t.key ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Search / filters — not shown for history tab */}
      {tab !== 'history' && (
        <div className="flex flex-wrap items-end gap-3 mb-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Пошук</label>
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Назва або ID" className="w-48"
              onKeyDown={(e) => { if (e.key === 'Enter') handleApplySearch(); }} />
          </div>
          <Button onClick={handleApplySearch}>Застосувати</Button>
        </div>
      )}

      {/* Tables */}
      {tab === 'history' ? (
        <HistoryTable refreshTrigger={status?.run_id} />
      ) : list.loading ? <LoadingState /> : list.error ? <ErrorState message={list.error} onRetry={() => window.location.reload()} /> : (
        <>
                    {tab === 'categories' && (
            <Table head={<><Th>Rozetka ID</Th><Th>Назва</Th><Th>Батьківська</Th><Th>Шлях</Th><Th>Атриб.</Th></>}>
              {catList.items.length === 0 ? (
                <tr><td colSpan={5} className="p-6 text-center text-gray-400">Немає категорій</td></tr>
              ) : catList.items.map((r) => (
                <tr key={r.id} className="hover:bg-gray-50">
                  <Td className="text-xs font-mono">{r.external_id}</Td>
                  <Td className="max-w-60 truncate"><span title={r.name}>{r.name}</span></Td>
                  <Td className="text-xs font-mono">{r.parent_external_id || '—'}</Td>
                  <Td className="text-xs max-w-40 truncate"><span title={r.path || ''}>{r.path || '—'}</span></Td>
                  <Td className="text-xs">{r.attributes_count || 0}</Td>
                </tr>
              ))}
            </Table>
          )}
          {tab === 'attributes' && (
            <Table head={<><Th>Назва</Th><Th>Rozetka ID</Th><Th>Категорія</Th><Th>Тип</Th><Th>Од.</Th><Th>Обов'язковий</Th></>}>
              {attrList.items.length === 0 ? (
                <tr><td colSpan={6} className="p-6 text-center text-gray-400">Немає атрибутів</td></tr>
              ) : attrList.items.map((r) => (
                <tr key={r.id} className="hover:bg-gray-50">
                  <Td className="max-w-48 truncate"><span title={r.name}>{r.name}</span></Td>
                  <Td className="text-xs font-mono">{r.external_id}</Td>
                  <Td className="text-xs">{r.category_name}</Td>
                  <Td className="text-xs">{r.param_type || '—'}</Td>
                  <Td className="text-xs">{r.unit || '—'}</Td>
                  <Td className="text-xs">{r.is_required ? 'Так' : 'Ні'}</Td>
                </tr>
              ))}
            </Table>
          )}
          {tab === 'values' && (
            <Table head={<><Th>Атрибут</Th><Th>Rozetka ID</Th><Th>Значення</Th><Th>Категорія</Th></>}>
              {valList.items.length === 0 ? (
                <tr><td colSpan={4} className="p-6 text-center text-gray-400">Немає значень</td></tr>
              ) : valList.items.map((r) => (
                <tr key={r.id} className="hover:bg-gray-50">
                  <Td className="max-w-48 truncate">{r.attribute_name || '—'}</Td>
                  <Td className="text-xs font-mono">{r.external_id}</Td>
                  <Td className="max-w-48 truncate"><span title={r.value}>{r.value}</span></Td>
                  <Td className="text-xs">{r.category_name || r.category_external_id || '—'}</Td>
                </tr>
              ))}
            </Table>
          )}
          <Pagination page={page} pages={pages} total={list.total || 0} onPage={setPage}
            onGoToPage={(p) => setPage(Math.min(Math.max(p, 1), pages))}
            pageSize={perPage}
            onPageSizeChange={(n) => { setPerPage(n); setPage(1); }} />
        </>
      )}
    </div>
  );
}
