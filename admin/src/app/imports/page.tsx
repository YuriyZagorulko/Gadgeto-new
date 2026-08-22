'use client';

import { useEffect, useState } from 'react';
import { api, qs } from '@/lib/api';
import { formatDateTime, IMPORT_STATUS_LABELS, importStatusTone } from '@/lib/format';
import { PageHeader, Button, Select, Table, Th, Td, Badge, LoadingState, ErrorState, EmptyState, Modal, ConfirmDialog, useToast } from '@/components/ui';

type Job = {
  id: number; supplier_id: number; supplier_name: string | null;
  import_type: string; status: string;
  started_at: string | null; finished_at: string | null; created_at: string;
  stats?: Record<string, unknown> | null;
  error_details?: unknown;
};
type Log = { id: number; level: string; message: string; item_ref: string | null; created_at: string };
type Sup = { id: number; code: string; name: string };
type ListResp = { items: Job[]; total: number; page: number; per_page: number };

const STATUSES = ['queued', 'running', 'succeeded', 'failed', 'aborted'];
const TYPES = ['full', 'prices', 'stocks'];
const TYPE_LABELS: Record<string, string> = { full: 'Повний', prices: 'Ціни', stocks: 'Залишки' };

export default function ImportsPage() {
  const toast = useToast();
  const [status, setStatus] = useState('');
  const [supplierId, setSupplierId] = useState('');
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ListResp | null>(null);
  const [suppliers, setSuppliers] = useState<Sup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tick, setTick] = useState(0);

  const [runOpen, setRunOpen] = useState(false);
  const [runCode, setRunCode] = useState('');
  const [runType, setRunType] = useState('full');
  const [running, setRunning] = useState(false);

  const [detail, setDetail] = useState<(Job & { logs?: Log[] }) | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    api.get<{ items: Sup[] }>('/suppliers' + qs({ per_page: 100 })).then((d) => setSuppliers(d.items || [])).catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError('');
    api.get<ListResp>('/imports/jobs' + qs({
      page, per_page: 20, status: status || undefined, supplier_id: supplierId || undefined,
    }))
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [page, status, supplierId, tick]);

  // Auto-refresh while any job is queued/running
  useEffect(() => {
    const hasActive = data?.items.some((j) => j.status === 'queued' || j.status === 'running');
    if (!hasActive) return;
    const t = setInterval(() => setTick((x) => x + 1), 5000);
    return () => clearInterval(t);
  }, [data]);

  const openDetail = async (j: Job) => {
    setDetail(j); setDetailLoading(true);
    try {
      const d = await api.get<Job & { logs: Log[] }>(`/imports/jobs/${j.id}`);
      setDetail(d);
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
      setDetail(null);
    } finally { setDetailLoading(false); }
  };

  const runImport = async () => {
    if (!runCode) { toast.push('error', 'Оберіть постачальника'); return; }
    setRunning(true);
    try {
      const res = await api.post<{ detail: string }>('/imports/run', { supplier_code: runCode, import_type: runType });
      toast.push('success', res.detail || 'Імпорт запущено');
      setRunOpen(false); setPage(1); setTick((t) => t + 1);
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally { setRunning(false); }
  };

  const statsChips = (j: Job): Array<[string, unknown]> => {
    if (!j.stats || typeof j.stats !== 'object') return [];
    return Object.entries(j.stats).filter(([, v]) => typeof v === 'number').slice(0, 4) as Array<[string, unknown]>;
  };

  return (
    <div>
      <PageHeader
        title="Імпорти"
        actions={<Button onClick={() => { setRunCode(suppliers[0]?.code || ''); setRunOpen(true); }}>▶ Запустити імпорт</Button>}
      />

      <div className="bg-white border border-gray-200 rounded-lg p-3 mb-4 flex flex-wrap gap-3 items-end">
        <div className="w-48">
          <label className="block text-xs text-gray-500 mb-1">Статус</label>
          <Select value={status} onChange={(e) => { setPage(1); setStatus(e.target.value); }}>
            <option value="">Усі статуси</option>
            {STATUSES.map((s) => <option key={s} value={s}>{IMPORT_STATUS_LABELS[s]}</option>)}
          </Select>
        </div>
        <div className="w-52">
          <label className="block text-xs text-gray-500 mb-1">Постачальник</label>
          <Select value={supplierId} onChange={(e) => { setPage(1); setSupplierId(e.target.value); }}>
            <option value="">Усі постачальники</option>
            {suppliers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </Select>
        </div>
      </div>

      {error && <ErrorState message={error} onRetry={() => setTick((t) => t + 1)} />}
      {!error && loading && !data && <LoadingState label="Завантаження імпортів..." />}
      {!error && data?.items.length === 0 && <EmptyState title="Імпортів не знайдено" hint="Запустіть перший імпорт кнопкою вище." />}
      {data && data.items.length > 0 && (
        <>
          <Table head={<tr><Th>ID</Th><Th>Постачальник</Th><Th>Тип</Th><Th>Статус</Th><Th>Результат</Th><Th>Почато</Th><Th>Завершено</Th><Th></Th></tr>}>
            {data.items.map((j) => (
              <tr key={j.id} className="hover:bg-gray-50">
                <Td className="font-mono text-xs">#{j.id}</Td>
                <Td className="font-medium">{j.supplier_name || '—'}</Td>
                <Td>{TYPE_LABELS[j.import_type] || j.import_type}</Td>
                <Td><Badge tone={importStatusTone(j.status)}>{IMPORT_STATUS_LABELS[j.status] || j.status}</Badge></Td>
                <Td>
                  <div className="flex gap-1 flex-wrap">
                    {statsChips(j).map(([k, v]) => (
                      <span key={k} className="text-xs bg-gray-100 rounded px-1.5 py-0.5 text-gray-600">{k}: {String(v)}</span>
                    ))}
                  </div>
                </Td>
                <Td className="whitespace-nowrap text-xs text-gray-500">{formatDateTime(j.started_at)}</Td>
                <Td className="whitespace-nowrap text-xs text-gray-500">{formatDateTime(j.finished_at)}</Td>
                <Td><Button size="sm" variant="secondary" onClick={() => openDetail(j)}>Деталі</Button></Td>
              </tr>
            ))}
          </Table>
          {data.total > data.per_page && (
            <div className="mt-4">
              <div className="text-sm text-gray-500">Сторінка {data.page} · Всього: {data.total}</div>
              <div className="flex gap-2 mt-2">
                <Button size="sm" variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Назад</Button>
                <Button size="sm" variant="secondary" disabled={page >= Math.ceil(data.total / data.per_page)} onClick={() => setPage(page + 1)}>Далі</Button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Run import modal */}
      <Modal open={runOpen} title="Запуск імпорту" onClose={() => setRunOpen(false)}>
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Постачальник *</label>
            <Select value={runCode} onChange={(e) => setRunCode(e.target.value)}>
              <option value="">Оберіть постачальника...</option>
              {suppliers.map((s) => <option key={s.id} value={s.code}>{s.name} ({s.code})</option>)}
            </Select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Тип імпорту</label>
            <Select value={runType} onChange={(e) => setRunType(e.target.value)}>
              {TYPES.map((t) => <option key={t} value={t}>{TYPE_LABELS[t] || t}</option>)}
            </Select>
          </div>
          <p className="text-xs text-gray-400">
            Імпорт виконається у фоні. Прогрес і результат з'являться в таблиці нижче (список оновлюється автоматично).
          </p>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setRunOpen(false)}>Скасувати</Button>
            <Button loading={running} onClick={runImport}>Запустити</Button>
          </div>
        </div>
      </Modal>

      {/* Job details modal */}
      <Modal open={!!detail} title={detail ? `Імпорт #${detail.id}` : ''} onClose={() => setDetail(null)} wide>
        {detailLoading && <LoadingState label="Завантаження деталей..." />}
        {!detailLoading && detail && (
          <div className="space-y-4 text-sm">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              <div><span className="text-gray-500">Постачальник:</span> {detail.supplier_name || '—'}</div>
              <div><span className="text-gray-500">Тип:</span> {TYPE_LABELS[detail.import_type] || detail.import_type}</div>
              <div><Badge tone={importStatusTone(detail.status)}>{IMPORT_STATUS_LABELS[detail.status] || detail.status}</Badge></div>
              <div><span className="text-gray-500">Створено:</span> {formatDateTime(detail.created_at)}</div>
              <div><span className="text-gray-500">Почато:</span> {formatDateTime(detail.started_at)}</div>
              <div><span className="text-gray-500">Завершено:</span> {formatDateTime(detail.finished_at)}</div>
            </div>

            {detail.stats && Object.keys(detail.stats).length > 0 && (
              <div>
                <div className="text-gray-500 mb-1">Статистика:</div>
                <pre className="bg-gray-50 border border-gray-100 rounded p-3 text-xs overflow-x-auto max-h-40">
                  {JSON.stringify(detail.stats, null, 2)}
                </pre>
              </div>
            )}

            {detail.error_details ? (
              <div>
                <div className="text-red-600 font-medium mb-1">Помилки:</div>
                <pre className="bg-red-50 border border-red-100 rounded p-3 text-xs overflow-x-auto max-h-40 whitespace-pre-wrap">
                  {typeof detail.error_details === 'string'
                    ? detail.error_details
                    : JSON.stringify(detail.error_details, null, 2)}
                </pre>
              </div>
            ) : null}

            <div>
              <div className="text-gray-500 mb-1">Журнал (останні записи):</div>
              {!detail.logs || detail.logs.length === 0 ? (
                <p className="text-xs text-gray-400">Записів журналу немає.</p>
              ) : (
                <div className="border border-gray-100 rounded divide-y divide-gray-50 max-h-64 overflow-y-auto">
                  {detail.logs.map((l) => (
                    <div key={l.id} className={`px-3 py-1.5 text-xs flex gap-3 ${l.level === 'error' ? 'bg-red-50/60' : l.level === 'warning' ? 'bg-yellow-50/40' : ''}`}>
                      <span className="text-gray-400 whitespace-nowrap">{new Date(l.created_at).toLocaleTimeString('uk-UA')}</span>
                      <span className={`font-mono uppercase w-14 ${l.level === 'error' ? 'text-red-600' : l.level === 'warning' ? 'text-yellow-700' : 'text-gray-400'}`}>{l.level}</span>
                      <span className="flex-1 break-all">{l.message}{l.item_ref ? ` (${l.item_ref})` : ''}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}



