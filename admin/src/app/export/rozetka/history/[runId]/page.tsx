'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { api } from '@/lib/api';
import { PageHeader, Button, LoadingState, ErrorState } from '@/components/ui';

type LogEntry = { level: string; message: string; timestamp?: string };
type ProductResult = { n: number; product_id: number; sku?: string; product_name?: string; status: string; error?: string; operation?: string; reason?: string };
type ErrorDetails = { type?: string; message?: string; last_product_id?: number; last_sku?: string };
type Progress = {
  total: number; processed: number; created: number; updated: number;
  skipped: number; failed: number; errors: number; current_operation?: string;
  error_details?: ErrorDetails; results?: ProductResult[]; logs?: LogEntry[];
};
type ExportDetail = {
  id: number; channel_id: number; run_type: string; status: string;
  started_at: string | null; finished_at: string | null; created_at: string;
  total_count: number; processed_count: number; created_count: number;
  updated_count: number; failed_count: number; skipped_count: number;
  current_stage: string | null; cancel_requested: boolean;
  duration: number | null; progress: Progress | null;
  logs?: LogEntry[]; logs_count?: number; results?: ProductResult[];
  error_details?: ErrorDetails | null;
};

const STATUS_MAP: Record<string, { label: string; color: string; icon: string }> = {
  queued: { label: 'У черзі', color: 'bg-gray-100 text-gray-800', icon: '\u23f3' },
  running: { label: 'Виконується', color: 'bg-blue-100 text-blue-800', icon: '\U0001f504' },
  succeeded: { label: 'Успішно', color: 'bg-green-100 text-green-800', icon: '\u2705' },
  partial: { label: 'З помилками', color: 'bg-yellow-100 text-yellow-800', icon: '\u26a0\ufe0f' },
  failed: { label: 'Помилка', color: 'bg-red-100 text-red-800', icon: '\u274c' },
  cancelled: { label: 'Скасовано', color: 'bg-gray-100 text-gray-500', icon: '\u23f9\ufe0f' },
};

const nf = new Intl.NumberFormat('uk-UA');

function fmtDuration(seconds?: number | null): string {
  if (!seconds && seconds !== 0) return '—';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  const parts: string[] = [];
  if (h > 0) parts.push(`${h}г`);
  if (m > 0) parts.push(`${m}хв`);
  parts.push(`${s}с`);
  return parts.join(' ');
}

function BadgeStatus({ status }: { status: string }) {
  const s = (status || '').toLowerCase();
  const m = STATUS_MAP[s] || { label: status, color: 'bg-gray-100 text-gray-800', icon: '' };
  return <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium ${m.color}`}><span>{m.icon}</span><span>{m.label}</span></span>;
}

function StatCard({ label, value, highlight }: { label: string; value: string | number; highlight?: boolean }) {
  return (
    <div className={`rounded-lg border px-4 py-3 ${highlight ? 'bg-red-50 border-red-200' : 'bg-white border-gray-200'}`}>
      <div className="text-xs text-gray-500 mb-0.5">{label}</div>
      <div className={`text-xl font-bold ${highlight ? 'text-red-700' : 'text-gray-900'}`}>{nf.format(Number(value))}</div>
    </div>
  );
}

export default function ExportDetailPage() {
  const params = useParams<{ runId: string }>();
  const runId = params.runId;
  const [report, setReport] = useState<ExportDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [logLimit, setLogLimit] = useState(200);
  const [resultFilter, setResultFilter] = useState('');

  useEffect(() => {
    if (!runId) return;
    setLoading(true);
    setError(null);
    api.get<ExportDetail>(`/export/channels/rozetka/history/${runId}`)
      .then((d) => setReport(d))
      .catch((e) => setError(e.message || 'Помилка завантаження'))
      .finally(() => setLoading(false));
  }, [runId]);

  if (loading) return <LoadingState label="Завантаження..." />;
  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />;
  if (!report) return <ErrorState message="Експорт не знайдено" />;

  const prog = report.progress;
  const status = (report.status || '').toLowerCase();
  const isActive = ['queued', 'running'].includes(status);
  const logsAll: LogEntry[] = report.logs || prog?.logs || [];
  const logsToShow = logsAll.slice(0, logLimit);
  const resultsAll: ProductResult[] = report.results || prog?.results || [];
  const filteredResults = resultFilter ? resultsAll.filter((r) => r.status === resultFilter) : resultsAll;
  const errDetails: ErrorDetails | null = report.error_details || prog?.error_details || null;

  return (
    <div className="max-w-5xl space-y-6">
      <PageHeader title={`Історія експорту #${report.id}`} />

      <div className="flex items-center gap-3 mb-4">
        <BadgeStatus status={status} />
        {report.cancel_requested && <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded">Скасування запиту</span>}
        <Link href="/export/rozetka/history" className="ml-auto text-sm text-blue-600 hover:text-blue-800 font-medium">← Назад до історії</Link>
      </div>

      {/* Timestamps */}
      <div className="bg-white rounded-lg border border-gray-200 p-5 space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          <div><div className="text-gray-500 text-xs">Розпочато</div><div className="font-medium">{report.started_at ? new Date(report.started_at).toLocaleString('uk-UA') : '—'}</div></div>
          <div><div className="text-gray-500 text-xs">Завершено</div><div className="font-medium">{report.finished_at ? new Date(report.finished_at).toLocaleString('uk-UA') : isActive ? '...' : '—'}</div></div>
          <div><div className="text-gray-500 text-xs">Тривалість</div><div className="font-medium">{fmtDuration(report.duration)}</div></div>
          <div><div className="text-gray-500 text-xs">Тип</div><div className="font-medium">Експорт на Rozetka</div></div>
        </div>
      </div>

      {/* Error details */}
      {errDetails && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-5">
          <h2 className="text-lg font-semibold text-red-700 mb-3 flex items-center gap-2"><span>❌</span> Експорт завершився з помилкою</h2>
          <div className="space-y-2 text-sm">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div><span className="text-gray-500">Тип помилки:</span><div className="font-mono text-red-700 bg-red-100 rounded px-2 py-1 mt-0.5">{errDetails.type || '—'}</div></div>
              <div><span className="text-gray-500">Час:</span><div className="font-medium">{report.finished_at ? new Date(report.finished_at).toLocaleString('uk-UA') : '—'}</div></div>
            </div>
            <div><span className="text-gray-500">Помилка:</span><pre className="mt-1 bg-red-100 border border-red-100 rounded p-3 text-xs overflow-x-auto max-h-40 whitespace-pre-wrap text-red-800">{errDetails.message || 'Невідома помилка'}</pre></div>
            {errDetails.last_sku && (
              <div><span className="text-gray-500">Товар:</span><span className="ml-2 font-mono text-sm">{errDetails.last_sku}</span></div>
            )}
          </div>
        </div>
      )}

      {/* Counts */}
      {report.total_count > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <h2 className="text-lg font-semibold mb-3">Результат експорту</h2>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <StatCard label="✅ Створено" value={report.created_count || 0} />
            <StatCard label="🔄 Оновлено" value={report.updated_count || 0} />
            <StatCard label="⚠️ Пропущено" value={report.skipped_count || 0} />
            <StatCard label="❌ Помилок" value={report.failed_count || 0} highlight={(report.failed_count || 0) > 0} />
            <StatCard label="📦 Всього товарів" value={report.total_count || 0} />
          </div>
        </div>
      )}

      {/* Product results */}
      {resultsAll.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold">Результати товарів ({resultsAll.length})</h2>
            <select value={resultFilter} onChange={(e) => setResultFilter(e.target.value)} className="text-xs border border-gray-200 rounded px-2 py-1">
              <option value="">Усі</option><option value="created">Створені</option><option value="updated">Оновлені</option><option value="unchanged">Без змін</option><option value="skipped">Пропущені</option><option value="failed">Помилки</option>
            </select>
          </div>
          <div className="overflow-x-auto max-h-96 overflow-y-auto border border-gray-100 rounded">
            <table className="w-full text-xs">
              <thead className="text-xs text-gray-500 uppercase bg-gray-50 sticky top-0">
                <tr><th className="p-2 text-left">#</th><th className="p-2 text-left">SKU</th><th className="p-2 text-left">Товар</th><th className="p-2 text-left">Статус</th><th className="p-2 text-left">Результат</th></tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {filteredResults.length === 0 ? (
                  <tr><td colSpan={5} className="p-4 text-center text-gray-400">Немає результатів</td></tr>
                ) : filteredResults.map((r) => {
                  const statusIcon = r.status === 'created' ? '✅' : r.status === 'updated' ? '🔄' : r.status === 'unchanged' ? '➖' : r.status === 'skipped' ? '⚠️' : r.status === 'failed' ? '❌' : '❓';
                  const statusColor = r.status === 'created' ? 'text-green-600' : r.status === 'updated' ? 'text-blue-600' : r.status === 'failed' ? 'text-red-600' : r.status === 'skipped' ? 'text-yellow-600' : 'text-gray-400';
                  return (
                    <tr key={r.n} className="hover:bg-gray-50">
                      <td className="p-2 text-gray-400">{r.n}</td>
                      <td className="p-2 font-mono">{r.sku || '—'}</td>
                      <td className="p-2 max-w-xs truncate">{r.product_name || `#${r.product_id}`}</td>
                      <td className={`p-2 font-medium ${statusColor}`}><span className="flex items-center gap-1"><span>{statusIcon}</span><span>{r.status}</span></span></td>
                      <td className={`p-2 max-w-sm whitespace-normal break-words ${
                        r.status === 'failed' ? 'text-red-600' : r.status === 'skipped' ? 'text-yellow-700' : 'text-gray-600'
                      }`}>
                        {r.status === 'failed' ? r.error || '—' : r.status === 'skipped' ? r.reason || '—' : r.operation || '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Logs */}
      {logsAll.length > 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <h2 className="text-lg font-semibold mb-3">Логи експорту ({logsAll.length} записів)</h2>
          <div className="border border-gray-100 rounded divide-y divide-gray-50 max-h-96 overflow-y-auto text-xs">
            {logsToShow.map((l, i) => (
              <div key={i} className="px-3 py-1.5 flex gap-3">
                <span className="text-gray-400 whitespace-nowrap">{l.timestamp ? new Date(l.timestamp).toLocaleTimeString('uk-UA') : ''}</span>
                <span className={`font-mono uppercase w-16 ${l.level === 'ERROR' ? 'text-red-600' : l.level === 'WARNING' ? 'text-yellow-600' : 'text-gray-600'}`}>{l.level}</span>
                <span className="flex-1 break-all">{l.message}</span>
              </div>
            ))}
          </div>
          {logLimit < logsAll.length && (
            <Button variant="ghost" size="sm" className="mt-2" onClick={() => setLogLimit((p) => Math.min(p + 200, logsAll.length))}>Показати більше</Button>
          )}
        </div>
      ) : (
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <h2 className="text-lg font-semibold mb-3">Логи експорту</h2>
          <p className="text-sm text-gray-500">Записів журналу немає.</p>
        </div>
      )}
    </div>
  );
}
