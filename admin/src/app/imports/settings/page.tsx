'use client';

import { Fragment, useCallback, useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { api, qs } from '@/lib/api';
import { formatDateTime, IMPORT_STATUS_LABELS, importStatusTone } from '@/lib/format';
import {
  PageHeader, Button, Select, Table, Th, Td, Badge,
  Pagination, LoadingState, ErrorState, EmptyState, ConfirmDialog, useToast,
} from '@/components/ui';
import PricingTab from '@/components/PricingTab';

type Job = {
  id: number; supplier_id: number; supplier_name: string | null;
  import_type: string; status: string;
  started_at: string | null; finished_at: string | null; created_at: string;
  stats?: Record<string, unknown> | null;
  error_details?: Record<string, unknown> | string | null;
};
type Sup = { id: number; code: string; name: string; config: Record<string, string> };
type RunAllResponse = { ok: boolean; jobs: number; suppliers: string[]; detail: string };

const TYPE_LABELS: Record<string, string> = { full: 'Повний', prices: 'Ціни', stocks: 'Залишки' };
const normalizeStatus = (s: string) => (s || '').toLowerCase();

export default function ImportSettingsPage() {
  const sp = useSearchParams();
  const router = useRouter();
  const tab = sp.get('tab') || 'settings';

  const setTab = (t: string) => {
    router.replace('/imports/settings' + (t === 'settings' ? '' : '?tab=' + t));
  };

  return (
    <div>
      <PageHeader title="Налаштування імпорту" />
      <div className="border-b border-gray-200 mb-4">
        <div className="flex gap-6 -mb-px">
          <button onClick={() => setTab('settings')}
            className={'pb-2 text-sm font-medium border-b-2 transition-colors ' + (tab === 'settings' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700')}>
            Налаштування
          </button>
          <button onClick={() => setTab('pricing')}
            className={'pb-2 text-sm font-medium border-b-2 transition-colors ' + (tab === 'pricing' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700')}>
            Ціноутворення
          </button>
          <button onClick={() => setTab('global')}
            className={'pb-2 text-sm font-medium border-b-2 transition-colors ' + (tab === 'global' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700')}>
            Глобальні дії
          </button>
        </div>
      </div>
      {tab === 'settings' && <SettingsTab />}
      {tab === 'pricing' && <PricingTab />}
      {tab === 'global' && <GlobalActionsTab />}
    </div>
  );
}

/* =====================================================================
   TAB 1: Settings — per-supplier config
   ===================================================================== */
function SettingsTab() {
  const toast = useToast();
  const [suppliers, setSuppliers] = useState<Sup[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<number | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    setLoading(true);
    api.get<{ items: Sup[] }>('/suppliers' + qs({ per_page: 100 }))
      .then((d) => setSuppliers(d.items || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [tick]);

  const updateConfig = async (sid: number, config: Record<string, string>) => {
    setSaving(sid);
    try {
      await api.put('/suppliers/' + sid + '/config', { config });
      toast.push('success', 'Налаштування збережено');
      setTick((x) => x + 1);
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally {
      setSaving(null);
    }
  };

  if (loading) return <LoadingState label="Завантаження налаштувань..." />;

  return (
    <div className="space-y-4">
      <p className="text-xs text-gray-400 mb-4">
        Налаштування стосуються лише імпортованих товарів. Ручна завантаження зображень через редактор товару завжди використовує локальне сховище.
      </p>
      {suppliers.length === 0 ? (
        <EmptyState title="Постачальників не знайдено" />
      ) : (
        suppliers.map((s) => {
          const mode = s.config?.image_storage_mode || 'supplier_url';
          return (
            <div key={s.id} className="bg-white border border-gray-200 rounded-lg p-5">
              <h3 className="font-semibold text-gray-900 mb-3">{s.name} ({s.code})</h3>
              <div className="max-w-md">
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Зберігання зображень</label>
                <div className="flex gap-4">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name={'image_storage_' + s.id}
                      value="supplier_url"
                      checked={mode === 'supplier_url'}
                      onChange={() => updateConfig(s.id, { ...s.config, image_storage_mode: 'supplier_url' })}
                      className="accent-blue-600"
                    />
                    <span className="text-sm">Зображення постачальника</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name={'image_storage_' + s.id}
                      value="local"
                      checked={mode === 'local'}
                      onChange={() => updateConfig(s.id, { ...s.config, image_storage_mode: 'local' })}
                      className="accent-blue-600"
                    />
                    <span className="text-sm">Зберігати локально</span>
                  </label>
                </div>
                <p className="text-xs text-gray-400 mt-1.5">
                  {mode === 'supplier_url'
                    ? 'Зображення будуть зберігатися як зовнішні URL-адреси постачальника.'
                    : 'Зображення будуть завантажені та збережені локально в медіа-бібліотеці.'}
                </p>
              </div>
              {saving === s.id && <span className="text-xs text-blue-600 mt-2 block">Збереження...</span>}
            </div>
          );
        })
      )}
    </div>
  );
}

/* =====================================================================
   TAB 2: Global Actions
   ===================================================================== */
function GlobalActionsTab() {
  const toast = useToast();
  const [confirming, setConfirming] = useState<null | 'import' | 'update'>(null);
  const [launching, setLaunching] = useState<null | 'import' | 'update'>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expandedJob, setExpandedJob] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const PER_PAGE = 10;

  const loadJobs = useCallback(async () => {
    try {
      const d = await api.get<{ items: Job[]; total: number; page: number; per_page: number }>('/imports/jobs' + qs({ page, per_page: PER_PAGE }));
      setJobs(d.items || []);
      setError('');
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => { loadJobs(); }, [loadJobs]);

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

  const pages = 1; // placeholder; backend returns total but we simplify

  return (
    <div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div className="bg-white border border-gray-200 rounded-lg p-5 flex flex-col gap-3">
          <h3 className="font-semibold text-gray-900">Імпортувати всі товари</h3>
          <p className="text-sm text-gray-500 flex-1">Імпортувати товари від усіх активних постачальників. Завдання виконуються послідовно у фоні.</p>
          <div>
            <Button
              variant="primary"
              disabled={hasActive}
              onClick={() => setConfirming('import')}
            >
              {hasActive ? 'Виконується імпорт...' : 'Імпортувати всі товари'}
            </Button>
          </div>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-5 flex flex-col gap-3">
          <h3 className="font-semibold text-gray-900">Оновити всі товари</h3>
          <p className="text-sm text-gray-500 flex-1">Оновити ціни та залишки для всіх активних постачальників.</p>
          <div>
            <Button
              variant="secondary"
              disabled={hasActive}
              onClick={() => setConfirming('update')}
            >
              {hasActive ? 'Виконується імпорт...' : 'Оновити всі товари'}
            </Button>
          </div>
        </div>
      </div>

      {error && <ErrorState message={error} onRetry={loadJobs} />}

      <h3 className="font-medium text-gray-800 mb-3">Останні глобальні операції</h3>
      {loading ? (
        <LoadingState label="Завантаження..." />
      ) : jobs.length === 0 ? (
        <EmptyState title="Імпортів не знайдено" hint="Після запуску глобального імпорту результати з'являться тут." />
      ) : (
        <Table head={<tr><Th>ID</Th><Th>Постачальник</Th><Th>Тип</Th><Th>Статус</Th><Th>Створено</Th><Th>Завершено</Th><Th></Th></tr>}>
          {jobs.map((j) => {
            const status = normalizeStatus(j.status);
            return (
              <Fragment key={j.id}>
                <tr className="hover:bg-gray-50">
                  <Td className="font-mono text-xs">{j.id}</Td>
                  <Td className="text-sm">{j.supplier_name || '—'}</Td>
                  <Td className="text-sm">{TYPE_LABELS[j.import_type] || j.import_type}</Td>
                  <Td><Badge tone={importStatusTone(status)}>{IMPORT_STATUS_LABELS[status] || j.status}</Badge></Td>
                  <Td className="whitespace-nowrap text-xs text-gray-500">{formatDateTime(j.created_at)}</Td>
                  <Td className="whitespace-nowrap text-xs text-gray-500">{formatDateTime(j.finished_at)}</Td>
                  <Td>
                    <Button size="sm" variant="ghost" onClick={() => setExpandedJob(expandedJob === j.id ? null : j.id)}>
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
                            {typeof j.error_details === 'string' ? j.error_details : JSON.stringify(j.error_details, null, 2)}
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

      <ConfirmDialog open={confirming === 'import'} title="Імпортувати всі товари?"
        message="Запустити повний імпорт товарів для ВСІХ активних постачальників? Це може тривати довго."
        confirmLabel="Запустити імпорт" busy={launching === 'import'} onConfirm={launch}
        onCancel={() => setConfirming(null)} />
      <ConfirmDialog open={confirming === 'update'} title="Оновити всі товари?"
        message="Запустити оновлення товарів (ціни та залишки) для ВСІХ активних постачальників?"
        confirmLabel="Запустити оновлення" busy={launching === 'update'} onConfirm={launch}
        onCancel={() => setConfirming(null)} />
    </div>
  );
}
