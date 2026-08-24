'use client';

import { useEffect, useState, useCallback } from 'react';
import { api, qs } from '@/lib/api';
import { formatDateTime, IMPORT_STATUS_LABELS, importStatusTone } from '@/lib/format';
import {
  PageHeader, Button, Select, Table, Th, Td, Badge,
  Pagination, LoadingState, ErrorState, EmptyState, Modal, ConfirmDialog, useToast,
} from '@/components/ui';

type Job = {
  id: number; supplier_id: number; supplier_name: string | null;
  import_type: string; status: string;
  started_at: string | null; finished_at: string | null; created_at: string;
  stats?: Record<string, unknown> | null;
  error_details?: Record<string, unknown> | string | null;
  percent?: number | null;
  progress?: { stage?: string; total?: number; processed?: number; created?: number; updated?: number; skipped?: number; failed?: number; message?: string } | null;
  current_stage?: string | null; current_item?: string | null;
  heartbeat_at?: string | null; last_activity_at?: string | null;
  total_count?: number; processed_count?: number; created_count?: number;
  updated_count?: number; skipped_count?: number; failed_count?: number;
  error_count?: number; warning_count?: number; cancel_requested?: boolean;
};
type Log = { id: number; level: string; message: string; item_ref: string | null; created_at: string };
type Sup = { id: number; code: string; name: string };
type ListResp = { items: Job[]; total: number; page: number; per_page: number };
type Detail = Job & { logs?: Log[] };

const STATUSES = ['queued', 'running', 'succeeded', 'failed', 'aborted', 'stale', 'cancelled'];
const TYPES = ['full', 'prices', 'stocks'];
const TYPE_LABELS: Record<string, string> = { full: 'Повний', prices: 'Ціни', stocks: 'Залишки' };
const STAGE_LABELS: Record<string, string> = {
  initializing: 'Ініціалізація імпорту',
  authenticating: 'Авторизація',
  downloading: 'Завантаження каталогу',
  parsing: 'Розбір каталогу',
  products: 'Обробка товарів',
  finalizing: 'Завершення',
  completed: 'Завершено',
};
const ACTIVE_STATUSES = new Set(['queued', 'running']);
const normalizeStatus = (s: string) => (s || '').toLowerCase();
const PER_PAGE = 20;

const nf = new Intl.NumberFormat('uk-UA');

function fmtTime(ts?: string | null): string {
  if (!ts) return '—';
  const d = new Date(ts);
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function elapsedMin(started?: string | null, finished?: string | null): string {
  if (!started) return '—';
  const a = new Date(started).getTime();
  if (isNaN(a)) return '—';
  const b = finished ? new Date(finished).getTime() : Date.now();
  const minutes = Math.max(0, Math.round((b - a) / 60000));
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h > 0 ? `${h}г ${m}хв` : `${m}хв`;
}

function progressValue(j: Job): number {
  const t = j.total_count || 0;
  const p = j.processed_count || 0;
  if (t > 0) return Math.min(100, Math.round((p / t) * 100));
  const prog = j.progress;
  const pt = prog?.processed || 0;
  const tt = prog?.total || 0;
  if (tt > 0) return Math.min(100, Math.round((pt / tt) * 100));
  return 0;
}
export default function ImportHistoryPage() {
  const toast = useToast();
  const [status, setStatus] = useState('');
  const [supplierId, setSupplierId] = useState('');
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ListResp | null>(null);
  const [suppliers, setSuppliers] = useState<Sup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tick, setTick] = useState(0);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [confirmDelete, setConfirmDelete] = useState<{ ids: number[]; count: number; bulk: boolean } | null>(null);
  const [confirmCancel, setConfirmCancel] = useState<Job | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const loadData = useCallback(() => {
    setLoading(true); setError('');
    api.get<ListResp>('/imports/jobs' + qs({
      page, per_page: PER_PAGE, status: status || undefined, supplier_id: supplierId || undefined,
    }))
      .then((d) => setData(d))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [page, status, supplierId]);

  useEffect(() => {
    api.get<{ items: Sup[] }>('/suppliers' + qs({ per_page: 100 }))
      .then((d) => setSuppliers(d.items || [])).catch(() => {});
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData, tick]);

  // Periodic refresh while any job is active (RUNNING/QUEUED).
  useEffect(() => {
    const hasActive = data?.items.some((j) => ACTIVE_STATUSES.has(normalizeStatus(j.status)));
    if (!hasActive) return;
    const t = setInterval(() => setTick((x) => x + 1), 5000);
    return () => clearInterval(t);
  }, [data]);

  // Detail modal live polling — no full page reload.
  useEffect(() => {
    if (!detail || !ACTIVE_STATUSES.has(normalizeStatus(detail.status))) return;
    const id = detail.id;
    const t = setInterval(() => {
      api.get<Detail>('/imports/jobs/' + id)
        .then((d) => { setDetail(d); setTick((x) => x + 1); })
        .catch(() => {});
    }, 3000);
    return () => clearInterval(t);
  }, [detail?.id, detail?.status]);

  // Reset selection when data changes (page switch, filter change)
const openDetail = async (j: Job) => {
    setDetail(j); setDetailLoading(true);
    try {
      const d = await api.get<Detail>('/imports/jobs/' + j.id);
      setDetail(d);
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
      setDetail(null);
    } finally { setDetailLoading(false); }
  };

  const handleCancel = async (j: Job) => {
    setCancelling(true);
    try {
      const res = await api.post<{ detail: string; cancelled_done?: boolean }>('/imports/jobs/' + j.id + '/cancel');
      toast.push('success', res.detail || 'Скасування імпорту запитано.');
      setDetail(null);
      setTick((x) => x + 1);
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally {
      setCancelling(false);
      setConfirmCancel(null);
    }
  };

  const handleDelete = async (ids: number[], bulk: boolean) => {
    setDeleting(true);
    try {
      if (ids.length === 1) {
        await api.delete('/imports/jobs/' + ids[0]);
        toast.push('success', `Імпорт #${ids[0]} видалено.`);
      } else {
        const res = await api.post<{ deleted: number; skipped: number; detail: string }>('/imports/jobs/bulk-delete', { ids });
        toast.push('success', `Видалено: ${res.deleted}, пропущено: ${res.skipped}.`);
      }
      setSelected(new Set());
      setDetail(null);
      if (data && data.items.length <= ids.length && page > 1) {
        setPage((p) => p - 1);
      } else {
        loadData();
      }
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally {
      setDeleting(false);
      setConfirmDelete(null);
    }
  };

  const pages = data ? Math.max(1, Math.ceil(data.total / data.per_page)) : 1;
const allVisibleIds = data?.items.map((j) => j.id) || [];
  const allVisibleSelected = allVisibleIds.length > 0 && allVisibleIds.every((id) => selected.has(id));

  const toggleSelect = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (allVisibleSelected) {
      setSelected(new Set());
    } else {
      setSelected(new Set(allVisibleIds));
    }
  };
  useEffect(() => { setSelected(new Set()); }, [data]);
return (
    <div>
      <PageHeader title="Історія імпортів" />

      <div className="bg-white border border-gray-200 rounded-lg p-3 mb-4 flex flex-wrap gap-3 items-end">
        <div className="w-48">
          <label className="block text-xs text-gray-500 mb-1">Постачальник</label>
          <Select value={supplierId} onChange={(e) => { setPage(1); setSupplierId(e.target.value); }}>
            <option value="">Усі</option>
            {suppliers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </Select>
        </div>
        <div className="w-40">
          <label className="block text-xs text-gray-500 mb-1">Статус</label>
          <Select value={status} onChange={(e) => { setPage(1); setStatus(e.target.value); }}>
            <option value="">Усі</option>
            {STATUSES.map((s) => <option key={s} value={s}>{IMPORT_STATUS_LABELS[s] || s}</option>)}
          </Select>
        </div>
        <Button variant="ghost" onClick={() => { setStatus(''); setSupplierId(''); setPage(1); }}>Скинути</Button>
        {selected.size > 0 && (
          <div className="flex items-center gap-2 ml-auto">
            <span className="text-xs text-gray-500">Обрано: {selected.size}</span>
            <Button size="sm" variant="danger" onClick={() => setConfirmDelete({ ids: Array.from(selected), count: selected.size, bulk: true })}>
              Видалити обрані
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setSelected(new Set())}>
              Скасувати вибір
            </Button>
          </div>
        )}
      </div>

      {error && <ErrorState message={error} onRetry={() => setTick((x) => x + 1)} />}
      {!error && loading && !data && <LoadingState label="Завантаження історії імпортів..." />}
      {!error && data?.items.length === 0 && <EmptyState title="Імпортів не знайдено" />}
      {data && data.items.length > 0 && (
        <>
          <Table head={<tr><Th className="w-10"><input type="checkbox" className="rounded" checked={allVisibleSelected} onChange={toggleSelectAll} title="Обрати всі на сторінці" /></Th><Th>ID</Th><Th>Постачальник</Th><Th>Тип</Th><Th>Статус</Th><Th>Створено</Th><Th>Завершено</Th><Th></Th></tr>}>
            {data.items.map((j) => {
              const ns = normalizeStatus(j.status);
              const isActive = ACTIVE_STATUSES.has(ns);
              const pct = j.percent ?? progressValue(j);
              return (
                <tr key={j.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => openDetail(j)}>
                  <Td>
                    <div onClick={(e) => e.stopPropagation()}>
                      <input type="checkbox" className="rounded" checked={selected.has(j.id)} onChange={() => toggleSelect(j.id)} />
                    </div>
                  </Td>
                  <Td className="font-mono text-xs">{j.id}</Td>
                  <Td className="text-sm font-medium">{j.supplier_name || '—'}</Td>
                  <Td className="text-sm">{TYPE_LABELS[j.import_type] || j.import_type}</Td>
                  <Td>
                    <div className="max-w-[220px]">
                      <Badge tone={importStatusTone(ns)}>{IMPORT_STATUS_LABELS[ns] || j.status}</Badge>
                      {(ns === 'running' || ns === 'queued') && (
                        <div className="mt-1 text-[11px] text-gray-500 space-y-0.5 leading-4">
                          {j.total_count ? (
                            <span>{nf.format(j.processed_count || 0)} / {nf.format(j.total_count)}</span>
                          ) : null}
                          {pct > 0 && (
                            <div className="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden">
                              <div className="h-full bg-blue-500" style={{ width: pct + '%' }} />
                            </div>
                          )}
                          <div>Остання активність: {fmtTime(j.last_activity_at || j.heartbeat_at)}</div>
                        </div>
                      )}
                      {ns === 'stale' && (
                        <div className="mt-1 text-[11px] text-yellow-700 leading-4">
                          <div>Остання активність: {fmtTime(j.last_activity_at)}</div>
                          {j.last_activity_at && <div>Активності немає {elapsedMin(j.last_activity_at)}</div>}
                        </div>
                      )}
                    </div>
                  </Td>
                  <Td className="whitespace-nowrap text-xs text-gray-500">{formatDateTime(j.created_at)}</Td>
                  <Td className="whitespace-nowrap text-xs text-gray-500">{formatDateTime(j.finished_at)}</Td>
                  <Td>
                    <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                      <Button size="sm" variant="ghost" onClick={() => openDetail(j)}>Деталі</Button>
                      {isActive && (
                        <Button size="sm" variant="ghost" className="text-orange-600 hover:text-orange-800" onClick={() => setConfirmCancel(j)}>Скасувати</Button>
                      )}
                      <Button size="sm" variant="ghost" className="text-red-600 hover:text-red-800" disabled={isActive} title={isActive ? 'Активний імпорт не можна видалити' : 'Видалити'} onClick={() => setConfirmDelete({ ids: [j.id], count: 1, bulk: false })}>🗑</Button>
                    </div>
                  </Td>
                </tr>
              );
            })}
          </Table>
          <div className="mt-4">
            <Pagination
              page={data.page} pages={pages} total={data.total}
              onPage={(p) => setPage(p)}
              onGoToPage={(p) => setPage(p)}
              pageSize={PER_PAGE}
            />
          </div>
        </>
)}
<Modal open={!!detail} title={detail ? 'Імпорт #' + detail.id : ''} onClose={() => setDetail(null)} wide>
        {detailLoading && <LoadingState label="Завантаження деталей..." />}
        {!detailLoading && detail && <JobDetailView job={detail} onRequestCancel={() => setConfirmCancel(detail)} />}
      </Modal>

      <ConfirmDialog
        open={!!confirmCancel}
        title="Скасування імпорту"
        message={confirmCancel ? `Скасувати імпорт #${confirmCancel.id}? Процес зупиниться на безпечній точці. Запис історії збережеться зі статусом «Скасовано».` : ''}
        confirmLabel={confirmCancel ? `Скасувати імпорт #${confirmCancel.id}` : 'Скасувати імпорт'}
        busy={cancelling}
        onConfirm={() => confirmCancel && handleCancel(confirmCancel)}
        onCancel={() => setConfirmCancel(null)}
      />

      <ConfirmDialog
        open={!!confirmDelete}
        title="Підтвердження видалення"
        message={
          confirmDelete
            ? confirmDelete.count === 1
              ? `Ви впевнені, що хочете видалити імпорт #${confirmDelete.ids[0]}? Це видалить лише запис історії імпорту, товари та інші дані залишаться незмінними.`
              : `Ви впевнені, що хочете видалити ${confirmDelete.count} записів історії імпортів? Активні імпорти (RUNNING) буде пропущено.`
            : ''
        }
        confirmLabel={confirmDelete && confirmDelete.count === 1 ? `Видалити імпорт #${confirmDelete.ids[0]}` : confirmDelete ? `Видалити ${confirmDelete.count} записів` : ''}
        danger
        busy={deleting}
        onConfirm={() => confirmDelete && handleDelete(confirmDelete.ids, confirmDelete.bulk)}
        onCancel={() => { setConfirmDelete(null); }}
      />
    </div>
  );
}
const LOG_TONE: Record<string, string> = {
  error: 'bg-red-50/60',
  warning: 'bg-yellow-50/40',
  success: 'bg-green-50/40',
};
const LOG_TEXT: Record<string, string> = {
  error: 'text-red-600',
  warning: 'text-yellow-700',
  success: 'text-green-600',
};

function JobDetailView({ job, onRequestCancel }: { job: Detail; onRequestCancel: () => void }) {
  const ns = normalizeStatus(job.status);
  const isActive = ACTIVE_STATUSES.has(ns);
  const pct = job.percent ?? progressValue(job);
  const logs = job.logs || [];
  const logsChron = [...logs].reverse();

  return (
    <div className="space-y-4 text-sm">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-xs">
        <div><span className="text-gray-500">Постачальник:</span> {job.supplier_name || '—'}</div>
        <div><span className="text-gray-500">Тип:</span> {TYPE_LABELS[job.import_type] || job.import_type}</div>
        <div><span className="text-gray-500">Статус:</span> <Badge tone={importStatusTone(ns)}>{IMPORT_STATUS_LABELS[ns] || job.status}</Badge></div>
        <div><span className="text-gray-500">Почато:</span> {formatDateTime(job.started_at)}</div>
        <div><span className="text-gray-500">Тривалість:</span> {elapsedMin(job.started_at, job.finished_at)}</div>
        <div><span className="text-gray-500">Завершено:</span> {formatDateTime(job.finished_at)}</div>
        <div><span className="text-gray-500">Остання активність:</span> {fmtTime(job.last_activity_at)}</div>
        <div><span className="text-gray-500">Heartbeat:</span> {fmtTime(job.heartbeat_at)}</div>
        <div><span className="text-gray-500">Створено:</span> {formatDateTime(job.created_at)}</div>
      </div>

      {(isActive || pct > 0) && (
        <div>
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>
              {job.total_count
                ? `Прогрес: ${nf.format(job.processed_count || 0)} / ${nf.format(job.total_count)}`
                : `Прогрес: ${job.progress?.message || '...'}`}
            </span>
            <span>{pct}%</span>
          </div>
          <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
            <div className={isActive ? 'h-full bg-blue-500 transition-all' : 'h-full bg-green-500'} style={{ width: pct + '%' }} />
          </div>
        </div>
      )}

      {job.total_count !== undefined && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
          {[
            ['Оброблено', job.processed_count],
            ['Створено', job.created_count],
            ['Оновлено', job.updated_count],
            ['Пропущено', job.skipped_count],
            ['Помилок', job.failed_count],
            ['Попереджень', job.warning_count],
          ].map(([label, value]) => (
            <div key={String(label)} className="bg-gray-50 rounded border border-gray-100 px-3 py-2">
              <div className="text-gray-500">{label}: <b className="text-gray-800">{nf.format(Number(value) || 0)}</b></div>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
        <div><span className="text-gray-500">Етап:</span> <b>{STAGE_LABELS[job.current_stage || ''] || job.current_stage || '—'}</b></div>
        <div><span className="text-gray-500">Поточний SKU:</span> <span className="font-mono">{job.current_item || '—'}</span></div>
        <div><span className="text-gray-500">Помилок (логів):</span> {job.error_count || 0}</div>
      </div>

      {isActive && (
        <Button variant="danger" onClick={onRequestCancel}>Скасувати імпорт</Button>
      )}

      {!!job.error_details && (
        <div>
          <div className="text-red-600 font-medium mb-1">Помилки:</div>
          <pre className="bg-red-50 border border-red-100 rounded p-3 text-xs overflow-x-auto max-h-40 whitespace-pre-wrap">
            {typeof job.error_details === 'string' ? job.error_details : JSON.stringify(job.error_details, null, 2)}
          </pre>
        </div>
      )}

      <div>
        <div className="text-gray-500 mb-1">Журнал ({logsChron.length} записів):</div>
        {logsChron.length === 0 ? (
          <p className="text-xs text-gray-400">Записів журналу немає.</p>
        ) : (
          <div className="border border-gray-100 rounded divide-y divide-gray-50 max-h-72 overflow-y-auto">
            {logsChron.map((l) => (
              <div key={l.id} className={'px-3 py-1.5 text-xs flex gap-3 ' + (LOG_TONE[l.level] || '')}>
                <span className="text-gray-400 whitespace-nowrap">{new Date(l.created_at).toLocaleTimeString('uk-UA')}</span>
                <span className={'font-mono uppercase w-14 ' + (LOG_TEXT[l.level] || 'text-gray-400')}>{l.level}</span>
                <span className="flex-1 break-all">{l.message}{l.item_ref ? ' (' + l.item_ref + ')' : ''}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}