'use client';

import { useEffect, useState, useCallback } from 'react';
import { api, qs } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import {
  PageHeader, Button, Input, Select, Table, Th, Td,
  Badge, LoadingState, ErrorState, Pagination, Modal, useToast,
} from '@/components/ui';

type Kind = 'categories' | 'attributes' | 'values';
const TABS: { key: string; label: string }[] = [
  { key: 'categories', label: 'Категорії' },
  { key: 'attributes', label: 'Атрибути' },
  { key: 'values', label: 'Значення атрибутів' },
  { key: 'coverage', label: 'Покриття' },
];

type ListResp<T> = { items: T[]; total: number; page: number; per_page: number };
type CoverageBlock = {
  total: number; accepted: number; proposed: number;
  excluded: number; unmapped: number;
  accepted_pct: number; proposed_pct: number; excluded_pct: number; unmapped_pct: number;
};
type Coverage = { categories: CoverageBlock; attributes: CoverageBlock; values: CoverageBlock };

type ExtCatOpt = { id: number; external_id: string; name: string; parent_external_id: string | null };
type ExtAttrOpt = { id: number; external_id: string; name: string; category_external_id: string; param_type: string | null; unit: string | null };
type ExtValOpt = { id: number; external_id: string; value: string; attribute_external_id: string };

const statusBadge: Record<string, { tone: 'gray' | 'green' | 'blue' | 'yellow'; label: string }> = {
  accepted: { tone: 'green', label: 'Прийнято' },
  proposed: { tone: 'blue', label: 'Запропоновано' },
  excluded: { tone: 'yellow', label: 'Виключено' },
  unmapped: { tone: 'gray', label: 'Не зіставлено' },
};

type FStatus = 'proposed' | 'accepted' | 'excluded';

/* ── Searchable taxonomy picker (reusable) ───────────────────────────── */

function RozetkaPicker<T extends { external_id: string; name?: string; value?: string }>({
  endpoint,
  label,
  extraParams = {} as Record<string, string | undefined>,
  displayName = (item) => (item as any).name || (item as any).value || '',
  value,
  onChange,
}: {
  endpoint: string;
  label: string;
  extraParams?: Record<string, string | undefined>;
  displayName?: (item: T) => string;
  value: string;
  onChange: (item: T | null) => void;
}) {
  const [query, setQuery] = useState('');
  const [opts, setOpts] = useState<T[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const fetch = useCallback((q: string) => {
    setLoading(true);
    api.get<ListResp<T>>(endpoint + qs({ ...extraParams, q: q || undefined, per_page: 50 }))
      .then((d) => setOpts(d.items))
      .catch(() => setOpts([]))
      .finally(() => setLoading(false));
  }, [endpoint, JSON.stringify(extraParams)]);

  useEffect(() => { fetch(query); }, [query, fetch]);

  return (
    <div className="relative">
      <label className="block text-xs text-gray-500 mb-1">{label}</label>
      <Input
        value={open ? query : (() => {
        const found = opts.find((o) => o.external_id === value);
        return found ? displayName(found) : (value || '');
      })()}
        onChange={(e) => { const v = e.target.value; setQuery(v); if (!open) setOpen(true); }}
        onFocus={() => { setOpen(true); fetch(query); }}
        onBlur={() => setTimeout(() => setOpen(false), 200)}
        placeholder={value ? '' : `Пошук ${label.toLowerCase()}...`}
        className="w-full"
      />
      {open && (
        <div className="absolute z-10 mt-1 w-full bg-white border border-gray-300 rounded-md shadow-lg overflow-y-auto text-sm max-h-60">
          {query && opts.length === 0 && !loading && (
            <div className="px-3 py-2 text-gray-400 text-xs">Нічого не знайдено</div>
          )}
          {loading && (
            <div className="px-3 py-2 text-gray-400 text-xs">Завантаження...</div>
          )}
          {opts.map((item) => (
            <button key={(item as any).id + '-' + (item as any).external_id}
              onMouseDown={(e) => { e.preventDefault(); onChange(item); setOpen(false); }}
              className="w-full text-left px-3 py-2 hover:bg-gray-100 border-b border-gray-50 last:border-0">
              <div className="font-medium text-sm">{displayName(item)}</div>
              <div className="text-[11px] text-gray-400">ID: {item.external_id}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
export default function RozetkaMappingPage() {
  const toast = useToast();

  const [tab, setTab] = useState('categories');
  const [rows, setRows] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [q, setQ] = useState('');
  const [appliedQ, setAppliedQ] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [extCatFilter, setExtCatFilter] = useState('');
  const [attrFilter, setAttrFilter] = useState('');
  const [scopeFilter, setScopeFilter] = useState('');

  // Value mode: 'all' (existing mappings) or 'unmapped' (candidates)
  const [valueMode, setValueMode] = useState<'all' | 'unmapped'>('all');
  // Scope selector for value mapping modal
  const [mappingScope, setMappingScope] = useState<'global' | 'category'>('global');
  const [scopeCategoryId, setScopeCategoryId] = useState('');
  const [scopeCategoryName, setScopeCategoryName] = useState('');
  // Categories for scope selector
  const [vmCategories, setVmCategories] = useState<ExtCatOpt[]>([]);
  const [vmCatLoaded, setVmCatLoaded] = useState(false);

  const [coverage, setCoverage] = useState<Coverage | null>(null);

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<any>(null);
  const [fStatus, setFStatus] = useState<FStatus>('proposed');

  // Rozetka entities chosen via pickers
  const [fExtCatId, setFExtCatId] = useState('');
  const [fExtCatName, setFExtCatName] = useState('');
  const [fExtAttrId, setFExtAttrId] = useState('');
  const [fExtAttrName, setFExtAttrName] = useState('');
  const [fExtValId, setFExtValId] = useState('');
  const [fExtValName, setFExtValName] = useState('');
  const [saving, setSaving] = useState(false);

  const pages = Math.max(1, Math.ceil(total / perPage));

  const load = useCallback(() => {
    if (tab === 'coverage') {
      api.get<Coverage>('/export/channels/rozetka/mapping-coverage')
        .then((d) => setCoverage(d))
        .catch((e: any) => toast.push('error', e.message || 'Помилка'));
      return;
    }
    setLoading(true);
    setError('');
    const params: Record<string, string | number | undefined> = { page, per_page: perPage };
    if (appliedQ) params.q = appliedQ;
    if (statusFilter) params.status = statusFilter;
    if (tab === 'attributes' || tab === 'values') {
      if (extCatFilter) params.external_category_id = extCatFilter;
      if (tab === 'values' && attrFilter) params.attribute_id = Number(attrFilter);
      if (tab === 'values' && valueMode === 'unmapped') params.status = 'unmapped';
      if (tab === 'attributes' && scopeFilter) params.scope = scopeFilter;
    }
    api.get<ListResp<any>>(`/export/channels/rozetka/mappings/${tab}` + qs(params))
      .then((d) => { setRows(d.items); setTotal(d.total); })
      .catch((e: any) => setError(e.message || 'Не вдалось завантажити'))
      .finally(() => setLoading(false));
  }, [tab, page, perPage, appliedQ, statusFilter, extCatFilter, attrFilter, scopeFilter, valueMode, toast]);

  useEffect(() => { load(); }, [load]);

  // Load categories for value mapping scope selector
  useEffect(() => {
    if (vmCatLoaded) return;
    api.get<{ items: ExtCatOpt[] }>('/export/channels/rozetka/pickers/external-categories?per_page=200')
      .then((d) => { setVmCategories(d.items || []); setVmCatLoaded(true); })
      .catch(() => setVmCatLoaded(true));
  }, [vmCatLoaded]);

  const handleDelete = async (id: number) => {
    if (!confirm('Видалити цей маппінг?')) return;
    try {
      await api.delete(`/export/channels/rozetka/mappings/${tab}/${id}`);
      load();
      toast.push('success', 'Маппінг видалено');
    } catch (e: any) { toast.push('error', e.message || 'Помилка'); }
  };

  const saveMapping = async (body: any) => {
    setSaving(true);
    try {
      await api.post(`/export/channels/rozetka/mappings/${tab}`, body);
      toast.push('success', 'Збережено');
      setModalOpen(false);
      load();
    } catch (e: any) { toast.push('error', e.message || 'Помилка'); }
    finally { setSaving(false); }
  };

  const updateMapping = async (id: number, body: any) => {
    setSaving(true);
    try {
      await api.put(`/export/channels/rozetka/mappings/${tab}/${id}`, body);
      toast.push('success', 'Оновлено');
      setModalOpen(false);
      load();
    } catch (e: any) { toast.push('error', e.message || 'Помилка'); }
    finally { setSaving(false); }
  };

  const openEdit = (r: any) => {
    setEditing(r);
    setFStatus(r.status === 'unmapped' ? 'proposed' : (r.status || 'proposed'));
    setFExtCatId(r.external_category_id || '');
    setFExtCatName(r.external_category_name || '');
    setFExtAttrId(r.external_attribute_id || '');
    setFExtAttrName(r.external_attribute_name || '');
    setFExtValId(r.external_id || '');
    setFExtValName(r.external_name || '');
    setModalOpen(true);
  };

  const openCreate = () => {
    setEditing(null);
    setFStatus('proposed');
    setFExtCatId('');
    setFExtCatName('');
    setFExtAttrId('');
    setFExtAttrName('');
    setFExtValId('');
    setFExtValName('');
    setModalOpen(true);
  };

  const handleModalSave = () => {
    const body: any = {
      status: fStatus,
      confidence: fStatus === 'accepted' ? 1.0 : 0.5,
      external_id: fExtValId || fExtAttrId || fExtCatId || undefined,
      external_name: fExtValName || fExtAttrName || fExtCatName || undefined,
      external_category_id: fExtCatId || undefined,
      external_attribute_id: fExtAttrId || undefined,
    };

    // Kind-specific field mapping
    if (tab === 'categories') {
      body.external_id = fExtCatId || undefined;
      body.external_name = fExtCatName || undefined;
      delete body.external_attribute_id;
    } else if (tab === 'attributes') {
      body.external_id = fExtAttrId || undefined;
      body.external_name = fExtAttrName || undefined;
      body.external_category_id = mappingScope === 'category' && scopeCategoryId ? scopeCategoryId : (fExtCatId || undefined);
    } else if (tab === 'values') {
      body.external_id = fExtValId || undefined;
      body.external_name = fExtValName || undefined;
      body.external_category_id = mappingScope === 'category' && scopeCategoryId ? scopeCategoryId : (fExtCatId || undefined);
    }

    if (editing && editing.mapping_id) { body.internal_id = editing.internal_id; updateMapping(editing.mapping_id, body); }
    else { body.internal_id = editing?.internal_id; saveMapping(body); }
  };

  return (
    <div>
      <PageHeader title="Маппінг Rozetka" actions={tab !== 'coverage' && (
        <Button onClick={openCreate}>+ Додати маппінг</Button>
      )} />

      <div className="flex gap-1 mb-4 border-b border-gray-200">
        {TABS.map((t) => (
          <button key={t.key} onClick={() => { setTab(t.key); setPage(1); }}
            className={`px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t.key ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'coverage' ? (
        <CoverageView coverage={coverage} />
      ) : (
        <>
          <div className="flex flex-wrap items-end gap-3 mb-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Пошук</label>
              <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Назва" className="w-48"
                onKeyDown={(e) => { if (e.key === 'Enter') { setAppliedQ(q); setPage(1); } }} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Статус</label>
              <Select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}>
                <option value="">Усі</option>
                <option value="accepted">Прийнято</option>
                <option value="proposed">Запропоновано</option>
                <option value="excluded">Виключено</option>
                <option value="unmapped">Не зіставлено</option>
              </Select>
            </div>
            {(tab === 'attributes' || tab === 'values') && (
              <div>
                <label className="block text-xs text-gray-500 mb-1">Rozetka категорія</label>
                <Input value={extCatFilter} onChange={(e) => { setExtCatFilter(e.target.value); setPage(1); }}
                  placeholder="ID категорії" className="w-48" />
              </div>
            )}
            {tab === 'values' && (
              <div>
                <label className="block text-xs text-gray-500 mb-1">Режим</label>
                <div className="flex gap-0">
                  <button
                    onClick={() => { setValueMode('all'); setPage(1); }}
                    className={`px-3 py-1.5 text-xs font-medium border rounded-l ${
                      valueMode === 'all'
                        ? 'bg-blue-600 text-white border-blue-600'
                        : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
                    }`}
                  >
                    Усі маппінги
                  </button>
                  <button
                    onClick={() => { setValueMode('unmapped'); setPage(1); }}
                    className={`px-3 py-1.5 text-xs font-medium border rounded-r ${
                      valueMode === 'unmapped'
                        ? 'bg-blue-600 text-white border-blue-600'
                        : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
                    }`}
                  >
                    Не зіставлені
                  </button>
                </div>
              </div>
            )}
            {tab === 'attributes' && (
              <div>
                <label className="block text-xs text-gray-500 mb-1">Scope</label>
                <Select value={scopeFilter} onChange={(e) => { setScopeFilter(e.target.value); setPage(1); }}>
                  <option value="">Усі</option>
                  <option value="global">Глобальні</option>
                  <option value="category">Категорійні</option>
                </Select>
              </div>
            )}
            <Button onClick={() => { setAppliedQ(q); setPage(1); }}>Застосувати</Button>
          </div>

          {loading ? <LoadingState /> : error ? <ErrorState message={error} onRetry={load} /> : (
            <>
              {tab === 'categories' && renderCategories(rows, openEdit)}
              {tab === 'attributes' && renderAttributes(rows, openEdit)}
              {tab === 'values' && renderValues(rows, openEdit, valueMode === 'unmapped')}
              <Pagination page={page} pages={pages} total={total} onPage={setPage}
                onGoToPage={(p) => setPage(Math.min(Math.max(p, 1), pages))}
                pageSize={perPage} onPageSizeChange={(n) => { setPerPage(n); setPage(1); }} />
            </>
          )}
        </>
      )}

      {/* Kind-specific modals */}
      {tab === 'categories' && (
        <CategoryMappingModal
          open={modalOpen}
          editing={editing}
          fStatus={fStatus}
          setFStatus={setFStatus}
          fExtCatId={fExtCatId}
          fExtCatName={fExtCatName}
          onChangeCategory={(item) => {
            setFExtCatId(item ? item.external_id : '');
            setFExtCatName(item ? item.name : '');
          }}
          onCancel={() => setModalOpen(false)}
          onSave={handleModalSave}
          saving={saving}
        />
      )}
      {tab === 'attributes' && (
        <AttributeMappingModal
          open={modalOpen}
          editing={editing}
          fStatus={fStatus}
          setFStatus={setFStatus}
          fExtCatId={fExtCatId}
          fExtCatName={fExtCatName}
          onChangeCategory={(item) => {
            setFExtCatId(item ? item.external_id : '');
            setFExtCatName(item ? item.name : '');
            // Clear attr when category changes
            setFExtAttrId('');
            setFExtAttrName('');
          }}
          fExtAttrId={fExtAttrId}
          fExtAttrName={fExtAttrName}
          onChangeAttribute={(item) => {
            setFExtAttrId(item ? item.external_id : '');
            setFExtAttrName(item ? item.name : '');
          }}
          onCancel={() => setModalOpen(false)}
          onSave={handleModalSave}
          saving={saving}
        />
      )}
      {tab === 'values' && (
        <ValueMappingModal
          open={modalOpen}
          editing={editing}
          fStatus={fStatus}
          setFStatus={setFStatus}
          fExtCatId={fExtCatId}
          fExtCatName={fExtCatName}
          onChangeCategory={(item) => {
            setFExtCatId(item ? item.external_id : '');
            setFExtCatName(item ? item.name : '');
            setFExtAttrId('');
            setFExtAttrName('');
            setFExtValId('');
            setFExtValName('');
          }}
          fExtAttrId={fExtAttrId}
          fExtAttrName={fExtAttrName}
          onChangeAttribute={(item) => {
            setFExtAttrId(item ? item.external_id : '');
            setFExtAttrName(item ? item.name : '');
            setFExtValId('');
            setFExtValName('');
          }}
          fExtValId={fExtValId}
          fExtValName={fExtValName}
          onChangeValue={(item) => {
            setFExtValId(item ? item.external_id : '');
            setFExtValName(item ? item.value : '');
          }}
          onCancel={() => setModalOpen(false)}
          onSave={handleModalSave}
          saving={saving}
          fScope={mappingScope}
          fScopeCategoryId={scopeCategoryId}
          fScopeCategoryName={scopeCategoryName}
          setScope={setMappingScope}
          setScopeCategory={(id, name) => { setScopeCategoryId(id); setScopeCategoryName(name); }}
          categories={vmCategories}
        />
      )}
    </div>
  );
}

/* ── Table renderers ───────────────────────────────────────── */

function renderCategories(rows: any[], openEdit: (r: any) => void) {
  return (
    <Table head={<><Th>Внутрішня категорія</Th><Th>→ Rozetka</Th><Th>Статус</Th><Th>Confidence</Th><Th>Джерело</Th><Th className="w-24">Дії</Th></>}>
      {rows.length === 0 ? (
        <tr><td colSpan={6} className="p-6 text-center text-gray-400">Немає відповідностей</td></tr>
      ) : rows.map((r: any) => {
        const sb = statusBadge[r.status] || { tone: 'gray' as const, label: r.status };
        return (
          <tr key={r.mapping_id || `cat-${r.internal_id}`} className="hover:bg-gray-50">
            <Td className="max-w-48 truncate font-medium"><span title={r.internal_name}>{r.internal_name}</span></Td>
            <Td className="max-w-48 truncate text-gray-600"><span title={r.external_name || ''}>{r.external_name || '—'}</span></Td>
            <Td><Badge tone={sb.tone}>{sb.label}</Badge></Td>
            <Td className="text-xs">{r.confidence != null ? `${Math.round(r.confidence * 100)}%` : '—'}</Td>
            <Td className="text-xs">{r.source === 'auto' ? 'Авто' : 'Вручну'}</Td>
            <Td>
              <button onClick={() => openEdit(r)} className="text-xs text-blue-600 hover:underline">Ред.</button>
            </Td>
          </tr>
        );
      })}
    </Table>
  );
}

function renderAttributes(rows: any[], openEdit: (r: any) => void) {
  return (
    <Table head={<><Th>Внутрішній атрибут</Th><Th>Rozetka категорія</Th><Th>→ Rozetka атрибут</Th><Th>Статус</Th><Th>Confidence</Th><Th className="w-24">Дії</Th></>}>
      {rows.length === 0 ? (
        <tr><td colSpan={6} className="p-6 text-center text-gray-400">Немає відповідностей</td></tr>
      ) : rows.map((r: any) => {
        const sb = statusBadge[r.status || 'unmapped'] || { tone: 'gray' as const, label: r.status || 'unmapped' };
        return (
          <tr key={r.mapping_id || `attr-${r.internal_id}`} className="hover:bg-gray-50">
            <Td className="max-w-48 truncate font-medium"><span title={r.internal_name}>{r.internal_name}</span></Td>
            <Td className="text-xs">{r.external_category_name || r.external_category_id || '—'}</Td>
            <Td className="max-w-40 truncate text-gray-600"><span title={r.external_name || ''}>{r.external_name || '—'}</span></Td>
            <Td><Badge tone={sb.tone}>{sb.label}</Badge></Td>
            <Td className="text-xs">{r.confidence != null ? `${Math.round(r.confidence * 100)}%` : '—'}</Td>
            <Td>
              <button onClick={() => openEdit(r)} className="text-xs text-blue-600 hover:underline">Ред.</button>
            </Td>
          </tr>
        );
      })}
    </Table>
  );
}

function renderValues(rows: any[], openEdit: (r: any) => void, unmappedMode = false) {
  const head = unmappedMode
    ? <><Th>Внутрішнє значення</Th><Th>Атрибут</Th><Th>Rozetka атрибут</Th><Th className="text-right">Товарів</Th><Th>Статус</Th><Th className="w-24">Дії</Th></>
    : <><Th>Внутрішнє значення</Th><Th>Атрибут</Th><Th>Rozetka атрибут</Th><Th>→ Rozetka значення</Th><Th>Статус</Th><Th className="w-24">Дії</Th></>;
  const colSpan = unmappedMode ? 6 : 6;
  return (
    <Table head={head}>
      {rows.length === 0 ? (
        <tr><td colSpan={colSpan} className="p-6 text-center text-gray-400">
          {unmappedMode ? 'Немає незіставлених значень. Усі знайдені значення вже мають відповідності Rozetka.' : 'Немає відповідностей'}
        </td></tr>
      ) : rows.map((r: any) => {
        const sb = statusBadge[r.status || 'unmapped'] || { tone: 'gray' as const, label: r.status || 'unmapped' };
        return (
          <tr key={r.mapping_id || `val-${r.internal_id}`} className="hover:bg-gray-50">
            <Td className="max-w-40 truncate font-medium"><span title={r.internal_name}>{r.internal_name}</span></Td>
            <Td className="text-xs">{r.attribute_name || '—'}</Td>
            <Td className="text-xs truncate">{r.external_attribute_name || '—'}</Td>
            {unmappedMode ? (
              <Td className="text-right text-xs">{r.product_count != null ? r.product_count.toLocaleString('uk-UA') : '—'}</Td>
            ) : (
              <Td className="max-w-40 truncate text-gray-600"><span title={r.external_name || ''}>{r.external_name || '—'}</span></Td>
            )}
            <Td><Badge tone={sb.tone}>{sb.label}</Badge></Td>
            <Td>
              <button onClick={() => openEdit(r)} className="text-xs text-blue-600 hover:underline">Ред.</button>
            </Td>
          </tr>
        );
      })}
    </Table>
  );
}

/* ── Coverage view ─────────────────────────────────────────── */

function CoverageView({ coverage }: { coverage: Coverage | null }) {
  if (!coverage) return <LoadingState label="Завантаження покриття..." />;
  const blocks: { label: string; key: keyof Coverage }[] = [
    { label: 'Категорії', key: 'categories' },
    { label: 'Атрибути', key: 'attributes' },
    { label: 'Значення', key: 'values' },
  ];
  return (
    <div>
      {blocks.map((b) => {
        const c = coverage[b.key];
        return (
          <div key={b.key} className="bg-white rounded-lg border border-gray-200 p-4 mb-4">
            <h3 className="font-medium mb-2">{b.label}</h3>
            <div className="grid grid-cols-4 gap-3 text-center">
              <div><div className="text-2xl font-bold text-green-700">{c.accepted}</div><div className="text-xs text-gray-500">Прийнято ({c.accepted_pct}%)</div></div>
              <div><div className="text-2xl font-bold text-blue-700">{c.proposed}</div><div className="text-xs text-gray-500">Запропоновано ({c.proposed_pct}%)</div></div>
              <div><div className="text-2xl font-bold text-yellow-700">{c.excluded}</div><div className="text-xs text-gray-500">Виключено ({c.excluded_pct}%)</div></div>
              <div><div className="text-2xl font-bold text-gray-700">{c.unmapped}</div><div className="text-xs text-gray-500">Не зіставлено ({c.unmapped_pct}%)</div></div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ── Selected entity card ──────────────────────────────────── */

function SelectedCard({ label, name, id, subtitle }: {
  label: string; name: string; id: string; subtitle?: string;
}) {
  if (!id) return null;
  return (
    <div className="bg-gray-50 border border-gray-200 rounded-md p-3">
      <div className="text-[11px] uppercase tracking-wide text-gray-500 mb-1">{label}</div>
      <div className="font-medium text-sm">{name}</div>
      <div className="text-xs text-gray-400">ID: {id}</div>
      {subtitle && <div className="text-xs text-gray-400">{subtitle}</div>}
    </div>
  );
}

/* ── Category Mapping Modal ────────────────────────────────── */

function CategoryMappingModal({
  open, editing,
  fStatus, setFStatus,
  fExtCatId, fExtCatName, onChangeCategory,
  onCancel, onSave, saving,
}: {
  open: boolean; editing: any | null;
  fStatus: FStatus; setFStatus: (v: FStatus) => void;
  fExtCatId: string; fExtCatName: string;
  onChangeCategory: (item: ExtCatOpt | null) => void;
  onCancel: () => void; onSave: () => void; saving: boolean;
}) {
  return (
    <Modal open={open} title={editing ? 'Редагування маппінгу категорії' : 'Створення маппінгу категорії'} onClose={onCancel} wide>
      <div className="space-y-4">
        {/* Internal entity */}
        <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
          <div className="text-[11px] uppercase tracking-wide text-blue-600 mb-1">ВНУТРІШНЯ КАТЕГОРІЯ</div>
          <div className="font-semibold text-sm">{editing?.internal_name || '—'}</div>
          <div className="text-xs text-blue-500">ID: {editing?.internal_id ?? '—'}</div>
        </div>

        <div className="flex items-center justify-center text-gray-400 text-lg">↓</div>

        {/* Rozetka category picker */}
        <div>
          <RozetkaPicker<ExtCatOpt>
            endpoint="/export/channels/rozetka/pickers/external-categories"
            label="Категорія Rozetka"
            value={fExtCatId}
            onChange={(item) => onChangeCategory(item as ExtCatOpt | null)}
            displayName={(item) => item.name}
          />
        </div>

        {/* Selected entity card */}
        <SelectedCard label="ОБРАНА КАТЕГОРІЯ ROZETKA" name={fExtCatName} id={fExtCatId} />

        {/* Status */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">Статус *</label>
          <Select value={fStatus} onChange={(e) => setFStatus(e.target.value as FStatus)}>
            <option value="proposed">Запропоновано</option>
            <option value="accepted">Прийнято</option>
            <option value="excluded">Виключено</option>
          </Select>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onCancel}>Скасувати</Button>
          <Button loading={saving} onClick={onSave}>
            {editing ? 'Зберегти зміни' : 'Створити'}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

/* ── Attribute Mapping Modal ───────────────────────────────── */

function AttributeMappingModal({
  open, editing,
  fStatus, setFStatus,
  fExtCatId, fExtCatName, onChangeCategory,
  fExtAttrId, fExtAttrName, onChangeAttribute,
  onCancel, onSave, saving,
}: {
  open: boolean; editing: any | null;
  fStatus: FStatus; setFStatus: (v: FStatus) => void;
  fExtCatId: string; fExtCatName: string;
  onChangeCategory: (item: ExtCatOpt | null) => void;
  fExtAttrId: string; fExtAttrName: string;
  onChangeAttribute: (item: ExtAttrOpt | null) => void;
  onCancel: () => void; onSave: () => void; saving: boolean;
}) {
  const extAttrExtra = fExtCatId ? { category_external_id: fExtCatId } : {};

  return (
    <Modal open={open} title={editing ? 'Редагування маппінгу атрибуту' : 'Створення маппінгу атрибуту'} onClose={onCancel} wide>
      <div className="space-y-4">
        {/* Internal entity */}
        <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
          <div className="text-[11px] uppercase tracking-wide text-blue-600 mb-1">ВНУТРІШНІЙ АТРИБУТ</div>
          <div className="font-semibold text-sm">{editing?.internal_name || '—'}</div>
          <div className="text-xs text-blue-500">ID: {editing?.internal_id ?? '—'}</div>
        </div>

        <div className="flex items-center justify-center text-gray-400 text-lg">↓</div>

        {/* Rozetka category context */}
        <RozetkaPicker<ExtCatOpt>
          endpoint="/export/channels/rozetka/pickers/external-categories"
          label="Контекст — категорія Rozetka (необов'язково для глобальних атрибутів)"
          value={fExtCatId}
          onChange={(item) => onChangeCategory(item as ExtCatOpt | null)}
          displayName={(item) => item.name}
        />
        <SelectedCard label="КАТЕГОРІЯ ROZETKA" name={fExtCatName} id={fExtCatId} />

        {/* Rozetka attribute — filtered by category */}
        <RozetkaPicker<ExtAttrOpt>
          endpoint="/export/channels/rozetka/pickers/external-attributes"
          label="Атрибут Rozetka"
          extraParams={extAttrExtra}
          value={fExtAttrId}
          onChange={(item) => onChangeAttribute(item as ExtAttrOpt | null)}
          displayName={(item) => {
            const extra = item.param_type ? ` (${item.param_type})` : '';
            return `${item.name}${extra}`;
          }}
        />
        <SelectedCard
          label="АТРИБУТ ROZETKA"
          name={fExtAttrName}
          id={fExtAttrId}
          subtitle={editing?.external_category_name ? `Категорія: ${editing.external_category_name}` : undefined}
        />

        {/* Status */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">Статус *</label>
          <Select value={fStatus} onChange={(e) => setFStatus(e.target.value as FStatus)}>
            <option value="proposed">Запропоновано</option>
            <option value="accepted">Прийнято</option>
            <option value="excluded">Виключено</option>
          </Select>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onCancel}>Скасувати</Button>
          <Button loading={saving} onClick={onSave}>
            {editing ? 'Зберегти зміни' : 'Створити'}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

/* ── Value Mapping Modal ───────────────────────────────────── */

function ValueMappingModal({
  open, editing,
  fStatus, setFStatus,
  fExtCatId, fExtCatName, onChangeCategory,
  fExtAttrId, fExtAttrName, onChangeAttribute,
  fExtValId, fExtValName, onChangeValue,
  onCancel, onSave, saving,
}: {
  open: boolean; editing: any | null;
  fStatus: FStatus; setFStatus: (v: FStatus) => void;
  fExtCatId: string; fExtCatName: string;
  onChangeCategory: (item: ExtCatOpt | null) => void;
  fExtAttrId: string; fExtAttrName: string;
  onChangeAttribute: (item: ExtAttrOpt | null) => void;
  fExtValId: string; fExtValName: string;
  onChangeValue: (item: ExtValOpt | null) => void;
  onCancel: () => void; onSave: () => void; saving: boolean;
  fScope?: 'global' | 'category'; fScopeCategoryId?: string; fScopeCategoryName?: string;
  setScope?: (v: 'global' | 'category') => void;
  setScopeCategory?: (id: string, name: string) => void;
  categories?: ExtCatOpt[];
}) {
  const extAttrExtra = fExtCatId ? { category_external_id: fExtCatId } : {};
  const extValExtra = {
    ...(fExtCatId ? { category_external_id: fExtCatId } : {}),
    ...(fExtAttrId ? { attribute_external_id: fExtAttrId } : {}),
  };

  return (
    <Modal open={open} title={editing ? 'Редагування маппінгу значення' : 'Створення маппінгу значення'} onClose={onCancel} wide>
      <div className="space-y-4">
        {/* Internal entities */}
        <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
          <div className="text-[11px] uppercase tracking-wide text-blue-600 mb-1">ВНУТРІШНІЙ АТРИБУТ</div>
          <div className="font-semibold text-sm">{editing?.attribute_name || '—'}</div>
          <div className="text-xs text-blue-500">ID: {editing?.attribute_id ?? '—'}</div>
        </div>
        <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
          <div className="text-[11px] uppercase tracking-wide text-blue-600 mb-1">ВНУТРІШНЄ ЗНАЧЕННЯ</div>
          <div className="font-semibold text-sm">{editing?.internal_name || '—'}</div>
          <div className="text-xs text-blue-500">ID: {editing?.internal_id ?? '—'}</div>
        </div>

        <div className="flex items-center justify-center text-gray-400 text-lg">↓</div>

        {/* Rozetka category */}
        <RozetkaPicker<ExtCatOpt>
          endpoint="/export/channels/rozetka/pickers/external-categories"
          label="Категорія Rozetka"
          value={fExtCatId}
          onChange={(item) => onChangeCategory(item as ExtCatOpt | null)}
          displayName={(item) => item.name}
        />
        <SelectedCard label="КАТЕГОРІЯ ROZETKA" name={fExtCatName} id={fExtCatId} />

        {/* Rozetka attribute — filtered by category */}
        <RozetkaPicker<ExtAttrOpt>
          endpoint="/export/channels/rozetka/pickers/external-attributes"
          label="Атрибут Rozetka"
          extraParams={extAttrExtra}
          value={fExtAttrId}
          onChange={(item) => onChangeAttribute(item as ExtAttrOpt | null)}
          displayName={(item) => {
            const extra = item.param_type ? ` (${item.param_type})` : '';
            return `${item.name}${extra}`;
          }}
        />
        <SelectedCard label="АТРИБУТ ROZETKA" name={fExtAttrName} id={fExtAttrId} />

        {/* Rozetka value — filtered by category + attribute */}
        <RozetkaPicker<ExtValOpt>
          endpoint="/export/channels/rozetka/pickers/external-values"
          label="Значення Rozetka"
          extraParams={extValExtra}
          value={fExtValId}
          onChange={(item) => onChangeValue(item as ExtValOpt | null)}
          displayName={(item) => item.value}
        />
        <SelectedCard
          label="ЗНАЧЕННЯ ROZETKA"
          name={fExtValName}
          id={fExtValId}
          subtitle={fExtAttrName ? `Атрибут: ${fExtAttrName}` : undefined}
        />

        {/* Status */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">Статус *</label>
          <Select value={fStatus} onChange={(e) => setFStatus(e.target.value as FStatus)}>
            <option value="proposed">Запропоновано</option>
            <option value="accepted">Прийнято</option>
            <option value="excluded">Виключено</option>
          </Select>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onCancel}>Скасувати</Button>
          <Button loading={saving} onClick={onSave}>
            {editing ? 'Зберегти зміни' : 'Створити'}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
