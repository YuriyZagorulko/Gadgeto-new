'use client';

import { useEffect, useState, useMemo, useCallback } from 'react';
import { api, qs } from '@/lib/api';
import {
  PageHeader, Button, Input, Select, Table, Th, Td,
  Badge, LoadingState, ErrorState, Pagination, Modal, useToast,
} from '@/components/ui';

type CandidateRow = {
  attribute_id: number;
  attribute_name: string;
  internal_value_id: number;
  internal_value: string;
  product_count: number;
  external_attribute_id: string | null;
  external_attribute_name: string | null;
  mapped: boolean;
  external_value_id: string | null;
  external_value_name: string | null;
  external_category_id: string | null;
  external_category_name: string | null;
};
type CandidatesResp = { items: CandidateRow[]; total: number; page: number; per_page: number };

type ExtValue = { id: number; external_id: string; value: string; attribute_external_id: string };
type ExtValueResp = { items: ExtValue[]; total: number };
type ExtCat = { id: number; external_id: string; name: string };
type ExtCatResp = { items: ExtCat[]; total: number };

type MappingResult = { ok: boolean; id: number; updated?: boolean };

export default function RozetkaValueMappingsPage() {
  const toast = useToast();
  const [rows, setRows] = useState<CandidateRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(25);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [q, setQ] = useState('');
  const [appliedQ, setAppliedQ] = useState('');
  const [statusFilter, setStatusFilter] = useState('unmapped');
  const [catFilter, setCatFilter] = useState('');
  const [categories, setCategories] = useState<ExtCat[]>([]);
  const [catLoaded, setCatLoaded] = useState(false);

  const [reviewItem, setReviewItem] = useState<CandidateRow | null>(null);
  const [extValues, setExtValues] = useState<ExtValue[]>([]);
  const [extValSearch, setExtValSearch] = useState('');
  const [extValLoading, setExtValLoading] = useState(false);
  const [selectedExtValId, setSelectedExtValId] = useState<string | null>(null);
  const [selectedExtValName, setSelectedExtValName] = useState<string | null>(null);
  const [mappingScope, setMappingScope] = useState<'category' | 'global'>('global');
  const [scopeCategoryId, setScopeCategoryId] = useState('');
  const [scopeCategoryName, setScopeCategoryName] = useState('');
  const [saving, setSaving] = useState(false);

  const pages = useMemo(() => Math.max(1, Math.ceil(total / perPage)), [total, perPage]);

  // Find the selected category name
  const selectedCatName = useMemo(() => {
    const c = categories.find((c) => c.external_id === catFilter);
    return c ? c.name : '';
  }, [categories, catFilter]);

  // Load categories
  useEffect(() => {
    if (catLoaded) return;
    api.get<{ items: { id: number; external_id: string; name: string }[] }>(
      '/export/channels/rozetka/pickers/external-categories?per_page=200')
      .then((d) => { setCategories(d.items || []); setCatLoaded(true); })
      .catch(() => setCatLoaded(true));
  }, [catLoaded]);

  const filterParams = useMemo(() => {
    const p: Record<string, string | number | undefined> = { page, per_page: perPage };
    if (appliedQ) p.q = appliedQ;
    if (statusFilter !== 'all') p.status = statusFilter;
    if (catFilter) p.external_category_id = catFilter;
    return p;
  }, [page, perPage, appliedQ, statusFilter, catFilter]);

  const load = useCallback(() => {
    setLoading(true); setError('');
    api.get<CandidatesResp>('/export/channels/rozetka/value-mappings/candidates' + qs(filterParams))
      .then((d) => { setRows(d.items); setTotal(d.total); })
      .catch((e) => setError(e.message || 'Failed to load candidates'))
      .finally(() => setLoading(false));
  }, [filterParams]);

  useEffect(() => { load(); }, [load]);

  const openReview = async (item: CandidateRow) => {
    setReviewItem(item);
    setExtValSearch('');
    setSelectedExtValId(null);
    setSelectedExtValName(null);
    setExtValues([]);
    // Reset scope from previous review
    setMappingScope('global');
    setScopeCategoryId('');
    setScopeCategoryName('');
    // Pre-fill scope from category filter if active
    if (catFilter) {
      setMappingScope('category');
      setScopeCategoryId(catFilter);
      setScopeCategoryName(selectedCatName);
    }
    if (item.external_attribute_id) {
      setExtValLoading(true);
      try {
        const params = 'attribute_external_id=' + item.external_attribute_id + '&per_page=50';
        const data = await api.get<ExtValueResp>(
          '/export/channels/rozetka/pickers/external-values?' + params);
        setExtValues(data.items || []);
      } catch (e: any) {
        toast.push('error', 'Failed to load Rozetka values');
      } finally {
        setExtValLoading(false);
      }
    }
  };

  const filteredExtValues = useMemo(() => {
    if (!extValSearch) return extValues;
    const s = extValSearch.toLowerCase();
    return extValues.filter((v) => v.value.toLowerCase().includes(s) || v.external_id.toLowerCase().includes(s));
  }, [extValues, extValSearch]);

  const selectExtValue = (id: string, name: string) => {
    setSelectedExtValId(id);
    setSelectedExtValName(name);
  };

  const saveMapping = async () => {
    if (!reviewItem || !selectedExtValId) return;
    setSaving(true);
    try {
      const extCatId = mappingScope === 'category' ? scopeCategoryId : null;
      await api.post<MappingResult>('/export/channels/rozetka/mappings/values', {
        internal_id: reviewItem.internal_value_id,
        external_id: selectedExtValId,
        external_name: selectedExtValName,
        external_category_id: extCatId,
        status: 'accepted',
      });
      const scopeLabel = extCatId ? ` (категорія: ${scopeCategoryName || extCatId})` : ' (глобально)';
      toast.push('success', `Маппінг створено${scopeLabel}`);
      setReviewItem(null);
      load();
    } catch (e: any) {
      toast.push('error', e.message || 'Failed to save mapping');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <PageHeader title="Маппінг значень Rozetka" />
      <p className="text-sm text-gray-500 mb-4">
        Значення атрибутів товарів, які ще не зіставлені з відповідними значеннями Rozetka.
        Сортування за кількістю товарів (найбільші першими).
      </p>

      <div className="flex flex-wrap items-end gap-3 mb-4">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Пошук</label>
          <Input value={q} onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { setAppliedQ(q); setPage(1); } }}
            placeholder="Атрибут / Значення" className="w-48" />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Категорія Rozetka</label>
          <Select value={catFilter} onChange={(e) => { setCatFilter(e.target.value); setPage(1); }}>
            <option value="">Всі категорії</option>
            {categories.map((c) => (
              <option key={c.external_id} value={c.external_id}>{c.name}</option>
            ))}
          </Select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Статус</label>
          <Select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}>
            <option value="unmapped">Не зіставлено</option>
            <option value="mapped">Зіставлено</option>
            <option value="all">Всі</option>
          </Select>
        </div>
        <div className="text-sm text-gray-600 pt-4">
          {total > 0 ? `Знайдено ${total.toLocaleString('uk-UA')} значень` : ''}
        </div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="text-xs text-gray-500 uppercase bg-gray-50">
            <tr>
              <Th>Атрибут</Th>
              <Th>Значення</Th>
              <Th className="text-right">Товарів</Th>
              <Th>Атрибут Rozetka</Th>
              <Th>Статус</Th>
              <Th></Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {rows.length === 0 ? (
              <tr><td colSpan={6} className="p-4 text-center text-gray-400">Немає значень</td></tr>
            ) : rows.map((r, i) => (
              <tr key={r.internal_value_id + '-' + i} className="hover:bg-gray-50">
                <Td>{r.attribute_name}</Td>
                <Td><span className="font-mono">{r.internal_value}</span></Td>
                <Td className="text-right">{r.product_count.toLocaleString('uk-UA')}</Td>
                <Td className="text-xs">{r.external_attribute_name || '—'}</Td>
                <Td>
                  {r.mapped ? <Badge tone="green">Зіставлено</Badge> : <Badge tone="gray">Не зіставлено</Badge>}
                </Td>
                <Td>
                  {!r.mapped && r.external_attribute_id && (
                    <Button variant="ghost" size="sm" onClick={() => openReview(r)}>Зіставити</Button>
                  )}
                </Td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="p-4 border-t border-gray-100">
          <Pagination
            page={page} pages={pages} total={total}
            onPage={setPage}
            onGoToPage={(p) => setPage(Math.min(Math.max(p, 1), pages))}
            pageSize={perPage} onPageSizeChange={(n) => { setPerPage(n); setPage(1); }} />
        </div>
      </div>

      {/* ── Review / Create Modal ── */}
      <Modal open={reviewItem !== null} onClose={() => setReviewItem(null)} title="Огляд зіставлення значення">
        {reviewItem && (
          <div className="space-y-4">
            <div className="bg-gray-50 rounded p-3 text-sm space-y-1">
              <div><span className="text-gray-500">Атрибут:</span> <strong>{reviewItem.attribute_name}</strong></div>
              <div><span className="text-gray-500">Значення:</span> <strong>{reviewItem.internal_value}</strong></div>
              <div><span className="text-gray-500">Товарів:</span> <strong>{reviewItem.product_count.toLocaleString('uk-UA')}</strong></div>
            </div>

            <div className="bg-gray-50 rounded p-3 text-sm">
              <div className="text-gray-500 mb-1">Атрибут Rozetka:</div>
              <div className="font-medium">{reviewItem.external_attribute_name || '—'}</div>
              {reviewItem.external_attribute_id && (
                <div className="text-xs text-gray-400">ID: {reviewItem.external_attribute_id}</div>
              )}
            </div>

            {/* Scope selector */}
            <div className="bg-gray-50 rounded p-3">
              <div className="text-sm font-medium mb-2">Область застосування</div>
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="radio" name="scope" value="global"
                    checked={mappingScope === 'global'}
                    onChange={() => setMappingScope('global')}
                    className="accent-blue-600" />
                  <span>Глобальне значення (для всіх категорій Rozetka)</span>
                </label>
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="radio" name="scope" value="category"
                    checked={mappingScope === 'category'}
                    onChange={() => setMappingScope('category')}
                    className="accent-blue-600" />
                  <span>Лише для категорії Rozetka:</span>
                </label>
                {mappingScope === 'category' && (
                  <div className="ml-6">
                    <Select
                      value={scopeCategoryId}
                      onChange={(e) => {
                        setScopeCategoryId(e.target.value);
                        const c = categories.find((c) => c.external_id === e.target.value);
                        setScopeCategoryName(c ? c.name : '');
                      }}
                      className="w-64"
                    >
                      <option value="">Виберіть категорію...</option>
                      {categories.map((c) => (
                        <option key={c.external_id} value={c.external_id}>{c.name}</option>
                      ))}
                    </Select>
                  </div>
                )}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Значення Rozetka</label>
              <Input value={extValSearch} onChange={(e) => setExtValSearch(e.target.value)}
                placeholder="Пошук значень Rozetka..." className="w-full mb-2" />
              {extValLoading ? (
                <LoadingState label="Завантаження значень..." />
              ) : filteredExtValues.length === 0 ? (
                <p className="text-sm text-gray-400">Немає значень Rozetka для цього атрибута</p>
              ) : (
                <div className="max-h-48 overflow-y-auto border border-gray-200 rounded text-sm">
                  {filteredExtValues.map((v) => (
                    <div key={v.id}
                      className={"px-3 py-1.5 cursor-pointer hover:bg-blue-50 flex items-center gap-2 " +
                        (selectedExtValId === v.external_id ? 'bg-blue-100 font-medium' : '')}
                      onClick={() => selectExtValue(v.external_id, v.value)}>
                      <input type="radio" checked={selectedExtValId === v.external_id}
                        onChange={() => selectExtValue(v.external_id, v.value)}
                        className="accent-blue-600" />
                      <span>{v.value}</span>
                      <span className="text-xs text-gray-400 ml-auto">ID: {v.external_id}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {selectedExtValId && (
              <div className="bg-blue-50 rounded p-3 text-sm">
                <div className="font-medium text-blue-800">Вибрано значення Rozetka</div>
                <div className="text-blue-600">{selectedExtValName}</div>
                <div className="text-xs text-blue-400">ID: {selectedExtValId}</div>
                {mappingScope === 'category' && scopeCategoryName && (
                  <div className="text-xs text-blue-400 mt-1">
                    Область: категорія «{scopeCategoryName}»
                  </div>
                )}
                {mappingScope === 'global' && (
                  <div className="text-xs text-blue-400 mt-1">
                    Область: глобально (всі категорії)
                  </div>
                )}
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2 border-t border-gray-100">
              <Button variant="ghost" onClick={() => setReviewItem(null)}>Закрити</Button>
              <Button variant="primary" onClick={saveMapping}
                disabled={!selectedExtValId || saving || (mappingScope === 'category' && !scopeCategoryId)}>
                {saving ? 'Збереження...' : 'Зберегти Маппінг'}
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
