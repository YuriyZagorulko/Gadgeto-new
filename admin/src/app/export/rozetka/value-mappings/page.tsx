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
  const [saving, setSaving] = useState(false);

  const pages = useMemo(() => Math.max(1, Math.ceil(total / perPage)), [total, perPage]);

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
      const result = await api.post<MappingResult>('/export/channels/rozetka/mappings/values', {
        internal_id: reviewItem.internal_value_id,
        external_id: selectedExtValId,
        external_name: selectedExtValName,
        external_category_id: null,
        status: 'accepted',
      });
      toast.push('success', 'Mappping created!');
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
      <PageHeader title="Mapppihr 3haveHb Rozetka" />
      <p className="text-sm text-gray-500 mb-4">
        3haveHHa aTpM6yTiB ToBapIB, 3Ki ue He 3icTaBneHi 3 BignoBiAHuMu 3haveHHamu Rozetka.
        CopTyBaHHa 3a KimbKicTio ToBapIB (HaMBnMB0BiUi nepuUuMu).
      </p>

      <div className="flex flex-wrap items-end gap-3 mb-4">
        <div>
          <label className="block text-xs text-gray-500 mb-1">PouyK</label>
          <Input value={q} onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { setAppliedQ(q); setPage(1); } }}
            placeholder="aTpM6yT / 3Ha4eHHa" className="w-48" />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">KaTeropia Rozetka</label>
          <Select value={catFilter} onChange={(e) => { setCatFilter(e.target.value); setPage(1); }}>
            <option value="">Bci kaTeropii</option>
            {categories.map((c) => (
              <option key={c.external_id} value={c.external_id}>{c.name}</option>
            ))}
          </Select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Cratyc</label>
          <Select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}>
            <option value="unmapped">He 3icTaBneHo</option>
            <option value="mapped">3icTaBneHo</option>
            <option value="all">Bci</option>
          </Select>
        </div>
        <div className="text-sm text-gray-600 pt-4">
          <strong>{total}</strong> KaHAuAaTiB
        </div>
        <div className="pt-4">
          <Button variant="primary" onClick={load}>OhoBumu</Button>
        </div>
      </div>

      {loading ? <LoadingState label="3aBaHTaxeHHa..." /> :
       error ? <ErrorState message={error} onRetry={load} /> : (
        <div className="overflow-x-auto">
          <Table head={<>
            <Th>ATpH6yT</Th>
            <Th>3HayeHH</Th>
            <Th className="text-right">TOBapIB</Th>
            <Th>KaTeropia Rozetka</Th>
            <Th>ATpH6yT Rozetka</Th>
            <Th>3HayeHH Rozetka</Th>
            <Th>Cratyc</Th>
            <Th></Th>
          </>}>
            {rows.length === 0 ? (
              <tr><td colSpan={8} className="p-6 text-center text-gray-400">HeMaE KaHAuAaTiB</td></tr>
            ) : rows.map((r) => (
              <tr key={r.internal_value_id} className="hover:bg-gray-50">
                <Td className="font-medium">{r.attribute_name}</Td>
                <Td className="max-w-xs truncate font-mono text-xs" title={r.internal_value}>{r.internal_value}</Td>
                <Td className="text-right font-mono">{r.product_count.toLocaleString('uk-UA')}</Td>
                <Td className="text-xs">{r.external_category_name || <span className="text-gray-400">—</span>}</Td>
                <Td className="text-xs">{r.external_attribute_name || <span className="text-gray-400">—</span>}</Td>
                <Td className="text-xs">{r.external_value_name || <span className="text-gray-400">—</span>}</Td>
                <Td><Badge tone={r.mapped ? 'green' : 'red'}>{r.mapped ? '3icTaBneHo' : 'He 3icTaBneHo'}</Badge></Td>
                <Td>
                  {!r.mapped && r.external_attribute_id ? (
                    <Button size="sm" variant="secondary" onClick={() => openReview(r)}>3icTaBumu</Button>
                  ) : (
                    <span className="text-xs text-gray-400">{r.mapped ? '—' : 'HeMaE aTpH6yTa'}</span>
                  )}
                </Td>
              </tr>
            ))}
          </Table>
        </div>
      )}

      <Pagination page={page} pages={pages} total={total} onPage={setPage}
        onGoToPage={(p) => setPage(Math.min(Math.max(p, 1), pages))}
        pageSize={perPage} onPageSizeChange={(n) => { setPerPage(n); setPage(1); }} />

      <Modal open={reviewItem !== null} onClose={() => setReviewItem(null)} title="OrnaA 3icTaBneHHa 3HayeHHa">
        {reviewItem && (
          <div className="space-y-4">
            <div className="bg-gray-50 rounded p-3 text-sm space-y-1">
              <div><span className="text-gray-500">ATpH6yT:</span> <strong>{reviewItem.attribute_name}</strong></div>
              <div><span className="text-gray-500">3HayeHHa:</span> <strong>{reviewItem.internal_value}</strong></div>
              <div><span className="text-gray-500">TOBapIB:</span> <strong>{reviewItem.product_count.toLocaleString('uk-UA')}</strong></div>
            </div>

            <div className="bg-gray-50 rounded p-3 text-sm">
              <div className="text-gray-500 mb-1">ATpH6yT Rozetka:</div>
              <div className="font-medium">{reviewItem.external_attribute_name || '—'}</div>
              {reviewItem.external_attribute_id && (
                <div className="text-xs text-gray-400">ID: {reviewItem.external_attribute_id}</div>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">3HayeHHa Rozetka</label>
              <Input value={extValSearch} onChange={(e) => setExtValSearch(e.target.value)}
                placeholder="PouyK 3HaveHb Rozetka..." className="w-full mb-2" />
              {extValLoading ? (
                <LoadingState label="3aBaHTaxeHHa 3Ha4eHb..." />
              ) : filteredExtValues.length === 0 ? (
                <p className="text-sm text-gray-400">HeMaE 3Ha4eHb Rozetka AAR uboro aTpH6yTa</p>
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
                <div className="font-medium text-blue-800">BupaHo 3HayeHHa Rozetka</div>
                <div className="text-blue-600">{selectedExtValName}</div>
                <div className="text-xs text-blue-400">ID: {selectedExtValId}</div>
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2 border-t border-gray-100">
              <Button variant="ghost" onClick={() => setReviewItem(null)}>3akpuTu</Button>
              <Button variant="primary" onClick={saveMapping}
                disabled={!selectedExtValId || saving}>
                {saving ? '3gepexeHHa...' : '3geperu Mannir'}
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
