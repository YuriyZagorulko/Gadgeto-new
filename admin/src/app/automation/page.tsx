'use client';

import { Fragment, useCallback, useEffect, useState } from 'react';
import { api, qs } from '@/lib/api';
import {
  PageHeader, Button, Table, Th, Td, Badge, Input, Modal,
  Pagination, ErrorState, EmptyState, useToast,
} from '@/components/ui';

/* Convenient presets only — the actual interval is stored in the backend
   DB settings (`catalog_sync_interval_hours`) and the scheduler reads it
   from there on every hourly tick. */
const INTERVAL_PRESETS = [1, 2, 4, 6, 8, 12, 24, 48, 72];
const MAX_INTERVAL_HOURS = 8760;

/* ── date helpers ───────────────────────────────────────────────────────────
   Backend timestamps come in TWO shapes: tz-aware UTC ISO strings from
   computed fields ("2026-09-02T04:00:00+00:00") and NAIVE strings from DB
   columns ("2026-09-02T04:00:00"), which are stored in the database session
   timezone (Europe/Kyiv) — the same convention the rest of the admin uses
   (`new Date(value)` → shown as wall-clock time).  Never blindly append
   'Z' to naive strings: that shifts them by the tz offset. */
function parseDbDate(value?: string | null): Date | null {
  if (!value) return null;
  const d = new Date(value);
  return isNaN(d.getTime()) ? null : d;
}

function fmtDateTime(d: Date | null): string {
  if (!d) return '—';
  const p = (n: number) => String(n).padStart(2, '0');
  return `${p(d.getDate())}.${p(d.getMonth() + 1)}.${d.getFullYear()} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

function fmtShortDateTime(value?: string | null): string {
  const d = parseDbDate(value);
  return d ? d.toLocaleString('uk-UA', {
    hour: '2-digit', minute: '2-digit', day: 'numeric', month: 'short',
  }) : '—';
}

/* ── Ukrainian pluralization for the interval label ── */
function hoursWord(h: number): string {
  const m10 = h % 10, m100 = h % 100;
  if (m10 === 1 && m100 !== 11) return 'година';
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return 'години';
  return 'годин';
}

function intervalLabel(h: number): string {
  return h === 1 ? 'Кожну годину' : `Кожні ${h} ${hoursWord(h)}`;
}

type AutomationStatus = {
  enabled: boolean;
  interval_hours: number;
  current_run: {
    id: number; status: string; trigger: string;
    started_at: string | null; finished_at: string | null;
    progress_json: string | null;
    suppliers: Array<{ code: string; name: string; status?: string; }>;
    exports: Array<{ channel: string; status?: string; run_id?: number; }>;
    logs: Array<{ level: string; message: string; created_at: string; }>;
  } | null;
  last_run: {
    id: number; status: string; trigger: string;
    started_at: string | null; finished_at: string | null;
    progress_json: string | null;
    suppliers: Array<{ code: string; name: string; status?: string; }>;
    exports: Array<{ channel: string; status?: string; run_id?: number; }>;
  } | null;
  next_run_at: string | null;
  lock: {
    locked: boolean | null;
    ttl?: number | null;
    run_id?: string | null;
    available?: boolean;   // false → Redis unreachable (separate UI state)
    error?: string | null;
  } | null;
};

type AutomationHistoryItem = {
  id: number; status: string; trigger: string;
  started_at: string | null; finished_at: string | null;
  suppliers: Array<{ code: string; name: string; status?: string; }>;
  exports: Array<{ channel: string; status?: string; run_id?: number; }>;
};

function AutomationPanel() {
  const toast = useToast();
  const [statusData, setStatusData] = useState<AutomationStatus | null>(null);
  const [error, setError] = useState('');
  const [toggling, setToggling] = useState(false);
  const [launchingSync, setLaunchingSync] = useState(false);
  const [historyItems, setHistoryItems] = useState<AutomationHistoryItem[]>([]);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [expandedRun, setExpandedRun] = useState<number | null>(null);
  // interval editor
  const [intervalModalOpen, setIntervalModalOpen] = useState(false);
  const [intervalDraft, setIntervalDraft] = useState(4);
  const [customMode, setCustomMode] = useState(false);
  const [customValue, setCustomValue] = useState('');
  const [savingInterval, setSavingInterval] = useState(false);

  const loadStatus = useCallback(async () => {
    try {
      const d = await api.get<AutomationStatus>('/automation/status');
      setStatusData(d);
      setError('');
    } catch (e: unknown) {
      setError((e as Error).message);
    }
  }, []);

  const loadHistory = useCallback(async () => {
    try {
      const d = await api.get<{ items: AutomationHistoryItem[]; total: number }>(
        '/automation/history' + qs({ page: historyPage, per_page: 10 })
      );
      setHistoryItems(d.items || []);
      setHistoryTotal(d.total || 0);
    } catch { /* ignore */ }
  }, [historyPage]);

  useEffect(() => { loadStatus(); }, [loadStatus]);
  useEffect(() => { loadHistory(); }, [loadHistory]);

  const hasActive = statusData?.current_run?.status === 'RUNNING';
  useEffect(() => {
    if (!hasActive) return;
    const t = setInterval(loadStatus, 5000);
    return () => clearInterval(t);
  }, [hasActive, loadStatus]);

  const toggleAutomation = async () => {
    setToggling(true);
    try {
      if (statusData?.enabled) {
        await api.post('/automation/disable');
        toast.push('success', 'Автоматизацію вимкнено');
      } else {
        await api.post('/automation/enable');
        toast.push('success', 'Автоматизацію увімкнено');
      }
      loadStatus();
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally {
      setToggling(false);
    }
  };

  const openIntervalModal = () => {
    const current = statusData?.interval_hours ?? 4;
    if (INTERVAL_PRESETS.includes(current)) {
      setCustomMode(false);
      setCustomValue('');
    } else {
      setCustomMode(true);
      setCustomValue(String(current));
    }
    setIntervalDraft(current);
    setIntervalModalOpen(true);
  };

  const parsedCustom = Number(customValue);
  const customInvalid = customMode && (
    customValue.trim() === '' || !Number.isInteger(parsedCustom)
    || parsedCustom < 1 || parsedCustom > MAX_INTERVAL_HOURS
  );

  const saveInterval = async () => {
    const value = customMode ? parsedCustom : intervalDraft;
    if (!Number.isInteger(value) || value < 1 || value > MAX_INTERVAL_HOURS) {
      toast.push('error', `Введіть додатне ціле число годин (1–${MAX_INTERVAL_HOURS})`);
      return;
    }
    setSavingInterval(true);
    try {
      await api.post('/automation/interval', { interval_hours: value });
      toast.push('success', intervalLabel(value) + ' — збережено');
      setIntervalModalOpen(false);
      loadStatus(); // refresh: status + recalculated next_run_at
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally {
      setSavingInterval(false);
    }
  };

  const startSync = async () => {
    setLaunchingSync(true);
    try {
      const res = await api.post<{ detail: string; run_id?: number }>('/automation/run');
      toast.push('success', res.detail || 'Синхронізацію запущено');
      loadStatus();
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally {
      setLaunchingSync(false);
    }
  };

  const statusLabel = statusData?.enabled ? 'Увімкнена' : 'Вимкнена';
  const statusColor = statusData?.enabled ? 'text-green-600' : 'text-gray-400';
  const intervalText = statusData?.interval_hours
    ? intervalLabel(statusData.interval_hours)
    : '—';

  // Next run comes tz-aware from the backend; parseDbDate keeps it safe.
  const nextRunStr = fmtDateTime(parseDbDate(statusData?.next_run_at));

  // Lock display: Redis unreachable is its OWN state — never shown as "Вільно".
  const lockDisplay = !statusData
    ? { label: '—', cls: 'text-gray-400' }
    : statusData.lock?.available === false
      ? { label: 'Redis недоступний', cls: 'text-red-600' }
      : statusData.lock?.locked
        ? { label: 'Зайнято', cls: 'text-amber-600' }
        : { label: 'Вільно', cls: 'text-green-600' };

  return (
    <div className="space-y-6">
      {/* ── Status card */}
      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <div className="flex items-start justify-between gap-4 flex-wrap mb-4">
          <div>
            <h3 className="font-semibold text-gray-900">Автоматизація</h3>
            <p className={`text-sm font-medium ${statusColor}`}>{statusLabel}</p>
          </div>
          <div className="flex gap-2 flex-wrap">
            {statusData?.enabled ? (
              <>
                <Button variant="secondary" size="sm" onClick={openIntervalModal}>
                  Редагувати
                </Button>
                <Button variant="primary" size="sm"
                  disabled={launchingSync || hasActive} onClick={startSync}>
                  {launchingSync ? 'Запуск...' : 'Запустити зараз'}
                </Button>
                <Button variant="secondary" size="sm"
                  disabled={toggling} onClick={toggleAutomation}>
                  Вимкнути
                </Button>
              </>
            ) : (
              <>
                <Button variant="secondary" size="sm" onClick={openIntervalModal}>
                  Налаштувати
                </Button>
                <Button variant="primary" size="sm"
                  disabled={toggling} onClick={toggleAutomation}>
                  Увімкнути
                </Button>
              </>
            )}
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
          <div>
            <span className="text-gray-500">Розклад:</span>
            <span className="ml-2 font-medium">{intervalText}</span>
          </div>
          {statusData?.enabled && (
            <div>
              <span className="text-gray-500">Наступний запуск:</span>
              <span className="ml-2 font-medium">{nextRunStr}</span>
            </div>
          )}
          <div>
            <span className="text-gray-500">Статус блокування:</span>
            <span className={`ml-2 font-medium ${lockDisplay.cls}`}>{lockDisplay.label}</span>
          </div>
        </div>
      </div>

      {/* ── Interval editor */}
      <Modal open={intervalModalOpen} title="Налаштування автоматизації"
        onClose={() => setIntervalModalOpen(false)}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Інтервал:
            </label>
            <div className="grid grid-cols-3 gap-2">
              {INTERVAL_PRESETS.map((h) => (
                <button key={h} type="button"
                  onClick={() => { setCustomMode(false); setIntervalDraft(h); }}
                  className={`border rounded-md px-3 py-2 text-sm transition-colors ${
                    !customMode && intervalDraft === h
                      ? 'border-blue-600 bg-blue-50 text-blue-700 font-medium'
                      : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                  }`}>
                  {intervalLabel(h)}
                </button>
              ))}
              <button type="button"
                onClick={() => {
                  setCustomMode(true);
                  if (!INTERVAL_PRESETS.includes(intervalDraft)) {
                    setCustomValue(String(intervalDraft));
                  }
                }}
                className={`border rounded-md px-3 py-2 text-sm transition-colors ${
                  customMode
                    ? 'border-blue-600 bg-blue-50 text-blue-700 font-medium'
                    : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                }`}>
                Інше значення
              </button>
            </div>
          </div>
          {customMode && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Кількість годин
              </label>
              <Input
                type="number" min={1} step={1}
                value={customValue}
                placeholder="Наприклад: 5"
                onChange={(e) => setCustomValue(e.target.value)}
              />
              {customInvalid && (
                <p className="text-xs text-red-600 mt-1">
                  Введіть додатне ціле число годин (1–{MAX_INTERVAL_HOURS})
                </p>
              )}
            </div>
          )}
          <p className="text-xs text-gray-500">
            Мінімальний інтервал між запусками синхронізації. Наступний запуск
            буде перераховано після збереження.
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" size="sm"
              onClick={() => setIntervalModalOpen(false)}>
              Скасувати
            </Button>
            <Button variant="primary" size="sm" loading={savingInterval}
              disabled={customInvalid} onClick={saveInterval}>
              Зберегти
            </Button>
          </div>
        </div>
      </Modal>

      {/* ── Current run */}
      {statusData?.current_run && (
        <div className="bg-white border border-amber-200 rounded-lg p-5">
          <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <span className="inline-block w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
            Синхронізація виконується
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-3">
            {statusData.current_run.suppliers?.map((s) => (
              <div key={s.code} className="flex items-center gap-2 text-sm">
                <span className={
                  s.status === 'SUCCEEDED' || s.status === 'COMPLETED' ? 'text-green-600' :
                  s.status === 'FAILED' ? 'text-red-600' :
                  ['RUNNING', 'QUEUED'].includes(s.status || '') ? 'text-amber-600' : 'text-gray-400'
                }>{s.status === 'SUCCEEDED' || s.status === 'COMPLETED' ? '\u2713' :
                   s.status === 'FAILED' ? '\u2717' :
                   ['RUNNING', 'QUEUED'].includes(s.status || '') ? '\u27F3' : '\u22EF'}</span>
                <span>{s.name || s.code}</span>
                {s.status && <span className="text-xs text-gray-400">({s.status})</span>}
              </div>
            ))}
            {statusData.current_run.exports?.map((e) => (
              <div key={e.channel} className="flex items-center gap-2 text-sm">
                <span className={
                  e.status === 'SUCCEEDED' || e.status === 'COMPLETED' ? 'text-green-600' :
                  e.status === 'FAILED' ? 'text-red-600' :
                  ['RUNNING', 'QUEUED'].includes(e.status || '') ? 'text-amber-600' : 'text-gray-400'
                }>{e.status === 'SUCCEEDED' || e.status === 'COMPLETED' ? '\u2713' :
                   e.status === 'FAILED' ? '\u2717' : '\u27F3'}</span>
                <span>{e.channel}</span>
                {e.status && <span className="text-xs text-gray-400">({e.status})</span>}
              </div>
            ))}
          </div>
          {statusData.current_run.logs && statusData.current_run.logs.length > 0 && (
            <div className="bg-gray-50 rounded p-3 max-h-40 overflow-y-auto">
              {statusData.current_run.logs.slice().reverse().map((log, i) => (
                <div key={i} className="text-xs font-mono leading-5">
                  <span className={log.level === 'ERROR' ? 'text-red-600' : log.level === 'WARNING' ? 'text-amber-600' : 'text-gray-500'}>
                    [{log.level}]
                  </span>
                  {' '}{log.message}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Last run result */}
      {statusData?.last_run && !hasActive && (
        <div className="bg-white border border-gray-200 rounded-lg p-5">
          <h3 className="font-semibold text-gray-900 mb-2">Останній запуск</h3>
          <div className="flex items-center gap-3 text-sm mb-2">
            <Badge tone={statusData.last_run.status === 'SUCCEEDED' ? 'green' : statusData.last_run.status === 'PARTIAL' ? 'yellow' : statusData.last_run.status === 'FAILED' ? 'red' : 'gray'}>
              {statusData.last_run.status === 'SUCCEEDED' ? 'Успіх' :
               statusData.last_run.status === 'PARTIAL' ? 'Частково' :
               statusData.last_run.status === 'FAILED' ? 'Помилка' :
               statusData.last_run.status === 'SKIPPED' ? 'Пропущено' : statusData.last_run.status}
            </Badge>
            <span className="text-gray-500">
              {fmtShortDateTime(statusData.last_run.started_at)}
            </span>
          </div>
        </div>
      )}

      {error && <ErrorState message={error} onRetry={loadStatus} />}

      {/* ── History */}
      <div>
        <h3 className="font-medium text-gray-800 mb-3">Історія синхронізацій</h3>
        {historyItems.length === 0 ? (
          <EmptyState title="Історії не знайдено" hint="Після запуску автоматичної синхронізації результати з'являться тут." />
        ) : (
          <Table head={<tr><Th>Дата</Th><Th>Статус</Th><Th>Тригер</Th><Th>Постачальники</Th><Th>Експорт</Th><Th></Th></tr>}>
            {historyItems.map((r) => (
              <Fragment key={r.id}>
                <tr className="hover:bg-gray-50 cursor-pointer" onClick={() => setExpandedRun(expandedRun === r.id ? null : r.id)}>
                  <Td className="whitespace-nowrap text-xs text-gray-500">
                    {fmtShortDateTime(r.started_at)}
                  </Td>
                  <Td>
                    <Badge tone={r.status === 'SUCCEEDED' ? 'green' : r.status === 'PARTIAL' ? 'yellow' : r.status === 'FAILED' ? 'red' : 'gray'}>
                      {r.status === 'SUCCEEDED' ? 'Успіх' : r.status === 'PARTIAL' ? 'Частково' : r.status === 'FAILED' ? 'Помилка' : r.status === 'SKIPPED' ? 'Пропущено' : r.status}
                    </Badge>
                  </Td>
                  <Td className="text-xs text-gray-500">
                    {r.trigger === 'scheduler' ? 'Розклад' : r.trigger === 'manual' ? 'Ручний' : r.trigger}
                  </Td>
                  <Td className="text-xs">{r.suppliers?.length || 0} / {r.suppliers?.filter((s) => s.status === 'SUCCEEDED' || s.status === 'COMPLETED').length || 0} успішно</Td>
                  <Td className="text-xs">{r.exports?.filter((e) => e.status === 'SUCCEEDED').length || 0} / {r.exports?.length || 0}</Td>
                  <Td><Button size="sm" variant="ghost">{expandedRun === r.id ? 'Сховати' : 'Деталі'}</Button></Td>
                </tr>
                {expandedRun === r.id && (
                  <tr className="bg-gray-50/60">
                    <td colSpan={6} className="px-6 py-3">
                      <div className="text-xs space-y-2">
                        <div className="font-medium text-gray-500">Постачальники:</div>
                        {r.suppliers?.length ? r.suppliers.map((s) => (
                          <div key={s.code} className="flex gap-3 pl-4">
                            <span className={s.status === 'SUCCEEDED' || s.status === 'COMPLETED' ? 'text-green-600' : s.status === 'FAILED' ? 'text-red-600' : 'text-gray-400'}>
                              {s.status === 'SUCCEEDED' || s.status === 'COMPLETED' ? '\u2713' : s.status === 'FAILED' ? '\u2717' : '\u22EF'}
                            </span>
                            <span>{s.name || s.code}</span>
                            {s.status && <span className="text-gray-400">({s.status})</span>}
                          </div>
                        )) : <div className="pl-4 text-gray-400">Немає даних</div>}
                        <div className="font-medium text-gray-500 mt-2">Експорт:</div>
                        {r.exports?.length ? r.exports.map((e) => (
                          <div key={e.channel} className="flex gap-3 pl-4">
                            <span className={e.status === 'SUCCEEDED' ? 'text-green-600' : e.status === 'PARTIAL' ? 'text-amber-600' : e.status === 'FAILED' ? 'text-red-600' : 'text-gray-400'}>
                              {e.status === 'SUCCEEDED' ? '\u2713' : e.status === 'FAILED' ? '\u2717' : '\u22EF'}
                            </span>
                            <span>{e.channel}</span>
                            {e.run_id && <span className="text-gray-400">(run #{e.run_id})</span>}
                          </div>
                        )) : <div className="pl-4 text-gray-400">\u2014</div>}
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </Table>
        )}
        <div className="mt-3 flex justify-center">
          <Pagination page={historyPage} pages={Math.ceil(historyTotal / 10)} total={historyTotal} onPage={setHistoryPage} />
        </div>
      </div>
    </div>
  );
}

export default function AutomationPage() {
  return (
    <div>
      <PageHeader title="Автоматизація" />
      <AutomationPanel />
    </div>
  );
}
