'use client';

import { useEffect, useState, useCallback } from 'react';
import { api, qs } from '@/lib/api';
import {
  PageHeader, Button, Input, Select, Table, Th, Td, Badge,
  LoadingState, ErrorState, EmptyState, Pagination, Modal,
  ConfirmDialog, useToast, Spinner,
} from '@/components/ui';

type Summary = {
  unassigned_mappings: number; ambiguous_global: number;
  orphans_total: number; inconsistent_targets: number;
};

type InconsistentItem = {
  id: number; supplier_item_name: string;
  current_value: string; current_av_id: number;
  current_attr_id: number; current_attr_name: string;
  target_attr_id: number; target_attr_name: string;
  product_usage: number; matching_exists: boolean;
};

type OrphanItem = {
  id: number; holder_name: string | null;
  supplier_item_name: string; catalog_name: string | null;
  parent_mapping_id: number | null;
  parent_active: boolean | null;
  reason: string; product_usage: number;
};

type UnassignedGroup = {
  attr_id: number; attr_name: string;
  mapping_count: number; supplier_names: string;
  product_usage: number;
  mappings: { id: number; supplier_attr: string; is_active: boolean }[];
  candidates: { id: number; name: string; cat_count: number }[];
};

type AmbiguousItem = {
  id: number; supplier_attr: string;
  internal_attr: string; cat_count: number;
  product_usage: number;
};

export default function MappingReview() {
  const toast = useToast();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('inconsistent');
  const [saving, setSaving] = useState(false);

  // Inconsistent state
  const [incItems, setIncItems] = useState<InconsistentItem[]>([]);
  const [incTotal, setIncTotal] = useState(0);
  const [incLoading, setIncLoading] = useState(false);
  const [incPage, setIncPage] = useState(1);

  // Orphan state
  const [orphanItems, setOrphanItems] = useState<OrphanItem[]>([]);
  const [orphanTotal, setOrphanTotal] = useState(0);
  const [orphanLoading, setOrphanLoading] = useState(false);
  const [orphanPage, setOrphanPage] = useState(1);

  // Unassigned state
  const [unassignedGroups, setUnassignedGroups] = useState<UnassignedGroup[]>([]);
  const [unassignedLoading, setUnassignedLoading] = useState(false);

  // Ambiguous state
  const [ambigItems, setAmbigItems] = useState<AmbiguousItem[]>([]);
  const [ambigTotal, setAmbigTotal] = useState(0);
  const [ambigLoading, setAmbigLoading] = useState(false);
  const [ambigPage, setAmbigPage] = useState(1);

  // All attrs for selectors
  const [allAttrs, setAllAttrs] = useState<{ id: number; name: string }[]>([]);

  // Modal state
  const [createVal, setCreateVal] = useState<{ open: boolean; mappingId: number; attrId: number; value: string } | null>(null);
  const [bulkAssign, setBulkAssign] = useState<{ open: boolean; attrId: number; mappingIds: number[] } | null>(null);
  const [bulkValId, setBulkValId] = useState('');
  const [bulkValOptions, setBulkValOptions] = useState<any[]>([]);
  const [confirmDelete, setConfirmDelete] = useState<{ id: number; name: string } | null>(null);

  const reloadSummary = useCallback(() => {
    api.get<Summary>('/mappings/review/summary').then(setSummary).catch(() => {});
  }, []);

  useEffect(() => {
    reloadSummary();
    api.get<{ items: { id: number; name: string }[] }>('/attributes?per_page=500')
      .then((d) => setAllAttrs(d.items || [])).catch(() => {});
  }, [reloadSummary]);

  // Load tab data
  const loadInconsistent = useCallback(() => {
    setIncLoading(true);
    api.get<{ items: InconsistentItem[]; total: number }>(
      `/mappings/review/inconsistent-detail/325?per_page=200&page=${incPage}`)
      .then((d) => { setIncItems(d.items); setIncTotal(d.total); })
      .catch(() => {})
      .finally(() => setIncLoading(false));
  }, [incPage]);

  const loadOrphans = useCallback(() => {
    setOrphanLoading(true);
    api.get<{ items: OrphanItem[]; total: number }>(
      `/mappings/review/orphans?per_page=200&page=${orphanPage}`)
      .then((d) => { setOrphanItems(d.items); setOrphanTotal(d.total); })
      .catch(() => {})
      .finally(() => setOrphanLoading(false));
  }, [orphanPage]);

  const loadUnassigned = useCallback(() => {
    setUnassignedLoading(true);
    api.get<{ items: UnassignedGroup[] }>('/mappings/review/unassigned')
      .then((d) => setUnassignedGroups(d.items || []))
      .catch(() => {})
      .finally(() => setUnassignedLoading(false));
  }, []);

  const loadAmbiguous = useCallback(() => {
    setAmbigLoading(true);
    api.get<{ items: AmbiguousItem[]; total: number }>(
      `/mappings/review/ambiguous?per_page=200&page=${ambigPage}`)
      .then((d) => { setAmbigItems(d.items); setAmbigTotal(d.total); })
      .catch(() => {})
      .finally(() => setAmbigLoading(false));
  }, [ambigPage]);

  useEffect(() => { if (tab === 'inconsistent') loadInconsistent(); }, [tab, loadInconsistent]);
  useEffect(() => { if (tab === 'orphans') loadOrphans(); }, [tab, loadOrphans]);
  useEffect(() => { if (tab === 'unassigned') loadUnassigned(); }, [tab, loadUnassigned]);
  useEffect(() => { if (tab === 'ambiguous') loadAmbiguous(); }, [tab, loadAmbiguous]);

  const refreshAll = () => {
    reloadSummary();
    loadInconsistent(); loadOrphans(); loadUnassigned(); loadAmbiguous();
  };

  // ── Actions ────────────────────────────────────────────────────────

  const openCreateValue = (item: InconsistentItem) => {
    setCreateVal({
      open: true,
      mappingId: item.id,
      attrId: item.target_attr_id,
      value: item.supplier_item_name,
    });
  };

  const doCreateValue = async () => {
    if (!createVal) return;
    setSaving(true);
    try {
      const result = await api.post<{ ok: boolean; attribute_value_id: number; created: boolean }>(
        '/mappings/review/values/create-and-assign', {
          mapping_id: createVal.mappingId,
          attribute_id: createVal.attrId,
          value: createVal.value,
        });
      toast.push('success', result.created
        ? 'Створено нове канонічне значення та призначено маппінг'
        : 'Знайдено існуюче значення та призначено маппінг');
      setCreateVal(null);
      refreshAll();
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally { setSaving(false); }
  };

  const openBulkReassign = async () => {
    setBulkValId('');
    try {
      const vals = await api.get<{ items: { id: number; value: string }[] }>('/attributes/325/values');
      setBulkValOptions(vals.items || []);
    } catch { setBulkValOptions([]); }
    const ids = incItems.map((r) => r.id);
    setBulkAssign({ open: true, attrId: 325, mappingIds: ids });
  };

  const doBulkReassign = async () => {
    if (!bulkAssign || !bulkValId) return;
    setSaving(true);
    try {
      const result = await api.put<{ updated: number; errors?: string[] }>(
        '/mappings/review/values/bulk-reassign', {
          mapping_ids: bulkAssign.mappingIds,
          attribute_value_id: Number(bulkValId),
        });
      if (result.errors && result.errors.length > 0) {
        toast.push('error', result.errors[0]);
      } else {
        toast.push('success', `${result.updated} значень перепризначено`);
      }
      setBulkAssign(null);
      refreshAll();
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally { setSaving(false); }
  };

  const doDeleteMapping = async () => {
    if (!confirmDelete) return;
    setSaving(true);
    try {
      await api.delete(`/mappings/values/${confirmDelete.id}`);
      toast.push('success', 'Маппінг видалено');
      setConfirmDelete(null);
      refreshAll();
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally { setSaving(false); }
  };

  const TABS = [
    { key: 'inconsistent', label: 'Неузгоджені значення', sumKey: 'inconsistent_targets' as const },
    { key: 'orphans', label: 'Сирітські', sumKey: 'orphans_total' as const },
    { key: 'ambiguous', label: 'Неоднозначні атрибути', sumKey: 'ambiguous_global' as const },
    { key: 'unassigned', label: 'Без категорії', sumKey: 'unassigned_mappings' as const },
  ];

  if (loading) return <LoadingState />;

  return (
    <div className="space-y-6">
      {/* Summary Dashboard */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-white rounded-lg border border-purple-200 px-4 py-3">
            <div className="text-2xl font-bold text-purple-600">{summary.inconsistent_targets}</div>
            <div className="text-xs text-gray-500 mt-0.5">Неузгоджені значення</div>
          </div>
          <div className="bg-white rounded-lg border border-orange-200 px-4 py-3">
            <div className="text-2xl font-bold text-orange-600">{summary.orphans_total}</div>
            <div className="text-xs text-gray-500 mt-0.5">Сирітські маппінги</div>
          </div>
          <div className="bg-white rounded-lg border border-yellow-200 px-4 py-3">
            <div className="text-2xl font-bold text-yellow-600">{summary.ambiguous_global}</div>
            <div className="text-xs text-gray-500 mt-0.5">Неоднозначні глобальні</div>
          </div>
          <div className="bg-white rounded-lg border border-red-200 px-4 py-3">
            <div className="text-2xl font-bold text-red-600">{summary.unassigned_mappings}</div>
            <div className="text-xs text-gray-500 mt-0.5">Без категорії</div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200 overflow-x-auto">
        {TABS.map((t) => (
          <button key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition whitespace-nowrap ${
              tab === t.key
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}>
            {t.label} ({summary ? summary[t.sumKey] : 0})
          </button>
        ))}
      </div>

      {/* ── INCONSISTENT VALUES TAB ─────────────────── */}
      {tab === 'inconsistent' && (
        <div>
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3 mb-4">
            <p className="text-sm text-yellow-800">
              <strong>Частота ядра, МГц</strong> — {incTotal} значень прив'язані до атрибуту «Частота ядра»,
              але батьківський маппінг очікує атрибут «Частота ядра, МГц».<br />
              Виберіть дію для кожного значення або скористайтесь масовим призначенням.
            </p>
          </div>

          <div className="flex gap-2 mb-3">
            <Button onClick={openBulkReassign} disabled={incItems.length === 0}>
              Призначити всі {incTotal} значень
            </Button>
            <Button variant="secondary" onClick={loadInconsistent}>
              Оновити
            </Button>
          </div>

          {incLoading ? <LoadingState /> : incItems.length === 0 ? (
            <EmptyState title="Немає неузгоджених значень" />
          ) : (
            <div className="overflow-x-auto border rounded-lg">
              <table className="w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <Th>Значення</Th>
                    <Th>Поточний атрибут</Th>
                    <Th>Очікуваний атрибут</Th>
                    <Th className="text-center">Є відповідник</Th>
                    <Th className="text-right">Товарів</Th>
                    <Th className="text-right">Дії</Th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {incItems.map((item) => (
                    <tr key={item.id} className="hover:bg-gray-50">
                      <Td className="font-mono text-xs">{item.supplier_item_name}</Td>
                      <Td>{item.current_attr_name}</Td>
                      <Td><Badge tone="blue">{item.target_attr_name}</Badge></Td>
                      <Td className="text-center">
                        {item.matching_exists
                          ? <Badge tone="green">Так</Badge>
                          : <Badge tone="red">Ні</Badge>
                        }
                      </Td>
                      <Td className="text-right">{item.product_usage}</Td>
                      <Td className="text-right">
                        <div className="flex gap-1 justify-end">
                          <Button size="sm" variant="secondary"
                            onClick={() => openCreateValue(item)}>
                            Створити значення
                          </Button>
                        </div>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── ORPHANS TAB ───────────────────────────────── */}
      {tab === 'orphans' && (
        <div>
          <div className="grid grid-cols-2 gap-3 mb-4">
            <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3">
              <div className="text-xl font-bold text-red-600">
                {orphanItems.filter((o) => o.reason === 'parent_missing').length}
              </div>
              <div className="text-xs text-gray-500 mt-0.5">Батька немає</div>
            </div>
            <div className="bg-orange-50 border border-orange-200 rounded-lg px-4 py-3">
              <div className="text-xl font-bold text-orange-600">
                {orphanItems.filter((o) => o.reason === 'parent_inactive').length}
              </div>
              <div className="text-xs text-gray-500 mt-0.5">Батько неактивний</div>
            </div>
          </div>

          <div className="bg-gray-50 border border-gray-200 rounded-lg px-4 py-3 mb-4">
            <p className="text-sm text-gray-600">
              Ці маппінги значень не мають активного батьківського маппінгу атрибута.
              Для виправлення використовуйте вкладку «Значення» в основній таблиці маппінгів.
            </p>
          </div>

          {orphanLoading ? <LoadingState /> : orphanItems.length === 0 ? (
            <EmptyState title="Немає сирітських маппінгів" />
          ) : (
            <div className="overflow-x-auto border rounded-lg max-h-96 overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    <Th>Атрибут</Th>
                    <Th>Значення</Th>
                    <Th>Причина</Th>
                    <Th className="text-right">Товарів</Th>
                    <Th className="text-right">Дії</Th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {orphanItems.map((o) => (
                    <tr key={o.id} className="hover:bg-gray-50">
                      <Td className="max-w-40 truncate">{o.holder_name || '—'}</Td>
                      <Td className="max-w-48 truncate">{o.supplier_item_name}</Td>
                      <Td>
                        {o.reason === 'parent_missing'
                          ? <Badge tone="red">Немає батька</Badge>
                          : <Badge tone="yellow">Батько неактивний</Badge>
                        }
                      </Td>
                      <Td className="text-right">{o.product_usage}</Td>
                      <Td className="text-right">
                        <Button size="sm" variant="ghost" className="text-red-600"
                          onClick={() => setConfirmDelete({ id: o.id, name: o.supplier_item_name })}>
                          Видалити
                        </Button>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── AMBIGUOUS GLOBAL TAB ─────────────────────── */}
      {tab === 'ambiguous' && (
        <div>
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3 mb-4">
            <p className="text-sm text-yellow-800">
              <strong>{ambigTotal}</strong> активних глобальних маппінгів атрибутів,
              які вказують на атрибути, що використовуються в кількох категоріях.
              Вони можуть бути легітимно глобальними або потребувати категорійного контексту.
            </p>
          </div>

          {ambigLoading ? <LoadingState /> : ambigItems.length === 0 ? (
            <EmptyState title="Немає неоднозначних маппінгів" />
          ) : (
            <div className="overflow-x-auto border rounded-lg max-h-96 overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    <Th>Атрибут постачальника</Th>
                    <Th>Внутрішній атрибут</Th>
                    <Th className="text-center">Категорій</Th>
                    <Th className="text-right">Товарів</Th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {ambigItems.map((a) => (
                    <tr key={a.id} className="hover:bg-gray-50">
                      <Td>{a.supplier_attr}</Td>
                      <Td><Badge tone="blue">{a.internal_attr}</Badge></Td>
                      <Td className="text-center">{a.cat_count}</Td>
                      <Td className="text-right">{a.product_usage}</Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── UNASSIGNED ATTRIBUTES TAB ────────────────── */}
      {tab === 'unassigned' && (
        <div>
          {unassignedLoading ? <LoadingState /> : unassignedGroups.length === 0 ? (
            <EmptyState title="Немає атрибутів без категорії" />
          ) : (
            <div className="space-y-4">
              {unassignedGroups.map((g) => (
                <div key={g.attr_id} className="bg-white rounded-lg border border-red-200 overflow-hidden">
                  <div className="px-4 py-3 bg-red-50 border-b border-red-100">
                    <div className="flex items-center justify-between">
                      <h4 className="font-semibold text-red-700">{g.attr_name}</h4>
                      <span className="text-xs text-red-500">{g.mapping_count} маппінгів</span>
                    </div>
                  </div>
                  <div className="px-4 py-3 space-y-2 text-sm">
                    <p><span className="text-gray-500">Назви постачальників:</span> {g.supplier_names}</p>
                    {g.candidates.length > 0 && (
                      <div>
                        <span className="text-gray-500">Можливі заміни:</span>
                        <div className="flex flex-wrap gap-1.5 mt-1">
                          {g.candidates.map((c) => (
                            <Badge key={c.id} tone="green">{c.name} ({c.cat_count} кат.)</Badge>
                          ))}
                        </div>
                      </div>
                    )}
                    <details className="text-xs mt-2">
                      <summary className="cursor-pointer text-blue-600 hover:underline">
                        Показати маппінги ({g.mappings.length})
                      </summary>
                      <ul className="mt-1 space-y-0.5">
                        {g.mappings.map((m) => (
                          <li key={m.id} className="text-gray-600">
                            ID {m.id}: {m.supplier_attr}
                            {m.is_active ? '' : ' (неактивний)'}
                          </li>
                        ))}
                      </ul>
                    </details>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── MODALS ────────────────────────────────────── */}

      {/* Create Value Modal */}
      <Modal open={!!createVal} title="Створити канонічне значення"
        onClose={() => setCreateVal(null)}>
        <div className="space-y-4">
          <p className="text-sm text-gray-600">Буде створено канонічне значення:</p>
          <div className="bg-gray-50 rounded-lg px-4 py-3 space-y-1 text-sm">
            <div><span className="text-gray-500">Атрибут:</span> {createVal ? allAttrs.find((a) => a.id === createVal.attrId)?.name : ''}</div>
            <div><span className="text-gray-500">Значення:</span> <strong>{createVal?.value}</strong></div>
          </div>
          <p className="text-xs text-gray-400">Якщо таке значення вже існує, буде використано існуюче.</p>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setCreateVal(null)}>Скасувати</Button>
            <Button onClick={doCreateValue} loading={saving}>Створити та призначити</Button>
          </div>
        </div>
      </Modal>

      {/* Bulk Reassign Modal */}
      <Modal open={!!bulkAssign} title="Призначити всі значення"
        onClose={() => setBulkAssign(null)}>
        <div className="space-y-4">
          <p className="text-sm text-gray-600">
            Ви збираєтесь призначити <strong>{bulkAssign?.mappingIds.length}</strong> значень
            до одного канонічного значення атрибута <strong>Частота ядра, МГц</strong>.
          </p>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Канонічне значення</label>
            <select value={bulkValId} onChange={(e) => setBulkValId(e.target.value)}
              className="input-field w-full text-sm">
              <option value="">Оберіть значення...</option>
              {bulkValOptions.map((v: any) => (
                <option key={v.id} value={v.id}>{v.value}</option>
              ))}
            </select>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setBulkAssign(null)}>Скасувати</Button>
            <Button onClick={doBulkReassign} loading={saving} disabled={!bulkValId}>
              Призначити всі
            </Button>
          </div>
        </div>
      </Modal>

      {/* Delete Confirmation */}
      <ConfirmDialog
        open={!!confirmDelete}
        title="Видалити маппінг значення?"
        message={confirmDelete
          ? `Маппінг значення «${confirmDelete.name}» буде видалено. Внутрішній каталог не зміниться. Товари не постраждають.`
          : ''}
        confirmLabel="Видалити" danger busy={saving}
        onConfirm={doDeleteMapping}
        onCancel={() => setConfirmDelete(null)} />
    </div>
  );
}
