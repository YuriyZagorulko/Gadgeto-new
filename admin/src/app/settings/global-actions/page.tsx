'use client';

import { Fragment, useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { formatDateTime, IMPORT_STATUS_LABELS, importStatusTone } from '@/lib/format';
import {
  PageHeader,
  Button,
  Badge,
  Table,
  Th,
  Td,
  LoadingState,
  ErrorState,
  EmptyState,
  ConfirmDialog,
  useToast,
} from '@/components/ui';

type Job = {
  id: number;
  supplier_id: number;
  supplier_name: string | null;
  import_type: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  stats?: Record<string, unknown> | null;
  error_details?: unknown;
};

type RunAllResponse = { ok: boolean; jobs: number; suppliers: string[]; detail: string };

const TYPE_LABELS: Record<string, string> = { full: 'Повний імпорт', prices: 'Ціни', stock: 'Залишки' };

const normalizeStatus = (status: string): string => (status || '').toLowerCase();

/**
 * Налаштування → Глобальні дії.
 * Масові дії імпорту для ВСІХ постачальників через реальний бекенд
 * (`POST /imports/run-all` → існуючий run_import).
 */
export default function GlobalActionsPage() {
  const toast = useToast();
  const [confirming, setConfirming] = useState<null | 'import' | 'update'>(null);
  const [launching, setLaunching] = useState<null | 'import' | 'update'>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expandedJob, setExpandedJob] = useState<number | null>(null);

  const loadJobs = useCallback(async () => {
    try {
      const d = await api.get<{ items: Job[] }>('/imports/jobs?per_page=12');
      setJobs(d.items || []);
      setError('');
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadJobs();
  }, [loadJobs]);

  // Auto-refresh while any job is queued/running (statuses are stored uppercase).
  const hasActive = jobs.some((j) => ['queued', 'running'].includes(normalizeStatus(j.status)));
  useEffect(() => {
    if (!hasActive) return;
    const t = setInterval(loadJobs, 4000);
    return () => clearInterval(t);
  }, [hasActive, loadJobs]);

  const launch = async () => {
    if (!confirming) return;
    setLaunching(confirming);
    try {
      const res = await api.post<RunAllResponse>('/imports/run-all', { action: confirming });
      toast.push('success', res.detail || 'Глобальне завдання запущено');
      setConfirming(null);
      loadJobs();
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally {
      setLaunching(null);
    }
  };

  return (
    <div>
      <PageHeader title="Глобальні дії" />
      <p className="text-xs text-gray-400 mb-4">
        Масові дії, що впливають на всіх постачальників одночасно. Завдання виконуються послідовно у фоні —
        прогрес і статистика з&apos;являться в таблиці нижче та оновлюватимуться автоматично.
      </p>

      {/* Action cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        <div className="bg-white border border-gray-200 rounded-lg p-5 flex flex-col gap-3">
          <h3 className="font-semibold text-gray-900">Імпортувати всі товари</h3>
          <p className="text-sm text-gray-500 flex-1">
            Імпортувати товари від усіх постачальників
          </p>
          <div>
            <Button
              loading={launching === 'import'}
              disabled={launching !== null}
              onClick={() => setConfirming('import')}
            >
              Імпортувати всі товари
            </Button>
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-5 flex flex-col gap-3">
          <h3 className="font-semibold text-gray-900">Оновити всі товари</h3>
          <p className="text-sm text-gray-500 flex-1">
            Оновити товари від усіх постачальників
          </p>
          <div>
            <Button
              variant="secondary"
              loading={launching === 'update'}
              disabled={launching !== null}
              onClick={() => setConfirming('update')}
            >
              Оновити всі товари
            </Button>
          </div>
        </div>
      </div>

      {/* Running banner */}
      {hasActive && (
        <div
          className="mb-4 rounded-md bg-blue-50 border border-blue-200 text-blue-800 text-sm px-4 py-3"
          role="status"
        >
          Виконуються завдання імпорту… Дані в таблиці оновлюються автоматично кожні 4 секунди.
        </div>
      )}

      {/* Recent jobs */}
      <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
        Останні завдання імпорту
      </h3>
      {error && <ErrorState message={error} onRetry={loadJobs} />}
      {!error && loading && <LoadingState label="Завантаження завдань..." />}
      {!error && !loading && jobs.length === 0 && (
        <EmptyState
          title="Завдань ще немає"
          hint="Історія з'явиться після запуску глобальних дій або імпорту окремого постачальника."
        />
      )}
      {!error && jobs.length > 0 && (
        <Table
          head={
            <tr>
              <Th>#</Th><Th>Постачальник</Th><Th>Тип</Th><Th>Статус</Th>
              <Th>Створено</Th><Th>Завершено</Th><Th className="w-28"></Th>
            </tr>
          }
        >
          {jobs.map((j) => {
            const status = normalizeStatus(j.status);
            return (
              <Fragment key={j.id}>
                <tr className="hover:bg-gray-50">
                  <Td className="font-mono text-xs">{j.id}</Td>
                  <Td className="text-sm">{j.supplier_name || '—'}</Td>
                  <Td className="text-sm">{TYPE_LABELS[j.import_type] || j.import_type}</Td>
                  <Td>
                    <Badge tone={importStatusTone(status)}>
                      {IMPORT_STATUS_LABELS[status] || j.status}
                    </Badge>
                  </Td>
                  <Td className="whitespace-nowrap text-xs text-gray-500">{formatDateTime(j.created_at)}</Td>
                  <Td className="whitespace-nowrap text-xs text-gray-500">{formatDateTime(j.finished_at)}</Td>
                  <Td>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setExpandedJob(expandedJob === j.id ? null : j.id)}
                    >
                      {expandedJob === j.id ? 'Сховати' : 'Деталі'}
                    </Button>
                  </Td>
                </tr>
                {expandedJob === j.id && (
                  <tr className="bg-gray-50/60">
                    <td colSpan={7} className="px-6 py-3">
                      {j.error_details ? (
                        <div className="mb-2">
                          <span className="text-red-600 font-medium text-xs">Помилки:</span>
                          <pre className="bg-red-50 border border-red-100 rounded p-2 text-xs overflow-x-auto max-h-40 whitespace-pre-wrap mt-1">
                            {typeof j.error_details === 'string'
                              ? j.error_details
                              : JSON.stringify(j.error_details, null, 2)}
                          </pre>
                        </div>
                      ) : null}
                      {j.stats && Object.keys(j.stats).length > 0 ? (
                        <div>
                          <span className="text-gray-500 font-medium text-xs">Статистика:</span>
                          <pre className="bg-white border border-gray-100 rounded p-2 text-xs overflow-x-auto max-h-40 mt-1">
                            {JSON.stringify(j.stats, null, 2)}
                          </pre>
                        </div>
                      ) : (
                        !j.error_details && <span className="text-xs text-gray-400">Деталів немає.</span>
                      )}
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </Table>
      )}

      <ConfirmDialog
        open={confirming === 'import'}
        title="Імпортувати всі товари?"
        message="Запустити повний імпорт товарів для ВСІХ активних постачальників? Це може тривати довго. Поки тривають завдання, запуск нових глобальних дій буде заблоковано."
        confirmLabel="Запустити імпорт"
        busy={launching === 'import'}
        onConfirm={launch}
        onCancel={() => setConfirming(null)}
      />
      <ConfirmDialog
        open={confirming === 'update'}
        title="Оновити всі товари?"
        message="Запустити оновлення товарів (ціни та залишки) для ВСІХ активних постачальників? Поки тривають завдання, запуск нових глобальних дій буде заблоковано."
        confirmLabel="Запустити оновлення"
        busy={launching === 'update'}
        onConfirm={launch}
        onCancel={() => setConfirming(null)}
      />
    </div>
  );
}

