'use client';

import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { api } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import {
  PageHeader, Badge, LoadingState, ErrorState,
} from '@/components/ui';

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

type RunReport = {
  run_id: number;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  categories: { processed: number; total: number; created: number; updated: number };
  attributes: { categories_processed: number; categories_total: number; total: number; created: number; updated: number };
  values: { total: number; created: number; updated: number };
  errors: number;
  current_operation: string | null;
  logs: { level: string; message: string; ts?: string }[];
};

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

const badgeTone: Record<string, 'gray' | 'green' | 'blue' | 'yellow' | 'red'> = {
  succeeded: 'green', running: 'blue', queued: 'gray',
  failed: 'red', partial: 'yellow',
};

const statusLabels: Record<string, string> = {
  succeeded: 'Успішно', running: 'Виконується', queued: 'У черзі',
  failed: 'Помилка', partial: 'Частково',
};

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

function StatCard({ label, value, tone = 'gray' }: { label: string; value: string | number; tone?: string }) {
  const colors: Record<string, string> = {
    gray: 'bg-gray-50 text-gray-700 border-gray-200',
    green: 'bg-green-50 text-green-700 border-green-200',
    red: 'bg-red-50 text-red-700 border-red-200',
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
    yellow: 'bg-yellow-50 text-yellow-800 border-yellow-200',
  };
  return (
    <div className={`rounded-lg border p-4 ${colors[tone] || colors.gray}`}>
      <div className="text-2xl font-bold">{typeof value === 'number' ? value.toLocaleString('uk-UA') : value}</div>
      <div className="text-sm mt-1 opacity-80">{label}</div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Main page                                                           */
/* ------------------------------------------------------------------ */

export default function TaxonomyRunReportPage() {
  const params = useParams<{ runId: string }>();
  const runId = Number(params.runId);
  const [report, setReport] = useState<RunReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [isRunning, setIsRunning] = useState(false);

  const load = useCallback(async () => {
    try {
      const d = await api.get<RunReport>(`/export/channels/rozetka/taxonomy/runs/${runId}`);
      if (d && d.status) d.status = d.status.toLowerCase();
      setReport(d);
      setIsRunning(d.status === 'running' || d.status === 'queued');
    } catch (e: any) {
      setError(e.message || 'Не вдалось завантажити звіт');
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => { load(); }, [load]);

  // Poll while running — never navigates, only updates React state
  useEffect(() => {
    if (!isRunning) return;
    const interval = setInterval(() => load(), 3000);
    return () => clearInterval(interval);
  }, [isRunning, load]);

  if (loading) return <LoadingState label="Завантаження звіту..." />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!report) return <ErrorState message="Звіт не знайдено" />;

  const r = report;
  const st = r.status ? (statusLabels[r.status] || r.status) : '—';
  const stTone = (badgeTone[r.status] || 'gray') as 'green' | 'blue' | 'gray' | 'yellow' | 'red';

  return (
    <div>
      <PageHeader
        title={`Оновлення таксономії Rozetka #${r.run_id}`}
        actions={
          <Link href="/export/rozetka/taxonomy" className="text-sm text-blue-600 hover:underline">
            ← До таксономії
          </Link>
        }
      />

      {/* Status header */}
      <div className="bg-white border border-gray-200 rounded-lg p-5 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <Badge tone={stTone}>{st}</Badge>
          {isRunning && <span className="inline-block w-2 h-2 bg-blue-500 rounded-full animate-pulse" />}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div><span className="text-gray-500">Початок:</span> {r.started_at ? formatDateTime(r.started_at) : '—'}</div>
          <div><span className="text-gray-500">Завершення:</span> {r.finished_at ? formatDateTime(r.finished_at) : isRunning ? 'триває...' : '—'}</div>
          <div><span className="text-gray-500">Тривалість:</span> {fmtDuration(r.duration_seconds)}</div>
          <div><span className="text-gray-500">Помилок:</span> <span className={r.errors > 0 ? 'text-red-600 font-medium' : ''}>{r.errors}</span></div>
        </div>
        {r.current_operation && (
          <div className="mt-2 text-sm text-gray-600">Остання операція: {r.current_operation}</div>
        )}
      </div>

      {/* Summary cards */}
      <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-3">Підсумок</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard label="Всього категорій Rozetka" value={r.attributes.categories_total} tone="blue" />
        <StatCard label="Оброблено категорій" value={r.attributes.categories_processed} tone="green" />
        <StatCard label="Категорій без атрибутів" value={r.attributes.categories_total - r.attributes.categories_processed} tone="yellow" />
        <StatCard label="Помилок" value={r.errors} tone={r.errors > 0 ? 'red' : 'green'} />
      </div>

      {/* Attribute and value cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
        <StatCard label="Атрибутів всього" value={r.attributes.total} tone="blue" />
        <StatCard label="Атрибутів створено" value={r.attributes.created} tone="green" />
        <StatCard label="Атрибутів оновлено" value={r.attributes.updated} tone="yellow" />
        <StatCard label="Значень атрибутів" value={r.values.total} tone="blue" />
        <StatCard label="Значень створено" value={r.values.created} tone="green" />
        <StatCard label="Значень оновлено" value={r.values.updated} tone="yellow" />
      </div>

      {/* Note about category counters */}
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 mb-6 text-xs text-gray-500">
        <strong>Примітка:</strong> Показник «Оброблено категорій» відображає кількість категорій, для яких
        було завантажено атрибути. «Всього категорій Rozetka» — загальна кількість категорій у таксономії.
        Якщо ці числа не збігаються, деякі категорії не мають визначених атрибутів у API Rozetka.
      </div>

      {/* Errors section */}
      {r.errors > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
          <h3 className="font-medium text-red-800 mb-2">Помилки: {r.errors}</h3>
          <p className="text-sm text-red-700">
            Детальна інформація про помилки доступна в журналі нижче.
            Кожна помилка відповідає одній категорії, обробка якої завершилась невдало.
          </p>
          <p className="text-xs text-red-500 mt-1">
            Причина помилок: у попередній версії імпортера виникали конфлікти при масовому вставленні
            значень атрибутів. Це виправлено в поточній версії.
          </p>
        </div>
      )}

      {/* Logs section */}
      <div className="bg-white border border-gray-200 rounded-lg p-4 mb-6">
        <h3 className="font-medium text-gray-900 mb-3">Журнал ({r.logs.length})</h3>
        {r.logs.length === 0 ? (
          <p className="text-gray-400 italic text-sm">Журнал порожній</p>
        ) : (
          <div className="max-h-96 overflow-y-auto text-xs font-mono space-y-0.5 bg-gray-50 rounded p-3 border border-gray-100">
            {r.logs.map((l, i) => (
              <div key={i} className="flex gap-2">
                <span className="text-gray-400 w-12 shrink-0">{l.level === 'WARNING' ? 'WARN' : l.level}</span>
                {l.ts && <span className="text-gray-400 w-16 shrink-0">{l.ts}</span>}
                <span className={l.level === 'ERROR' || l.level === 'WARNING' ? 'text-red-700' : 'text-gray-700'}>
                  {l.message}
                </span>
              </div>
            ))}
          </div>
        )}
        {r.logs.length >= 300 && (
          <p className="text-xs text-gray-400 mt-2">
            * Відображаються останні 300 записів журналу. Повний історичний журнал не зберігається.
          </p>
        )}
      </div>

      {/* Category details note */}
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
        <h3 className="font-medium text-gray-900 mb-2">Деталі по категоріях</h3>
        <p className="text-sm text-gray-600">
          Деталі по кожній окремій категорії (які саме категорії були успішно оброблені, а які — ні)
          не зберігаються в історичному записі. Доступна лише загальна статистика та журнал подій.
        </p>
        <p className="text-sm text-gray-600 mt-1">
          Категорій з атрибутами: {r.attributes.categories_processed} / {r.attributes.categories_total}
        </p>
        <p className="text-sm text-gray-600 mt-1">
          Атрибутів імпортовано: {r.attributes.total} (створено: {r.attributes.created}, оновлено: {r.attributes.updated})
        </p>
        <p className="text-sm text-gray-600 mt-1">
          Значень атрибутів: {r.values.total} (створено: {r.values.created}, оновлено: {r.values.updated})
        </p>
      </div>
    </div>
  );
}
