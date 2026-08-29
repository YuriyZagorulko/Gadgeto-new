'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { api } from '@/lib/api';
import { PageHeader, Button, LoadingState, ErrorState } from '@/components/ui';

type LogEntry = { level: string; message: string; timestamp?: string };
type MissingAttr = { attribute_id?: number | string; attribute_name?: string };
type MissingValue = MissingAttr & { attribute_value_id?: number | string; value_name?: string };
type IssueSummary = {
  total: number;
  missing_attribute_mappings: MissingAttr[];
  missing_value_mappings: MissingValue[];
  other: { code?: string; message?: string }[];
  external_category_id?: string | null;
};
type ProductResult = {
  n: number; product_id: number; sku?: string; product_name?: string;
  status: string; error?: string; operation?: string; reason?: string;
  issues?: IssueSummary;
};
type ErrorDetails = { type?: string; message?: string; last_product_id?: number; last_sku?: string };
type Progress = {
  total: number; processed: number; created: number; updated: number;
  skipped: number; failed: number; errors: number; current_operation?: string;
  unchanged?: number; not_exported?: number;
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

const RESULT_LABELS: Record<string, { label: string; icon: string; color: string }> = {
  created: { label: 'Створено', icon: '✅', color: 'text-green-600' },
  updated: { label: 'Оновлено', icon: '🔄', color: 'text-blue-600' },
  unchanged: { label: 'Без змін', icon: '➖', color: 'text-gray-500' },
  skipped: { label: 'Не експортовано', icon: '⚠️', color: 'text-yellow-600' },
  failed: { label: 'Помилка', icon: '❌', color: 'text-red-600' },
};

const MAPPING_PAGE = '/export/rozetka/mapping';

function mappingAttrHref(extCatId?: string | null): string {
  const sp = new URLSearchParams();
  sp.set('tab', 'attributes');
  if (extCatId) sp.set('category_external_id', String(extCatId));
  return `${MAPPING_PAGE}?${sp.toString()}`;
}

function mappingValueHref(attrId?: number | string | null, extCatId?: string | null): string {
  const sp = new URLSearchParams();
  sp.set('tab', 'values');
  if (attrId) sp.set('attribute_id', String(attrId));
  if (extCatId) sp.set('category_external_id', String(extCatId));
  return `${MAPPING_PAGE}?${sp.toString()}`;
}

/** Grouped, actionable view of a validation-skipped product's issues.
 *  The raw `reason` stays available in a collapsible block — this summary
 *  is additive and never replaces backend data. */
function SkippedIssues({ r }: { r: ProductResult }) {
  const iss = r.issues;
  if (!iss) return <span className="text-yellow-700">{r.reason || '—'}</span>;
  const attrs = iss.missing_attribute_mappings || [];
  const values = iss.missing_value_mappings || [];
  const other = iss.other || [];
  const total = iss.total ?? (attrs.length + values.length + other.length);
  const catId = iss.external_category_id || null;
  const mappingCount = attrs.length + values.length;
  const headline = mappingCount === total
    ? `${total} проблем маппінгу`
    : mappingCount > 0
      ? `${mappingCount} проблем маппінгу, ${total - mappingCount} інших`
      : `${total} проблем валідації`;
  return (
    <div className="space-y-2">
      <div className="font-medium text-yellow-800">{headline}</div>
      {catId && <div className="text-gray-400">Категорія Rozetka: <span className="font-mono">{catId}</span></div>}
      {attrs.length > 0 && (
        <div>
          <div className="text-gray-500">Атрибути без маппінгу — {attrs.length}</div>
          <ul className="list-disc list-inside">
            {attrs.map((a, i) => (
              <li key={i}>
                {a.attribute_name || a.attribute_id || '—'}
                {' '}
                <Link className="text-blue-600 hover:text-blue-800 whitespace-nowrap" href={mappingAttrHref(catId)}>Замапити атрибут →</Link>
              </li>
            ))}
          </ul>
        </div>
      )}
      {values.length > 0 && (
        <div>
          <div className="text-gray-500">Значення без маппінгу — {values.length}</div>
          <ul className="list-disc list-inside">
            {values.map((v, i) => (
              <li key={i}>
                {v.attribute_name || v.attribute_id || '—'} → {v.value_name || '—'}
                {' '}
                <Link className="text-blue-600 hover:text-blue-800 whitespace-nowrap" href={mappingValueHref(v.attribute_id, catId)}>Замапити значення →</Link>
              </li>
            ))}
          </ul>
        </div>
      )}
      {other.length > 0 && (
        <div>
          <div className="text-gray-500">Інші проблеми — {other.length}</div>
          <ul className="list-disc list-inside">
            {other.map((o, i) => (<li key={i}>{o.message || o.code || '—'}</li>))}
          </ul>
        </div>
      )}
      {r.reason && (
        <details className="text-gray-400">
          <summary className="cursor-pointer select-none hover:text-gray-600">Повна причина</summary>
          <div className="mt-1 whitespace-normal break-words text-gray-500">{r.reason}</div>
        </details>
      )}
    </div>
  );
}

function BadgeStatus({ status }: { status: string }) {
  const s = (status || '').toLowerCase();
  const m = STATUS_MAP[s] || { label: status, color: 'bg-gray-100 text-gray-800', icon: '' };
  return <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium ${m.color}`}><span>{m.icon}</span><span>{m.label}</span></span>;
}

function StatCard({ label, value, tone }: { label: string; value: string | number; tone?: 'neutral' | 'ok' | 'bad' }) {
  const box = tone === 'bad' ? 'bg-red-50 border-red-200'
    : tone === 'ok' ? 'bg-green-50 border-green-200'
    : 'bg-white border-gray-200';
  const text = tone === 'bad' ? 'text-red-700'
    : tone === 'ok' ? 'text-green-700'
    : 'text-gray-900';
  return (
    <div className={`rounded-lg border px-4 py-3 ${box}`}>
      <div className="text-xs text-gray-500 mb-0.5">{label}</div>
      <div className={`text-xl font-bold ${text}`}>{nf.format(Number(value))}</div>
    </div>
  );
}

const RESULT_STATUS_LABELS: Record<string, string> = {
  created: 'Створено', updated: 'Оновлено', unchanged: 'Без змін',
  skipped: 'Не експортовано', failed: 'Помилка',
};

/** Grouped validation issues for a skipped product (from the run's
 *  per-product `issues` summary).  The raw `reason` stays available in the
 *  row and is shown in a collapsible block below. */
function MappingIssues({ issues }: { issues: IssueSummary }) {
  const mAttrs = issues.missing_attribute_mappings || [];
  const mVals = issues.missing_value_mappings || [];
  const other = issues.other || [];
  const q = (s?: string) => (s ? encodeURIComponent(s) : '');
  return (
    <div className="space-y-2">
      <div className="font-medium text-yellow-800">
        ⚠️ Не експортовано — {issues.total} проблем маппінгу/валідації
      </div>
      {mAttrs.length > 0 && (
        <div>
          <div className="font-medium text-gray-700">Атрибути без маппінгу — {mAttrs.length}</div>
          <ul className="list-disc list-inside text-gray-600">
            {mAttrs.map((a, i) => (
              <li key={i} className="break-words">{a.attribute_name || `#${a.attribute_id}`}</li>
            ))}
          </ul>
          <Link
            className="inline-block mt-0.5 text-blue-600 hover:text-blue-800 underline"
            href={`/export/rozetka/mapping?tab=attributes&q=${q(mAttrs[0]?.attribute_name)}`}
          >
            Замапити атрибут →
          </Link>
        </div>
      )}
      {mVals.length > 0 && (
        <div>
          <div className="font-medium text-gray-700">Значення без маппінгу — {mVals.length}</div>
          <ul className="list-disc list-inside text-gray-600">
            {mVals.map((v, i) => (
              <li key={i} className="break-words">
                {v.attribute_name || `#${v.attribute_id}`} → {v.value_name || '—'}
              </li>
            ))}
          </ul>
          <Link
            className="inline-block mt-0.5 text-blue-600 hover:text-blue-800 underline"
            href={`/export/rozetka/mapping?tab=values&q=${q(mVals[0]?.attribute_name)}`}
          >
            Замапити значення →
          </Link>
        </div>
      )}
      {other.length > 0 && (
        <div>
          <div className="font-medium text-gray-700">Інші проблеми — {other.length}</div>
          <ul className="list-disc list-inside text-gray-600">
            {other.map((o, i) => (
              <li key={i} className="break-words">{o.message || o.code}</li>
            ))}
          </ul>
        </div>
      )}
      {issues.external_category_id && (
        <div className="text-gray-400">Категорія Rozetka: {issues.external_category_id}</div>
      )}
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
  const resultsAll: ProductResult[] = report.results || prog?.results || [];
  const filteredResults = resultFilter ? resultsAll.filter((r) => r.status === resultFilter) : resultsAll;
  // New runs split skipped into unchanged/not_exported in progress_json.
  // Pre-fix runs only have the combined counter — approximate the split from
  // per-product results when they are complete (< 1000 rows are stored),
  // otherwise count everything skipped as "not exported".
  const exportedCount = (report.created_count || 0) + (report.updated_count || 0);
  const resultsComplete = resultsAll.length > 0 && resultsAll.length < 1000;
  const unchangedCount = prog?.unchanged
    ?? (resultsComplete ? resultsAll.filter((r) => r.status === 'unchanged').length : 0);
  const notExportedCount = prog?.not_exported
    ?? Math.max(0, (report.skipped_count || 0) - unchangedCount);
  const status = (report.status || '').toLowerCase();
  const isActive = ['queued', 'running'].includes(status);
  const logsAll: LogEntry[] = report.logs || prog?.logs || [];
  const logsToShow = logsAll.slice(0, logLimit);
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
            <StatCard label="📦 Всього товарів" value={report.total_count || 0} />
            <StatCard label="🚀 Успішно експортовано" value={exportedCount} tone={exportedCount > 0 ? 'ok' : 'neutral'} />
            <StatCard label="✅ Створено" value={report.created_count || 0} />
            <StatCard label="🔄 Оновлено" value={report.updated_count || 0} />
            <StatCard label="➖ Без змін" value={unchangedCount} />
            <StatCard label="⚠️ Не експортовано" value={notExportedCount} tone={notExportedCount > 0 ? 'bad' : 'neutral'} />
            <StatCard label="❌ Помилки" value={report.failed_count || 0} tone={(report.failed_count || 0) > 0 ? 'bad' : 'neutral'} />
          </div>
        </div>
      )}

      {/* Product results */}
      {resultsAll.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold">Результати товарів ({resultsAll.length})</h2>
            <select value={resultFilter} onChange={(e) => setResultFilter(e.target.value)} className="text-xs border border-gray-200 rounded px-2 py-1">
              <option value="">Усі</option><option value="created">Створені</option><option value="updated">Оновлені</option><option value="unchanged">Без змін</option><option value="skipped">Не експортовані</option><option value="failed">Помилки</option>
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
                      <td className={`p-2 font-medium ${statusColor}`}><span className="flex items-center gap-1"><span>{statusIcon}</span><span>{RESULT_STATUS_LABELS[r.status] || r.status}</span></span></td>
                      <td className={`p-2 max-w-sm whitespace-normal break-words ${
                        r.status === 'failed' ? 'text-red-600' : r.status === 'skipped' ? 'text-yellow-700' : 'text-gray-600'
                      }`}>
                        {r.status === 'failed'
                          ? (r.error || '—')
                          : r.status === 'skipped'
                            ? (r.issues
                                ? <MappingIssues issues={r.issues} />
                                : <div className="font-medium text-yellow-800">⚠️ Не експортовано</div>)
                            : (r.operation || '—')}
                        {r.status === 'skipped' && r.reason && (
                          <details className="mt-1">
                            <summary className="cursor-pointer text-gray-400">Повна причина</summary>
                            <div className="mt-1 text-gray-500 break-words">{r.reason}</div>
                          </details>
                        )}
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
