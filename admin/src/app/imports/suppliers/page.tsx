'use client';

import { useCallback, useEffect, useState } from 'react';
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

/** Постачальники визначені наперед і не можуть бути створені або видалені. */
const FIXED_SUPPLIERS = [
  { code: 'itlink', name: 'IT-Link' },
  { code: 'dclink', name: 'DC-Link' },
] as const;

const TYPE_LABELS: Record<string, string> = { full: 'Повний', prices: 'Ціни', stock: 'Залишки' };

const normStatus = (s: string): string => (s || '').toLowerCase();

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

  // Recent imports for the active supplier.
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

  // Auto-refresh while a job is queued/running.
  const hasActiveJob = jobs.some((j) => ['queued', 'running'].includes(normStatus(j.status)));
  useEffect(() => {
    if (!hasActiveJob) return;
    const t = setInterval(() => setJobsTick((x) => x + 1), 4000);
    return () => clearInterval(t);
  }, [hasActiveJob]);

  /** Запуск реального імпорту постачальника через існуючий бекенд. */
  const runImport = async (importType: string) => {
    if (!active) return;
    setRunningAction(importType);
    try {
      const res = await api.post<{ detail: string }>('/imports/run', {
        supplier_code: active.code,
        import_type: importType,
      });
      toast.push('success', res.detail || 'Імпорт запущено');
      setTimeout(() => setJobsTick((x) => x + 1), 1500);
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally {
      setRunningAction(null);
    }
  };

  return (
    <div>
      <PageHeader title="Постачальники" />
      <p className="text-xs text-gray-400 mb-4">
        Постачальники — фіксовані системні інтеграції, визначені в коді застосунку. Створення, редагування та
        видалення не передбачені. Кожен постачальник має власне джерело цін (прайс/фід), конфігурацію імпорту,
        маппінг та окремий процес імпорту.
      </p>

      {/* Fixed supplier tabs */}
      <div className="flex gap-1 mb-4 border-b border-gray-200">
        {FIXED_SUPPLIERS.map((s) => (
          <button
            key={s.code}
            onClick={() => setActiveCode(s.code)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition ${
              activeCode === s.code
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-800'
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
          {/* Info */}
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

          {/* Import actions (real backend) */}
          <section>
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">Імпорт</h3>
            <div className="bg-white border border-gray-200 rounded-lg p-4 flex flex-wrap gap-2 items-center">
              <Button
                loading={runningAction === 'full'}
                disabled={runningAction !== null || !active.enabled}
                onClick={() => runImport('full')}
              >
                Імпортувати товари
              </Button>
              <Button
                variant="secondary"
                loading={runningAction === 'prices'}
                disabled={runningAction !== null || !active.enabled}
                onClick={() => runImport('prices')}
              >
                Оновити ціни
              </Button>
              <Button
                variant="secondary"
                loading={runningAction === 'stock'}
                disabled={runningAction !== null || !active.enabled}
                onClick={() => runImport('stock')}
              >
                Оновити залишки
              </Button>
              {!active.enabled && (
                <span className="text-xs text-yellow-700 bg-yellow-50 border border-yellow-100 rounded px-2 py-1">
                  Постачальника вимкнено — імпорт недоступний.
                </span>
              )}
            </div>
          </section>

          {/* Recent imports */}
          <section>
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
              Останні імпорти {hasActiveJob && <span className="normal-case font-normal text-blue-600">— виконується…</span>}
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

          {/* Price source & import configuration (read-only, defined in code) */}
          <section>
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
              Джерело цін та конфігурація імпорту
            </h3>
            <pre className="bg-white border border-gray-200 rounded-lg p-4 text-xs overflow-x-auto max-h-72">
              {active.config ? JSON.stringify(active.config, null, 2) : 'Конфігурацію не задано.'}
            </pre>
            <p className="text-xs text-gray-400 mt-1">
              Джерело прайсу/фіду та параметри імпорту визначаються розробником у коді
              (системний реєстр постачальників). Маппінг налаштовується в розділі «Імпорт → Маппінг».
            </p>
          </section>
        </div>
      )}
    </div>
  );
}



