'use client';

import { use, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { formatDateTime, IMPORT_STATUS_LABELS, importStatusTone } from '@/lib/format';
import {
  PageHeader, Button, Badge, LoadingState, ErrorState,
} from '@/components/ui';

interface UnmappedItem {
  count: number;
  id: string | null;
  skus: string[];
}

interface UnmappedValItem {
  count: number;
  skus: string[];
}

interface LogEntry {
  id: number;
  level: string;
  message: string;
  item_ref: string | null;
  created_at: string;
}

interface Report {
  id: number;
  supplier_id: number;
  supplier_name: string | null;
  import_type: string;
  status: string;
  display_status: string;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  duration: number | null;
  percent: number | null;
  current_stage: string | null;
  total_count: number;
  processed_count: number;
  created_count: number;
  updated_count: number;
  skipped_count: number;
  failed_count: number;
  error_count: number;
  warning_count: number;
  unmapped_categories: Record<string, UnmappedItem>;
  unmapped_attributes: Record<string, UnmappedItem>;
  unmapped_attribute_values: Record<string, Record<string, UnmappedValItem>>;
  unmapped_categories_count: number;
  unmapped_attributes_count: number;
  unmapped_attribute_values_count: number;
  warnings: string[];
  errors: any[];
  has_unmapped: boolean;
  has_errors: boolean;
  logs: LogEntry[];
  error_message?: string;
}

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
  const colorMap: Record<string, string> = {
    COMPLETED: 'bg-green-100 text-green-800',
    COMPLETED_WITH_WARNINGS: 'bg-yellow-100 text-yellow-800',
    FAILED: 'bg-red-100 text-red-800',
    RUNNING: 'bg-blue-100 text-blue-800',
    QUEUED: 'bg-gray-100 text-gray-800',
    CANCELLED: 'bg-gray-100 text-gray-500',
    ABORTED: 'bg-red-100 text-red-800',
  };
  const label: Record<string, string> = {
    COMPLETED: 'Успішно',
    COMPLETED_WITH_WARNINGS: 'З попередженнями',
    FAILED: 'Помилка',
    RUNNING: 'Виконується',
    QUEUED: 'У черзі',
    CANCELLED: 'Скасовано',
    ABORTED: 'Перервано',
  };
  return (
    <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${colorMap[status] || 'bg-gray-100 text-gray-800'}`}>
      {label[status] || status}
    </span>
  );
}

function StatCard({ label, value, highlight }: { label: string; value: string | number; highlight?: boolean }) {
  return (
    <div className={`rounded-lg border px-4 py-3 ${highlight ? 'bg-red-50 border-red-200' : 'bg-white border-gray-200'}`}>
      <div className="text-xs text-gray-500 mb-0.5">{label}</div>
      <div className={`text-xl font-bold ${highlight ? 'text-red-700' : 'text-gray-900'}`}>{nf.format(Number(value))}</div>
    </div>
  );
}

export default function ImportReportPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = Number(params.id);
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAllSkus, setShowAllSkus] = useState<Record<string, boolean>>({});
  const [logLimit, setLogLimit] = useState(100);

  useEffect(() => {
    if (!jobId) return;
    setLoading(true);
    api.get<Report>(`/imports/jobs/${jobId}/report`)
      .then(setReport)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [jobId]);

  if (loading) return <LoadingState label="Завантаження звіту..." />;
  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />;
  if (!report) return <ErrorState message="Звіт не знайдено" />;

  const isRunning = report.status === 'RUNNING' || report.status === 'QUEUED';
  const logsToShow = (report.logs || []).slice(0, logLimit);

  const sectionAnchor = (label: string): string => {
    const map: Record<string, string> = {
      'Категорії': 'section-unmapped-categories',
      'Атрибути': 'section-unmapped-attributes',
      'Значення': 'section-unmapped-values',
      'Попередження': 'section-warnings',
      'Помилки': 'section-errors',
    };
    return map[label] || `section-${label}`;
  };

  const summaryIssues = [
    { label: 'Категорії', count: report.unmapped_categories_count, color: 'bg-yellow-100 text-yellow-800' },
    { label: 'Атрибути', count: report.unmapped_attributes_count, color: 'bg-yellow-100 text-yellow-800' },
    { label: 'Значення', count: report.unmapped_attribute_values_count, color: 'bg-yellow-100 text-yellow-800' },
    { label: 'Попередження', count: report.warnings.length, color: 'bg-yellow-100 text-yellow-800' },
    { label: 'Помилки', count: report.errors.length, color: 'bg-red-100 text-red-800' },
  ];

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <PageHeader
        title={`Звіт імпорту #${report.id}`}
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => router.push('/imports/history')}>
              Назад до історії
            </Button>
          </div>
        }
      />

      {/* Import info */}
      <div className="bg-white rounded-lg border border-gray-200 p-5">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <div className="text-gray-500 text-xs">Постачальник</div>
            <div className="font-medium">{report.supplier_name || `ID ${report.supplier_id}`}</div>
          </div>
          <div>
            <div className="text-gray-500 text-xs">Тип</div>
            <div className="font-medium">{
              { full: 'Повний імпорт', prices: 'Ціни', stock: 'Залишки' }[report.import_type] || report.import_type
            }</div>
          </div>
          <div>
            <div className="text-gray-500 text-xs">Статус</div>
            <div><BadgeStatus status={report.display_status} /></div>
          </div>
          <div>
            <div className="text-gray-500 text-xs">Тривалість</div>
            <div className="font-medium">{fmtDuration(report.duration ?? undefined)}</div>
          </div>
          <div>
            <div className="text-gray-500 text-xs">Початок</div>
            <div className="font-medium">{formatDateTime(report.started_at)}</div>
          </div>
          <div>
            <div className="text-gray-500 text-xs">Завершення</div>
            <div className="font-medium">{formatDateTime(report.finished_at)}</div>
          </div>
          <div>
            <div className="text-gray-500 text-xs">Етап</div>
            <div className="font-medium">{report.current_stage || '—'}</div>
          </div>
          <div>
            <div className="text-gray-500 text-xs">Всього товарів</div>
            <div className="font-medium">{nf.format(report.total_count)}</div>
          </div>
        </div>

        {/* Progress bar for running */}
        {isRunning && report.percent != null && (
          <div className="mt-4">
            <div className="flex justify-between text-xs text-gray-500 mb-1">
              <span>Прогрес</span>
              <span>{report.percent}%</span>
            </div>
            <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
              <div className="h-full bg-blue-500 transition-all" style={{ width: report.percent + '%' }} />
            </div>
          </div>
        )}
      </div>

      {/* Problem summary banner */}
      {(report.has_unmapped || report.has_errors) && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <span className="text-yellow-600 text-xl">{'\u26a0\ufe0f'}</span>
            <div className="flex-1">
              <div className="font-medium text-yellow-800">Виявлено проблеми під час імпорту</div>
              <div className="flex flex-wrap gap-2 mt-2">
                {summaryIssues.map((s) => s.count > 0 && (
                  <a
                    key={s.label}
                    href={`#${sectionAnchor(s.label)}`}
                    className={`inline-block px-3 py-1 rounded-full text-xs font-medium ${s.color}`}
                  >
                    {s.label}: {s.count}
                  </a>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Всього" value={report.total_count} />
        <StatCard label="Оброблено" value={report.processed_count} />
        <StatCard label="Створено" value={report.created_count} />
        <StatCard label="Оновлено" value={report.updated_count} />
        <StatCard label="Пропущено" value={report.skipped_count} />
        <StatCard label="Помилок" value={report.failed_count} highlight={report.failed_count > 0} />
        <StatCard label="Попереджень" value={report.warning_count} highlight={report.warning_count > 0} />
        <StatCard label="Немаппінгу" value={report.unmapped_categories_count + report.unmapped_attributes_count + report.unmapped_attribute_values_count} highlight={report.has_unmapped} />
      </div>

      {/* Unmapped categories */}
      <section id="section-unmapped-categories" className="bg-white rounded-lg border border-gray-200 p-5">
        <h2 className="text-lg font-semibold mb-3">Невідображені категорії ({report.unmapped_categories_count})</h2>
        {report.unmapped_categories_count === 0 ? (
          <p className="text-sm text-gray-500">Немає невідображених категорій.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-gray-500">
                  <th className="pb-2 pr-4">Назва категорії</th>
                  <th className="pb-2 pr-4 text-right">Кількість</th>
                  <th className="pb-2 pr-4">ID</th>
                  <th className="pb-2">Приклади SKU</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(report.unmapped_categories).map(([name, item]) => (
                  <tr key={name} className="border-b border-gray-50">
                    <td className="py-2 pr-4 font-medium">{name === '*' ? '(загальна кількість)' : name}</td>
                    <td className="py-2 pr-4 text-right">{nf.format(item.count)}</td>
                    <td className="py-2 pr-4 text-gray-500">{item.id || '—'}</td>
                    <td className="py-2">
                      {item.skus.length > 0 ? item.skus.slice(0, 5).join(', ') : '—'}
                      {item.skus.length > 5 && (
                        <button
                          onClick={() => setShowAllSkus((p) => ({ ...p, ['cat-' + name]: !p['cat-' + name] }))}
                          className="ml-1 text-blue-600 hover:text-blue-800 text-xs"
                        >
                          {showAllSkus['cat-' + name] ? '\u2191' : `+${item.skus.length - 5}`}
                        </button>
                      )}
                      {item.skus.length > 5 && showAllSkus['cat-' + name] && (
                        <div className="mt-1 text-xs text-gray-500">{item.skus.join(', ')}</div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Unmapped attributes */}
      <section id="section-unmapped-attributes" className="bg-white rounded-lg border border-gray-200 p-5">
        <h2 className="text-lg font-semibold mb-3">Невідображені атрибути ({report.unmapped_attributes_count})</h2>
        {report.unmapped_attributes_count === 0 ? (
          <p className="text-sm text-gray-500">Немає невідображених атрибутів.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-gray-500">
                  <th className="pb-2 pr-4">Назва атрибуту</th>
                  <th className="pb-2 pr-4 text-right">Кількість</th>
                  <th className="pb-2 pr-4">ID</th>
                  <th className="pb-2">Приклади SKU</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(report.unmapped_attributes).map(([name, item]) => (
                  <tr key={name} className="border-b border-gray-50">
                    <td className="py-2 pr-4 font-medium">{name === '*' ? '(загальна кількість)' : name}</td>
                    <td className="py-2 pr-4 text-right">{nf.format(item.count)}</td>
                    <td className="py-2 pr-4 text-gray-500">{item.id || '—'}</td>
                    <td className="py-2">
                      {item.skus.length > 0 ? item.skus.slice(0, 5).join(', ') : '—'}
                      {item.skus.length > 5 && (
                        <button
                          onClick={() => setShowAllSkus((p) => ({ ...p, ['attr-' + name]: !p['attr-' + name] }))}
                          className="ml-1 text-blue-600 hover:text-blue-800 text-xs"
                        >
                          {showAllSkus['attr-' + name] ? '\u2191' : `+${item.skus.length - 5}`}
                        </button>
                      )}
                      {item.skus.length > 5 && showAllSkus['attr-' + name] && (
                        <div className="mt-1 text-xs text-gray-500">{item.skus.join(', ')}</div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Unmapped attribute values */}
      <section id="section-unmapped-values" className="bg-white rounded-lg border border-gray-200 p-5">
        <h2 className="text-lg font-semibold mb-3">Невідображені значення атрибутів ({report.unmapped_attribute_values_count})</h2>
        {report.unmapped_attribute_values_count === 0 ? (
          <p className="text-sm text-gray-500">Немає невідображених значень.</p>
        ) : (
          <div className="space-y-4">
            {Object.entries(report.unmapped_attribute_values).map(([attrName, values]) => (
              <div key={attrName}>
                <h3 className="font-medium text-sm text-gray-700 mb-1">{attrName === '*' ? '(загальна кількість)' : attrName}</h3>
                <div className="ml-4 space-y-1">
                  {Object.entries(values).map(([val, info]) => (
                    <div key={val} className="text-sm flex items-start gap-2">
                      <span className="font-mono text-xs bg-gray-100 px-1.5 py-0.5 rounded">{val === '*' ? '(невідомі)' : val}</span>
                      <span className="text-gray-500 text-xs whitespace-nowrap">{nf.format(info.count)} прод.</span>
                      {info.skus.length > 0 && (
                        <span className="text-gray-400 text-xs truncate max-w-xs">
                          ({info.skus.slice(0, 3).join(', ')}{info.skus.length > 3 ? '...' : ''})
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Warnings */}
      <section id="section-warnings" className="bg-white rounded-lg border border-gray-200 p-5">
        <h2 className="text-lg font-semibold mb-3">Попередження ({report.warnings.length})</h2>
        {report.warnings.length === 0 ? (
          <p className="text-sm text-gray-500">Немає попереджень.</p>
        ) : (
          <ul className="space-y-1">
            {report.warnings.map((w, i) => (
              <li key={i} className="text-sm flex items-start gap-2">
                <span className="text-yellow-500 mt-0.5">{'\u26a0'}</span>
                <span>{w}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Errors */}
      <section id="section-errors" className="bg-white rounded-lg border border-red-200 p-5">
        <h2 className="text-lg font-semibold mb-3 text-red-700">Помилки ({report.errors.length})</h2>
        {report.errors.length === 0 ? (
          <p className="text-sm text-gray-500">Немає помилок.</p>
        ) : (
          <ul className="space-y-2">
            {report.errors.map((e, i) => (
              <li key={i} className="text-sm bg-red-50 rounded p-2">
                {typeof e === 'string' ? e : JSON.stringify(e)}
              </li>
            ))}
          </ul>
        )}
        {report.error_message && (
          <div className="mt-2 text-sm text-red-700 bg-red-50 rounded p-2">
            <strong>Деталі:</strong> {report.error_message}
          </div>
        )}
      </section>

      {/* Import logs */}
      <section className="bg-white rounded-lg border border-gray-200 p-5">
        <h2 className="text-lg font-semibold mb-3">Журнал імпорту ({report.logs?.length || 0} записів)</h2>
        {!report.logs || report.logs.length === 0 ? (
          <p className="text-sm text-gray-500">Записів журналу немає.</p>
        ) : (
          <>
            <div className="border border-gray-100 rounded divide-y divide-gray-50 max-h-96 overflow-y-auto text-xs">
              {logsToShow.map((l) => {
                const levelColor: Record<string, string> = {
                  INFO: 'text-gray-600',
                  WARNING: 'text-yellow-600',
                  ERROR: 'text-red-600',
                  SUCCEEDED: 'text-green-600',
                  FAILED: 'text-red-600',
                };
                return (
                  <div key={l.id} className="px-3 py-1.5 flex gap-3">
                    <span className="text-gray-400 whitespace-nowrap">
                      {new Date(l.created_at).toLocaleTimeString('uk-UA')}
                    </span>
                    <span className={`font-mono uppercase w-16 ${levelColor[l.level] || 'text-gray-400'}`}>
                      {l.level}
                    </span>
                    <span className="flex-1 break-all">{l.message}{l.item_ref ? ` (${l.item_ref})` : ''}</span>
                  </div>
                );
              })}
            </div>
            {logLimit < (report.logs?.length || 0) && (
              <Button
                variant="ghost"
                size="sm"
                className="mt-2"
                onClick={() => setLogLimit((p) => Math.min(p + 200, report.logs?.length || 0))}
              >
                Показати більше
              </Button>
            )}
          </>
        )}
      </section>

 </div>
  );
}
