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
};
type Log = { id: number; level: string; message: string; item_ref: string | null; created_at: string };
type Sup = { id: number; code: string; name: string };
type ListResp = { items: Job[]; total: number; page: number; per_page: number };

const STATUSES = ['queued', 'running', 'succeeded', 'failed', 'aborted'];
const TYPES = ['full', 'prices', 'stocks'];
const TYPE_LABELS: Record<string, string> = { full: 'Повний', prices: 'Ціни', stocks: 'Залишки' };
const normalizeStatus = (s: string) => (s || '').toLowerCase();
const PER_PAGE = 20;

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
  const [detail, setDetail] = useState<(Job & { logs?: Log[] }) | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [confirmDelete, setConfirmDelete] = useState<{ ids: number[]; count: number; bulk: boolean } | null>(null);
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

  useEffect(() => {
    const hasActive = data?.items.some((j) => j.status === 'queued' || j.status === 'running');
    if (!hasActive) return;
    const t = setInterval(() => setTick((x) => x + 1), 5000);
    return () => clearInterval(t);
  }, [data]);

  // Reset selection when data changes (page switch, filter change)
  useEffect(() => { setSelected(new Set()); }, [data]);

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

  const openDetail = async (j: Job) => {
    setDetail(j); setDetailLoading(true);
    try {
      const d = await api.get<Job & { logs: Log[] }>('/imports/jobs/' + j.id);
      setDetail(d);
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
      setDetail(null);
    } finally { setDetailLoading(false); }
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
              const isActive = ns === 'queued' || ns === 'running';
              return (
                <tr key={j.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => openDetail(j)}>
                  <Td onClick={(e) => e.stopPropagation()}>
                    <input type="checkbox" className="rounded" checked={selected.has(j.id)} onChange={() => toggleSelect(j.id)} />
                  </Td>
                  <Td className="font-mono text-xs">{j.id}</Td>
                  <Td className="text-sm font-medium">{j.supplier_name || '—'}</Td>
                  <Td className="text-sm">{TYPE_LABELS[j.import_type] || j.import_type}</Td>
                  <Td><Badge tone={importStatusTone(ns)}>{IMPORT_STATUS_LABELS[ns] || j.status}</Badge></Td>
                  <Td className="whitespace-nowrap text-xs text-gray-500">{formatDateTime(j.created_at)}</Td>
                  <Td className="whitespace-nowrap text-xs text-gray-500">{formatDateTime(j.finished_at)}</Td>
                  <Td>
                    <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                      <Button size="sm" variant="ghost" onClick={() => openDetail(j)}>Деталі</Button>
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
        {!detailLoading && detail && (
          <div className="space-y-4 text-sm">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              <div><span className="text-gray-500">Постачальник:</span> {detail.supplier_name || '—'}</div>
              <div><span className="text-gray-500">Тип:</span> {TYPE_LABELS[detail.import_type] || detail.import_type}</div>
              <div><Badge tone={importStatusTone(normalizeStatus(detail.status))}>{IMPORT_STATUS_LABELS[normalizeStatus(detail.status)] || detail.status}</Badge></div>
              <div><span className="text-gray-500">Створено:</span> {formatDateTime(detail.created_at)}</div>
              <div><span className="text-gray-500">Почато:</span> {formatDateTime(detail.started_at)}</div>
              <div><span className="text-gray-500">Завершено:</span> {formatDateTime(detail.finished_at)}</div>
            </div>
            {!!detail.stats && Object.keys(detail.stats as Record<string, unknown>).length > 0 && (
              <div>
                <div className="text-gray-500 mb-1">Статистика:</div>
                <pre className="bg-gray-50 border border-gray-100 rounded p-3 text-xs overflow-x-auto max-h-40">{JSON.stringify(detail.stats as Record<string, unknown> || {}, null, 2)}</pre>
              </div>
            )}
            {!!detail.error_details && (
              <div>
                <div className="text-red-600 font-medium mb-1">Помилки:</div>
                <pre className="bg-red-50 border border-red-100 rounded p-3 text-xs overflow-x-auto max-h-40 whitespace-pre-wrap">
                  {typeof detail.error_details === 'string' ? detail.error_details : JSON.stringify(detail.error_details, null, 2)}
                </pre>
              </div>
            )}
            <div>
              <div className="text-gray-500 mb-1">Журнал (останні записи):</div>
              {!detail.logs || detail.logs.length === 0 ? (
                <p className="text-xs text-gray-400">Записів журналу немає.</p>
              ) : (
                <div className="border border-gray-100 rounded divide-y divide-gray-50 max-h-64 overflow-y-auto">
                  {detail.logs.map((l) => (
                    <div key={l.id} className={'px-3 py-1.5 text-xs flex gap-3 ' + (l.level === 'error' ? 'bg-red-50/60' : l.level === 'warning' ? 'bg-yellow-50/40' : '')}>
                      <span className="text-gray-400 whitespace-nowrap">{new Date(l.created_at).toLocaleTimeString('uk-UA')}</span>
                      <span className={'font-mono uppercase w-14 ' + (l.level === 'error' ? 'text-red-600' : l.level === 'warning' ? 'text-yellow-700' : 'text-gray-400')}>{l.level}</span>
                      <span className="flex-1 break-all">{l.message}{l.item_ref ? ' (' + l.item_ref + ')' : ''}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={!!confirmDelete}
        title="Підтвердження видалення"
        message={
          confirmDelete
            ? confirmDelete.count === 1
              ? `Ви впевнені, що хочете видалити імпорт #${confirmDelete.ids[0]}? Це видалить лише запис історії імпорту, товари та інші дані залишаться незмінними.`
              : `Ви впевнені, що хочете видалити ${confirmDelete.count} записів історії імпортів? Активні імпорти (QUEUED/RUNNING) буде пропущено.`
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
