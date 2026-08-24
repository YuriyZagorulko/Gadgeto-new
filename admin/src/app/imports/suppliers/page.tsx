'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { api, qs } from '@/lib/api';
import { formatDateTime, IMPORT_STATUS_LABELS, importStatusTone } from '@/lib/format';
import { PageHeader, Button, Table, Th, Td, Badge, LoadingState, ErrorState, useToast } from '@/components/ui';

type Supplier = {
  id: number; code: string; name: string; enabled: boolean;
  products_count: number; categories_count: number; attributes_count: number;
  imports_count: number; last_import_at: string | null;
};
type Detail = Supplier & { config?: Record<string, unknown> | null };
type Job = {
  id: number; supplier_id: number; supplier_name: string | null;
  import_type: string; status: string;
  started_at: string | null; finished_at: string | null; created_at: string;
  stats?: Record<string, unknown> | null; error_details?: unknown;
};
type ImportLog = { id: number; level: string; message: string; item_ref: string | null; created_at: string };
type ImportProgress = {
  id: number; status: string; supplier_name: string | null; supplier_code: string | null;
  current_stage: string | null; started_at: string | null; finished_at: string | null;
  progress?: { stage: string; total: number; processed: number; created: number; updated: number; skipped: number; failed: number; message: string } | null;
  stats?: Record<string, unknown> | null;
  error_details?: { error: string } | null;
  logs: ImportLog[];
};

const FIXED_SUPPLIERS = [
  { code: 'itlink', name: 'IT-Link' },
  { code: 'dclink', name: 'DC-Link' },
] as const;

const TYPE_LABELS: Record<string, string> = { full: 'Повний', prices: 'Ціни', stock: 'Залишки' };

const normStatus = (s: string): string => (s || '').toLowerCase();

const LEVEL_COLORS: Record<string, string> = {
  INFO: 'text-gray-600',
  WARNING: 'text-yellow-700',
  ERROR: 'text-red-600',
  SUCCESS: 'text-green-600',
};

const LEVEL_BADGES: Record<string, string> = {
  INFO: '[INFO]',
  WARNING: '[WARN]',
  ERROR: '[ERROR]',
  SUCCESS: '[OK]',
};

function formatTime(ts: string): string {
  try { return new Date(ts).toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit', second: '2-digit' }); }
  catch { return ''; }
}

export default function SuppliersPage() {
  const toast = useToast();
  const [activeCode, setActiveCode] = useState<(typeof FIXED_SUPPLIERS)[number]['code']>('itlink');
  const [suppliers, setSuppliers] = useState<Record<string, Detail>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobsLoading, setJobsLoading] = useState(true);
  const [jobsTick, setJobsTick] = useState(0);

  const [runningAction, setRunningAction] = useState<string | null>(null);

  // Live import monitor
  const [activeJobId, setActiveJobId] = useState<number | null>(null);
  const [importProgress, setImportProgress] = useState<ImportProgress | null>(null);
  const [importPollTick, setImportPollTick] = useState(0);
  const [importStarted, setImportStarted] = useState(false);
  const consoleRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  const active = suppliers[activeCode];

  const loadSupplier = useCallback(async (code: string) => {
    try {
      const list = await api.get<{ items: Supplier[] }>('/suppliers' + qs({ per_page: 100 }));
      const found = (list.items || []).find((s) => s.code === code);
      if (!found) throw new Error('Постачальника не знайдено. Зверніться до адміністратора.');
      const d = await api.get<Detail>(`/suppliers/${found.id}`);
      setSuppliers((prev) => ({ ...prev, [code]: d }));
      setError('');
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadSupplier(activeCode); }, [activeCode, loadSupplier]);

  const supplierId = active?.id;
  useEffect(() => {
    if (!supplierId) return;
    let cancelled = false;
    setJobsLoading(true);
    api.get<{ items: Job[] }>('/imports/jobs' + qs({ supplier_id: supplierId, per_page: 10 }))
      .then((d) => { if (!cancelled) setJobs(d.items || []); })
      .catch(() => { if (!cancelled) setJobs([]); })
      .finally(() => { if (!cancelled) setJobsLoading(false); });
    return () => { cancelled = true; };
  }, [supplierId, jobsTick]);

  const hasActiveJob = jobs.some((j) => ['queued', 'running'].includes(normStatus(j.status)));
  useEffect(() => {
    if (!hasActiveJob) return;
    const t = setInterval(() => setJobsTick((x) => x + 1), 4000);
    return () => clearInterval(t);
  }, [hasActiveJob]);

  // Poll import progress
  useEffect(() => {
    if (!activeJobId || !importStarted) return;
    let cancelled = false;
    api.get<ImportProgress>(`/imports/jobs/${activeJobId}/progress`)
      .then((d) => { if (!cancelled) setImportProgress(d); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [activeJobId, importPollTick, importStarted]);

  // Auto-poll every 3s while running
  useEffect(() => {
    if (!importProgress || ['SUCCEEDED', 'FAILED', 'STALE', 'CANCELLED', 'ABORTED'].includes(importProgress.status)) {
      return;
    }
    const t = setInterval(() => setImportPollTick((x) => x + 1), 3000);
    return () => clearInterval(t);
  }, [importProgress]);

  // Auto-scroll console
  useEffect(() => {
    if (autoScroll && consoleRef.current) {
      consoleRef.current.scrollTop = consoleRef.current.scrollHeight;
    }
  }, [importProgress?.logs, autoScroll]);

  const startImport = async () => {
    if (!active) return;
    setRunningAction('full');
    try {
      const res = await api.post<{ ok: boolean; job_id: number; detail: string }>('/imports/start', {
        supplier_code: active.code,
        import_type: 'full',
      });
      toast.push('success', res.detail || 'Імпорт запущено');
      setActiveJobId(res.job_id);
      setImportStarted(true);
      setImportProgress(null);
      setImportPollTick((x) => x + 1);
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally {
      setRunningAction(null);
    }
  };

  const progress = importProgress?.progress;
  const isRunning = importProgress?.status === 'RUNNING' || importProgress?.status === 'QUEUED';
  const isDone = importProgress?.status === 'SUCCEEDED';
  const isFailed = importProgress?.status === 'FAILED';

  const logLines = importProgress?.logs || [];

  return (
    <div>
      <PageHeader title="Постачальники" />
      <p className="text-xs text-gray-400 mb-4">
        Постачальники — фіксовані системні інтеграції, визначені в коді. Створення та видалення непередбачені.
      </p>

      {/* Fixed supplier tabs */}
      <div className="flex gap-1 mb-4 border-b border-gray-200">
        {FIXED_SUPPLIERS.map((s) => (
          <button key={s.code} onClick={() => { setActiveCode(s.code); setActiveJobId(null); setImportProgress(null); setImportStarted(false); }}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition ${
              activeCode === s.code ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-800'
            }`}
          >
            {s.name}
          </button>
        ))}
      </div>

      {error && <ErrorState message={error} onRetry={() => { setLoading(true); loadSupplier(activeCode); }} />}
      {!error && loading && !active && <LoadingState label="Завантаження постачальника..." />}
      {!error && !loading && active && (
        <div className="space-y-6">
          {/* Info card */}
          <div className="bg-white border border-gray-200 rounded-lg p-5">
            <div className="flex items-center justify-between gap-3 flex-wrap mb-3">
              <h3 className="font-semibold text-gray-900">{active.name}</h3>
              <div className="flex items-center gap-2">
                <Badge tone={active.enabled ? 'green' : 'gray'}>{active.enabled ? 'Активний' : 'Вимкнений'}</Badge>
                <Badge tone="blue">Системна інтеграція</Badge>
              </div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
              <div><span className="text-gray-500">Код:</span> <span className="font-mono text-xs">{active.code}</span></div>
              <div><span className="text-gray-500">Товарів:</span> {active.products_count}</div>
              <div><span className="text-gray-500">Категорій:</span> {active.categories_count}</div>
              <div><span className="text-gray-500">Атрибутів:</span> {active.attributes_count}</div>
              <div><span className="text-gray-500">Останній імпорт:</span> {formatDateTime(active.last_import_at)}</div>
            </div>
          </div>

          {/* Import actions */}
          <section>
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">Імпорт</h3>
            <div className="bg-white border border-gray-200 rounded-lg p-4 flex flex-wrap gap-2 items-center">
              <Button
                loading={runningAction === 'full'}
                disabled={runningAction !== null || !active.enabled || isRunning}
                onClick={startImport}
              >
                Імпортувати товари
              </Button>
              {isRunning && (
                <span className="text-xs text-blue-700 bg-blue-50 border border-blue-200 rounded px-2 py-1">
                  Імпорт виконується...
                </span>
              )}
              {!active.enabled && (
                <span className="text-xs text-yellow-700 bg-yellow-50 border border-yellow-100 rounded px-2 py-1">
                  Постачальника вимкнено — імпорт недоступний.
                </span>
              )}
            </div>
          </section>

          {/* Live import monitor */}
          {importStarted && importProgress && (
            <section>
              <div className={`border rounded-lg p-5 ${
                isRunning ? 'bg-blue-50 border-blue-200' :
                isDone ? 'bg-green-50 border-green-200' :
                isFailed ? 'bg-red-50 border-red-200' : 'bg-white border-gray-200'
              }`}>
                {/* Header */}
                <div className="flex items-center gap-2 mb-4">
                  <h3 className="font-semibold text-gray-900">
                    {active.name} — Імпорт товарів
                  </h3>
                  {isRunning && <Badge tone="blue">Виконується</Badge>}
                  {isDone && <Badge tone="green">Завершено</Badge>}
                  {isFailed && <Badge tone="red">Помилка</Badge>}
                </div>

                {/* Progress bar */}
                {progress && progress.total > 0 && (
                  <div className="mb-4">
                    <div className="w-full bg-gray-200 rounded-full h-3">
                      <div
                        className={`h-3 rounded-full transition-all duration-500 ${
                          isFailed ? 'bg-red-500' : isDone ? 'bg-green-500' : 'bg-blue-500'
                        }`}
                        style={{ width: `${Math.min(100, Math.round(progress.processed / progress.total * 100))}%` }}
                      />
                    </div>
                  </div>
                )}

                {/* Counters */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4 text-sm">
                  <div>
                    <span className="text-gray-500">Оброблено:</span>
                    <span className="font-medium ml-1">
                      {progress?.processed ?? 0}{progress?.total ? ` / ${progress.total}` : ''}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500">Створено:</span>
                    <span className="font-medium ml-1 text-green-700">{progress?.created ?? 0}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Оновлено:</span>
                    <span className="font-medium ml-1 text-blue-700">{progress?.updated ?? 0}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Помилок:</span>
                    <span className="font-medium ml-1 text-red-700">{progress?.failed ?? 0}</span>
                  </div>
                </div>

                {/* Stage */}
                {progress?.message && (
                  <p className="text-xs text-gray-600 mb-3">{progress.message}</p>
                )}

                {/* Failure reason */}
                {isFailed && importProgress.error_details && (
                  <div className="mb-3 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
                    <strong>Причина:</strong><br />
                    {importProgress.error_details.error}
                  </div>
                )}

                {/* Stats on completion */}
                {isDone && importProgress.stats && (
                  <div className="mb-3 p-3 bg-green-50 border border-green-200 rounded text-sm">
                    <strong>Статистика:</strong>
                    <pre className="mt-1 text-xs whitespace-pre-wrap">{JSON.stringify(importProgress.stats, null, 2)}</pre>
                  </div>
                )}
              </div>

              {/* Console log panel */}
              <div className="mt-3 border border-gray-200 rounded-lg bg-white">
                <div className="flex items-center justify-between px-4 py-2 border-b border-gray-200 text-xs text-gray-500">
                  <span>Консоль імпорту</span>
                  <button
                    type="button"
                    onClick={() => setAutoScroll(!autoScroll)}
                    className={`text-xs underline ${autoScroll ? 'text-blue-600' : 'text-gray-400'}`}
                  >
                    {autoScroll ? 'Автопрокрутка: Увімкн.' : 'Автопрокрутка: Вимкн.'}
                  </button>
                </div>
                <div
                  ref={consoleRef}
                  className="overflow-y-auto max-h-80 p-3 font-mono text-xs leading-5"
                  onScroll={(e) => {
                    const el = e.currentTarget;
                    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
                    setAutoScroll(atBottom);
                  }}
                >
                  {logLines.length === 0 && importStarted && (
                    <p className="text-gray-400">Очікування логів...</p>
                  )}
                  {logLines.map((log) => (
                    <div key={log.id} className={`${LEVEL_COLORS[log.level] || 'text-gray-600'}`}>
                      <span className="text-gray-400">[{formatTime(log.created_at)}]</span>{' '}
                      <span className="font-medium">{LEVEL_BADGES[log.level] || log.level}</span>{' '}
                      <span>{log.message}</span>
                    </div>
                  ))}
                </div>
              </div>
            </section>
          )}

          {/* Recent imports */}
          <section>
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
              Останні імпорти
            </h3>
            {jobsLoading && !jobs.length ? (
              <LoadingState label="Завантаження імпортів..." />
            ) : jobs.length === 0 ? (
              <p className="text-xs text-gray-400">Імпортів для цього постачальника ще не було.</p>
            ) : (
              <Table head={<tr><Th>#</Th><Th>Тип</Th><Th>Статус</Th><Th>Створено</Th><Th>Завершено</Th></tr>}>
                {jobs.map((j) => {
                  const status = normStatus(j.status);
                  return (
                    <tr key={j.id} className="hover:bg-gray-50">
                      <Td className="font-mono text-xs">{j.id}</Td>
                      <Td className="text-sm">{TYPE_LABELS[j.import_type] || j.import_type}</Td>
                      <Td>
                        <Badge tone={importStatusTone(status)}>
                          {IMPORT_STATUS_LABELS[status] || j.status}
                        </Badge>
                      </Td>
                      <Td className="whitespace-nowrap text-xs text-gray-500">{formatDateTime(j.created_at)}</Td>
                      <Td className="whitespace-nowrap text-xs text-gray-500">{formatDateTime(j.finished_at)}</Td>
                    </tr>
                  );
                })}
              </Table>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
