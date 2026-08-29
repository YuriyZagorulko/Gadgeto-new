'use client';

import { use, useEffect, useState, useCallback, useRef } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { formatDateTime, IMPORT_STATUS_LABELS, importStatusTone } from '@/lib/format';
import {
  PageHeader, Button, Badge, LoadingState, ErrorState, Modal, Input, Select,
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
supplier_code: string | null;
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
  const [mappingModal, setMappingModal] = useState<{
    kind: 'categories' | 'attributes' | 'values';
    itemName: string;
    open: boolean;
  } | null>(null);
  const [mappingTarget, setMappingTarget] = useState<{ id: number; name: string } | null>(null);
  const [mappingSearch, setMappingSearch] = useState('');
  const [mappingSearchResults, setMappingSearchResults] = useState<{ id: number; name: string }[]>([]);
  const [mappingSearchLoading, setMappingSearchLoading] = useState(false);
  const [mappingSaving, setMappingSaving] = useState(false);
  const [mappingAttrId, setMappingAttrId] = useState<number | null>(null);
const [mappingValueMode, setMappingValueMode] = useState<'existing' | 'create'>('existing');
  const [mappingNewValue, setMappingNewValue] = useState('');
  const [mappingAttrName, setMappingAttrName] = useState<string | null>(null);
  // Create entity state
  const [createModal, setCreateModal] = useState<{
    kind: 'categories' | 'attributes' | 'values';
    itemName: string;
    open: boolean;
    attrId?: number;
    attrName?: string;
  } | null>(null);
  const [createName, setCreateName] = useState('');
  const [createParentSearch, setCreateParentSearch] = useState('');
  const [createParentResults, setCreateParentResults] = useState<{ id: number; name: string }[]>([]);
  const [createParentId, setCreateParentId] = useState<number | null>(null);
  const [createParentName, setCreateParentName] = useState('');
  const [createSaving, setCreateSaving] = useState(false);
  const [logLimit, setLogLimit] = useState(100);

const attrResolved = useRef(false);
  useEffect(() => {
    if (!jobId) return;
    setLoading(true);
    api.get<Report>(`/imports/jobs/${jobId}/report`)
      .then(setReport)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [jobId]);

const handleMappingSave = async () => {
    if (!mappingModal || !report) return;
    let supCode = (report.supplier_code || report.supplier_name || '').toLowerCase();
    if (!supCode) { alert('Не вказано код постачальника'); return; }
    // For values in 'create' mode: require new value text instead of mappingTarget
    if (mappingModal.kind === 'values' && mappingValueMode === 'create') {
      if (!mappingNewValue.trim() || !mappingAttrId) return;
    } else if (!mappingTarget) return;
    setMappingSaving(true);
    try {
      let targetId = mappingTarget?.id;
      if (mappingModal.kind === 'values' && mappingValueMode === 'create' && mappingAttrId) {
        // 1. Create the new internal value
        const createRes = await api.post<{ ok: boolean; id: number }>(`/attributes/${mappingAttrId}/values`, {
          value: mappingNewValue.trim(),
          is_active: true,
        });
        targetId = createRes.id;
      }
      // For value mappings: extract supplier attribute name and value from itemName
      // itemName format: "attrName = val"
      const isValue = mappingModal.kind === 'values';
      let supplierItemName = mappingModal.itemName;
      let supplierParentName: string | undefined = undefined;
      if (isValue) {
        const eqIdx = mappingModal.itemName.indexOf(' = ');
        if (eqIdx !== -1) {
          supplierParentName = mappingModal.itemName.slice(0, eqIdx);
          supplierItemName = mappingModal.itemName.slice(eqIdx + 3);
        }
      }
      // 2. Create the mapping (either existing or freshly created value)
      const body: Record<string, any> = {
        supplier_code: supCode,
        supplier_item_name: supplierItemName,
        catalog_item_id: targetId,
      };
      if (isValue && supplierParentName) {
        body.supplier_parent_name = supplierParentName;
      }
      await api.post(`/mappings/${mappingModal.kind}`, body);
      setMappingModal(null);
      setMappingTarget(null);
      setMappingSearch('');
      setMappingSearchResults([]);
      setMappingAttrId(null);
      setMappingAttrName(null);
      setMappingSaving(false);
      setMappingValueMode('existing');
      setMappingNewValue('');
      // Refresh report
      api.get<Report>(`/imports/jobs/${jobId}/report`)
        .then(setReport)
        .catch(() => {});
    } catch (e: any) {
      alert(e.message || 'Помилка створення маппінгу');
      setMappingSaving(false);
    }
  };

  // Search internal entities when modal opens or search text changes
  useEffect(() => {
    if (!mappingModal) {
      attrResolved.current = false;
      return;
    }
    const kind = mappingModal.kind;

    // For values: first resolve the internal attribute ID (once per modal open)
    if (kind === 'values' && !mappingAttrId && !attrResolved.current) {
      if (!mappingModal.itemName) return;
      attrResolved.current = true;
      // Look up the supplier attribute mapping to find the internal attribute
      api.get<any>(`/mappings/supplier-attributes?q=${encodeURIComponent(mappingModal.itemName.split(' = ')[0] || mappingModal.itemName)}&unmapped=false&_=${Date.now()}`)
        .then((res: any) => {
          const items = res.items || [];
          const matched = items.find((i: any) => i.catalog_name);
          if (matched) {
            setMappingAttrId(matched.catalog_item_id || Number(matched.id));
            setMappingAttrName(matched.catalog_name || matched.catalog_item_name);
          }
        })
        .catch(() => {});
      return;
    }

    if (!mappingSearch.trim() && kind !== 'values') {
      setMappingSearchResults([]);
      return;
    }
    setMappingSearchLoading(true);
    const t = setTimeout(() => {
      let url = '';
      if (kind === 'categories') {
        url = `/categories?search=${encodeURIComponent(mappingSearch)}`;
      } else if (kind === 'attributes') {
        url = `/attributes?search=${encodeURIComponent(mappingSearch)}&per_page=15`;
      } else if (kind === 'values' && mappingAttrId) {
        url = `/attributes/${mappingAttrId}/values`;
      }
      if (!url) { setMappingSearchLoading(false); return; }
      api.get<any>(url)
        .then((res: any) => {
          const items = res.items || [];
          if (kind === 'values') {
            // Filter by search term client-side since values API doesn't support search
            const q = mappingSearch.toLowerCase();
            const filtered = items.filter((v: any) => v.value?.toLowerCase().includes(q));
            setMappingSearchResults(filtered.map((v: any) => ({ id: v.id, name: v.value || String(v.value) })));
          } else {
            setMappingSearchResults(items.map((i: any) => ({ id: i.id, name: i.name })));
          }
        })
        .catch(() => setMappingSearchResults([]))
        .finally(() => setMappingSearchLoading(false));
    }, 300);
    return () => clearTimeout(t);
  }, [mappingModal, mappingSearch, mappingAttrId, report, jobId]);
// Create entity handler
  const handleCreate = async () => {
    if (!createModal || !createName.trim()) return;
    setCreateSaving(true);
    try {
      if (createModal.kind === 'categories') {
        await api.post('/categories', {
          name: createName.trim(),
          parent_id: createParentId || undefined,
          is_active: true,
        });
      } else if (createModal.kind === 'attributes') {
        await api.post('/attributes', {
          name: createName.trim(),
          type: 'select',
          is_filterable: true,
        });
      } else if (createModal.kind === 'values' && createModal.attrId) {
        await api.post(`/attributes/${createModal.attrId}/values`, {
          value: createName.trim(),
          is_active: true,
        });
      }
      setCreateModal(null);
      setCreateName('');
      setCreateParentId(null);
      setCreateParentName('');
      setCreateParentSearch('');
      setCreateParentResults([]);
      setCreateSaving(false);
      // Refresh report
      api.get<Report>(`/imports/jobs/${jobId}/report`)
        .then(setReport)
        .catch(() => {});
    } catch (e: any) {
      alert(e.message || 'Помилка створення');
      setCreateSaving(false);
    }
  };

  // Parent category search effect
  useEffect(() => {
    if (!createModal || createModal.kind !== 'categories' || !createParentSearch.trim()) {
      setCreateParentResults([]);
      return;
    }
    const t = setTimeout(() => {
      api.get<any>(`/categories?search=${encodeURIComponent(createParentSearch)}`)
        .then((res: any) => {
          const items = res.items || [];
          setCreateParentResults(items.slice(0, 10).map((i: any) => ({ id: i.id, name: i.name })));
        })
        .catch(() => setCreateParentResults([]));
    }, 300);
    return () => clearTimeout(t);
  }, [createModal, createParentSearch]);
  const downloadReport = useCallback(() => {
    if (!report) return;
    const lines: string[] = [];
    const add = (v: string) => lines.push(v);
    const sep = () => add('─'.repeat(60));

    add(`Звіт імпорту #${report.id}`);
    add(`Сформовано: ${new Date().toLocaleString('uk-UA')}`);
    sep();
    add(`Постачальник: ${report.supplier_name || `ID ${report.supplier_id}`}`);
    add(`Тип: ${({ full: 'Повний імпорт', prices: 'Ціни', stock: 'Залишки' } as Record<string, string>)[report.import_type] || report.import_type}`);
    add(`Статус: ${report.display_status || report.status}`);
    add(`Початок: ${report.started_at ? new Date(report.started_at).toLocaleString('uk-UA') : '—'}`);
    add(`Завершення: ${report.finished_at ? new Date(report.finished_at).toLocaleString('uk-UA') : '—'}`);
    add(`Тривалість: ${fmtDuration(report.duration ?? undefined)}`);
    sep();
    add(`Всього товарів: ${report.total_count}`);
    add(`Оброблено: ${report.processed_count}`);
    add(`Створено: ${report.created_count}`);
    add(`Оновлено: ${report.updated_count}`);
    add(`Пропущено: ${report.skipped_count}`);
    add(`Помилок: ${report.failed_count}`);
    add(`Попереджень: ${report.warning_count}`);
    sep();

    if (report.unmapped_categories_count > 0) {
      add(`\nНевідображені категорії (${report.unmapped_categories_count}):`);
      for (const [name, item] of Object.entries(report.unmapped_categories)) {
        add(`  ${name} — ${item.count} товар(ів), ID: ${item.id || '—'}, SKU: ${(item.skus || []).slice(0, 5).join(', ')}${item.skus?.length > 5 ? '...' : ''}`);
      }
    }
    if (report.unmapped_attributes_count > 0) {
      add(`\nНевідображені атрибути (${report.unmapped_attributes_count}):`);
      for (const [name, item] of Object.entries(report.unmapped_attributes)) {
        add(`  ${name} — ${item.count} товар(ів), SKU: ${(item.skus || []).slice(0, 5).join(', ')}${item.skus?.length > 5 ? '...' : ''}`);
      }
    }
    if (report.unmapped_attribute_values_count > 0) {
      add(`\nНевідображені значення атрибутів (${report.unmapped_attribute_values_count}):`);
      for (const [attr, vals] of Object.entries(report.unmapped_attribute_values)) {
        for (const [val, info] of Object.entries(vals)) {
          add(`  ${attr} = ${val} — ${info.count} товар(ів), SKU: ${(info.skus || []).slice(0, 5).join(', ')}${info.skus?.length > 5 ? '...' : ''}`);
        }
      }
    }

    if (report.warnings.length > 0) {
      add(`\nПопередження (${report.warnings.length}):`);
      for (const w of report.warnings) add(`  [WARN] ${w}`);
    }
    if (report.errors.length > 0) {
      add(`\nПомилки (${report.errors.length}):`);
      for (const e of report.errors) add(`  [ERROR] ${typeof e === 'string' ? e : JSON.stringify(e)}`);
    }
    if (report.error_message) add(`\nДеталі помилки: ${report.error_message}`);

    if (report.logs && report.logs.length > 0) {
      add(`\nЖурнал імпорту (${report.logs.length} записів):`);
      for (const l of report.logs) {
        add(`  [${l.level}] ${new Date(l.created_at).toLocaleString('uk-UA')} — ${l.message}${l.item_ref ? ` (${l.item_ref})` : ''}`);
      }
    }

    const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `import-report-${report.id}-${new Date().toISOString().slice(0, 10)}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [report]);

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
            <Button variant="secondary" onClick={downloadReport}>
              Завантажити звіт
            </Button>
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
                  <th className="pb-2">Дії</th>
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
                    <td className="py-2">
                      <div className="flex gap-2">
                        <button
                          onClick={() => setMappingModal({ kind: 'categories', itemName: name, open: true })}
                          className="text-xs text-blue-600 hover:text-blue-800"
                        >
                          Замапити
                        </button>
                        <button
                          onClick={() => {
                            setCreateModal({ kind: 'categories', itemName: name, open: true });
                            setCreateName(name);
                          }}
                          className="text-xs text-green-600 hover:text-green-800"
                        >
                          Створити категорію
                        </button>
                      </div>
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
                  <th className="pb-2">Дії</th>
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
                    <td className="py-2">
                      <div className="flex gap-2">
                        <button
                          onClick={() => setMappingModal({ kind: 'attributes', itemName: name, open: true })}
                          className="text-xs text-blue-600 hover:text-blue-800"
                        >
                          Замапити
                        </button>
                        <button
                          onClick={() => {
                            setCreateModal({ kind: 'attributes', itemName: name, open: true });
                            setCreateName(name);
                          }}
                          className="text-xs text-green-600 hover:text-green-800"
                        >
                          Створити атрибут
                        </button>
                      </div>
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
                      <button
                        onClick={() => { setMappingModal({ kind: 'values', itemName: attrName + ' = ' + val, open: true }); setMappingNewValue(val); setMappingValueMode('existing'); }}
                        className="text-xs text-blue-600 hover:text-blue-800 ml-2"
                      >
                        Замапити
                      </button>
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

{/* Mapping modal */}
      {mappingModal && report && (
        <Modal
          open={true}
          title={`Створення маппінгу ${
            mappingModal.kind === 'categories' ? 'категорії' :
            mappingModal.kind === 'attributes' ? 'атрибуту' : 'значення'
          }`}
          onClose={() => setMappingModal(null)}
        >
          <div className="space-y-4">
            {/* Supplier context */}
            <div className="bg-gray-50 border border-gray-200 rounded-md p-3">
              <div className="text-xs text-gray-500 mb-1">Постачальник</div>
              <div className="text-sm font-medium">{report.supplier_code || report.supplier_name || '—'}</div>
            </div>

            {/* Source item */}
            <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
              <div className="text-[11px] uppercase tracking-wide text-blue-600 mb-1">
                {mappingModal.kind === 'categories' ? 'КАТЕГОРІЯ ПОСТАЧАЛЬНИКА' :
                 mappingModal.kind === 'attributes' ? 'АТРИБУТ ПОСТАЧАЛЬНИКА' :
                 'ЗНАЧЕННЯ ПОСТАЧАЛЬНИКА'}
              </div>
              <div className="font-semibold text-sm">{mappingModal.itemName}</div>
            </div>

            {/* Values: show resolved internal attribute */}
            {mappingModal.kind === 'values' && (
              mappingAttrId && mappingAttrName ? (
                <div className="bg-green-50 border border-green-200 rounded-md p-3">
                  <div className="text-[11px] uppercase tracking-wide text-green-600 mb-1">ВНУТРІШНІЙ АТРИБУТ</div>
                  <div className="font-semibold text-sm">{mappingAttrName}</div>
                  <div className="text-xs text-green-500">ID: {mappingAttrId}</div>
                </div>
              ) : (
                <div className="bg-yellow-50 border border-yellow-300 rounded-md p-3 text-sm text-yellow-800">
                  <span className="font-medium">⚠ Увага:</span> Спочатку створіть маппінг атрибуту в розділі «Невідображені атрибути».
                </div>
              )
            )}

            {/* Value mode toggle */}
            {mappingModal.kind === 'values' && mappingAttrId && (
              <div>
                <div className="flex gap-4 mb-3">
                  <label className="flex items-center gap-2 cursor-pointer text-sm">
                    <input
                      type="radio"
                      name="valueMode"
                      checked={mappingValueMode === 'existing'}
                      onChange={() => setMappingValueMode('existing')}
                      className="accent-blue-600"
                    />
                    <span>Вибрати існуюче значення</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer text-sm">
                    <input
                      type="radio"
                      name="valueMode"
                      checked={mappingValueMode === 'create'}
                      onChange={() => { setMappingValueMode('create'); setMappingTarget(null); }}
                      className="accent-green-600"
                    />
                    <span>Створити нове значення</span>
                  </label>
                </div>

                {mappingValueMode === 'existing' && (
                  <>
                    <Input
                      value={mappingSearch}
                      onChange={(e) => { setMappingSearch(e.target.value); setMappingTarget(null); }}
                      placeholder="Пошук значення..."
                    />
                    {mappingSearch && (
                      <div className="max-h-48 overflow-y-auto border border-gray-200 rounded-md divide-y divide-gray-50 mt-1">
                        {mappingSearchLoading && (
                          <div className="px-3 py-2 text-xs text-gray-400">Завантаження...</div>
                        )}
                        {!mappingSearchLoading && mappingSearchResults.length === 0 && (
                          <div className="px-3 py-2 text-xs text-gray-400">Нічого не знайдено</div>
                        )}
                        {!mappingSearchLoading && mappingSearchResults.map((item) => (
                          <button
                            key={item.id}
                            onMouseDown={() => setMappingTarget(item)}
                            className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50 ${
                              mappingTarget?.id === item.id ? 'bg-blue-50 font-medium' : ''
                            }`}
                          >
                            <div>{item.name}</div>
                            <div className="text-[11px] text-gray-400">ID: {item.id}</div>
                          </button>
                        ))}
                      </div>
                    )}
                    {mappingTarget && (
                      <div className="mt-2 bg-green-50 border border-green-200 rounded-md p-3">
                        <div className="text-[11px] uppercase tracking-wide text-green-600 mb-1">ОБРАНО</div>
                        <div className="font-semibold text-sm">{mappingTarget.name}</div>
                        <div className="text-xs text-green-500">ID: {mappingTarget.id}</div>
                      </div>
                    )}
                  </>
                )}

                {mappingValueMode === 'create' && (
                  <div>
                    <Input
                      value={mappingNewValue}
                      onChange={(e) => setMappingNewValue(e.target.value)}
                      placeholder="Введіть нове значення"
                    />
                    <p className="text-xs text-gray-400 mt-1">Після збереження значення буде створено та одразу замаплено.</p>
                  </div>
                )}
              </div>
            )}

            {/* Search for categories / attributes */}
            {mappingModal.kind !== 'values' && (
              <div>
                <label className="block text-xs text-gray-500 mb-1">
                  {mappingModal.kind === 'categories' ? 'Внутрішня категорія' : 'Внутрішній атрибут'}
                </label>
                <Input
                  value={mappingSearch}
                  onChange={(e) => { setMappingSearch(e.target.value); setMappingTarget(null); }}
                  placeholder="Пошук..."
                />
                {mappingSearch && (
                  <div className="max-h-48 overflow-y-auto border border-gray-200 rounded-md divide-y divide-gray-50 mt-1">
                    {mappingSearchLoading && (
                      <div className="px-3 py-2 text-xs text-gray-400">Завантаження...</div>
                    )}
                    {!mappingSearchLoading && mappingSearchResults.length === 0 && (
                      <div className="px-3 py-2 text-xs text-gray-400">Нічого не знайдено</div>
                    )}
                    {!mappingSearchLoading && mappingSearchResults.map((item) => (
                      <button
                        key={item.id}
                        onMouseDown={() => setMappingTarget(item)}
                        className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50 ${
                          mappingTarget?.id === item.id ? 'bg-blue-50 font-medium' : ''
                        }`}
                      >
                        <div>{item.name}</div>
                        <div className="text-[11px] text-gray-400">ID: {item.id}</div>
                      </button>
                    ))}
                  </div>
                )}
                {mappingTarget && (
                  <div className="mt-2 bg-green-50 border border-green-200 rounded-md p-3">
                    <div className="text-[11px] uppercase tracking-wide text-green-600 mb-1">ОБРАНО</div>
                    <div className="font-semibold text-sm">{mappingTarget.name}</div>
                    <div className="text-xs text-green-500">ID: {mappingTarget.id}</div>
                  </div>
                )}
              </div>
            )}

            {/* Action buttons */}
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => setMappingModal(null)}>Скасувати</Button>
              <Button
                loading={mappingSaving}
                disabled={
                  mappingModal.kind === 'values' && mappingAttrId
                    ? mappingValueMode === 'create'
                      ? !mappingNewValue.trim()
                      : !mappingTarget
                    : !mappingTarget
                }
                onClick={handleMappingSave}
              >
                {mappingModal.kind === 'values' && mappingValueMode === 'create' ? 'Створити та замапити' : 'Зберегти маппінг'}
              </Button>
</div>
          </div>
        </Modal>
      )}
{/* Create modal */}
      {createModal && (
        <Modal
          open={true}
          title={`Створення ${
            createModal.kind === 'categories' ? 'категорії' :
            createModal.kind === 'attributes' ? 'атрибуту' : 'значення'
          }`}
          onClose={() => setCreateModal(null)}
        >
          <div className="space-y-4">
            {/* Supplier context */}
            <div className="bg-gray-50 border border-gray-200 rounded-md p-3">
              <div className="text-xs text-gray-500 mb-1">Постачальник</div>
              <div className="text-sm font-medium">{report?.supplier_code || '—'}</div>
            </div>

            {/* Source item */}
            <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
              <div className="text-[11px] uppercase tracking-wide text-blue-600 mb-1">
                {createModal.kind === 'categories' ? 'КАТЕГОРІЯ ПОСТАЧАЛЬНИКА' :
                 createModal.kind === 'attributes' ? 'АТРИБУТ ПОСТАЧАЛЬНИКА' :
                 'ЗНАЧЕННЯ ПОСТАЧАЛЬНИКА'}
              </div>
              <div className="font-semibold text-sm">{createModal.itemName}</div>
            </div>

            {/* For values: show resolved internal attribute */}
            {createModal.kind === 'values' && createModal.attrId && createModal.attrName && (
              <div className="bg-green-50 border border-green-200 rounded-md p-3">
                <div className="text-[11px] uppercase tracking-wide text-green-600 mb-1">ВНУТРІШНІЙ АТРИБУТ</div>
                <div className="font-semibold text-sm">{createModal.attrName}</div>
                <div className="text-xs text-green-500">ID: {createModal.attrId}</div>
              </div>
            )}

            {/* For values without resolved attribute */}
            {createModal.kind === 'values' && !createModal.attrId && (
              <div className="bg-yellow-50 border border-yellow-300 rounded-md p-3 text-sm text-yellow-800">
                <span className="font-medium">⚠ Увага:</span> Спочатку створіть маппінг атрибуту в розділі «Невідображені атрибути».
              </div>
            )}

            {/* Name input */}
            {(!(createModal.kind === 'values') || createModal.attrId) && (
              <div>
                <label className="block text-xs text-gray-500 mb-1">
                  {createModal.kind === 'categories' ? 'Назва нової категорії' :
                   createModal.kind === 'attributes' ? 'Назва нового атрибуту' :
                   'Нове значення'}
                </label>
                <Input
                  value={createName}
                  onChange={(e) => setCreateName(e.target.value)}
                  placeholder="Введіть назву"
                />
              </div>
            )}

            {/* Parent category selector */}
            {createModal.kind === 'categories' && (
              <div>
                <label className="block text-xs text-gray-500 mb-1">Батьківська категорія (необов'язково)</label>
                <Input
                  value={createParentSearch}
                  onChange={(e) => { setCreateParentSearch(e.target.value); setCreateParentId(null); setCreateParentName(''); }}
                  placeholder="Пошук батьківської категорії..."
                />
                {createParentSearch && createParentResults.length > 0 && (
                  <div className="max-h-36 overflow-y-auto border border-gray-200 rounded-md divide-y divide-gray-50 mt-1">
                    {createParentResults.map((item) => (
                      <button
                        key={item.id}
                        onMouseDown={() => { setCreateParentId(item.id); setCreateParentName(item.name); setCreateParentSearch(item.name); }}
                        className={`w-full text-left px-3 py-1.5 text-sm hover:bg-gray-50 ${
                          createParentId === item.id ? 'bg-blue-50 font-medium' : ''
                        }`}
                      >
                        {item.name}
                        <span className="text-[11px] text-gray-400 ml-2">ID: {item.id}</span>
                      </button>
                    ))}
                  </div>
                )}
                {createParentId && (
                  <div className="mt-1 text-xs text-green-600">Обрано: {createParentName}</div>
                )}
              </div>
            )}

            {/* Action buttons */}
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => setCreateModal(null)}>Скасувати</Button>
              <Button
                loading={createSaving}
                disabled={!createName.trim() || (createModal.kind === 'values' && !createModal.attrId)}
                onClick={handleCreate}
              >
                Створити
              </Button>
            </div>
          </div>
        </Modal>
      )}

    </div>
);
}
