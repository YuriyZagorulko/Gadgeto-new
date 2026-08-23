'use client';

import { useEffect, useMemo, useState } from 'react';
import { api, qs } from '@/lib/api';
import { PageHeader, Button, Input, Select, Table, Th, Td, Badge, LoadingState, ErrorState, EmptyState, Pagination, Modal, ConfirmDialog, useToast } from '@/components/ui';

type Kind = 'attributes' | 'values' | 'categories';
const KIND_LABELS: Record<Kind, string> = {
  attributes: 'Маппінг атрибутів',
  values: 'Маппінг значень атрибутів',
  categories: 'Маппінг категорій',
};
const PICKER_PATH: Record<Kind, string> = {
  categories: '/mappings/supplier-categories',
  attributes: '/mappings/supplier-attributes',
  values: '/mappings/supplier-values',
};
// Field names returned by GET /mappings/{kind} (see backend _KINDS map).
const SUPPLIER_FK: Record<Kind, string> = {
  categories: 'supplier_category_id',
  attributes: 'supplier_attribute_id',
  values: 'supplier_attribute_value_id',
};
const CATALOG_FK: Record<Kind, string> = {
  categories: 'category_id',
  attributes: 'attribute_id',
  values: 'attribute_value_id',
};

type MappingRow = {
  id: number;
  is_active: boolean;
  supplier_name: string;
  catalog_name: string | null;
} & Partial<Record<string, number | null>>;
type SupplierItem = { id: number; supplier_name?: string; supplier_value?: string };
type Opt = { id: number; name: string };
type ValueOpt = { id: number; value: string };

type SortKey = 'id' | 'supplier' | 'catalog' | 'status';
type SortDir = 'asc' | 'desc';

export default function MappingsPage() {
  const toast = useToast();
  const [kind, setKind] = useState<Kind>('attributes');
  const [supplierId, setSupplierId] = useState('');
  const [q, setQ] = useState('');
  const [appliedQ, setAppliedQ] = useState('');
  const [suppliers, setSuppliers] = useState<Opt[]>([]);
  const [cats, setCats] = useState<Opt[]>([]);
  const [attrs, setAttrs] = useState<Opt[]>([]);

  const [maps, setMaps] = useState<MappingRow[]>([]);
  const [mapTotal, setMapTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tick, setTick] = useState(0);

  // Client-side sorting of the loaded page.
  const [sortKey, setSortKey] = useState<SortKey>('id');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const [items, setItems] = useState<SupplierItem[]>([]);
  const [itemsLoading, setItemsLoading] = useState(false);
  const [itemsQ, setItemsQ] = useState('');

  // Mapping modal (create from the picker or edit an existing row)
  const [mappingItem, setMappingItem] = useState<SupplierItem | null>(null);
  const [editing, setEditing] = useState<MappingRow | null>(null);
  const [targetAttrId, setTargetAttrId] = useState('');   // for values kind
  const [targetId, setTargetId] = useState('');
  const [targetValues, setTargetValues] = useState<ValueOpt[]>([]);
  const [saving, setSaving] = useState(false);

  const [deleting, setDeleting] = useState<MappingRow | null>(null);

  useEffect(() => {
    api.get<{ items: Opt[] }>('/suppliers' + qs({ per_page: 100 })).then((d) => setSuppliers(d.items || [])).catch(() => {});
    api.get<{ items: Opt[] }>('/categories').then((d) => setCats(d.items || [])).catch(() => {});
    api.get<{ items: Opt[] }>('/attributes' + qs({ per_page: 100 })).then((d) => setAttrs(d.items || [])).catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError('');
    api.get<{ items: MappingRow[]; total: number }>(`/mappings/${kind}` + qs({
      page, per_page: perPage, supplier_id: supplierId || undefined, q: appliedQ || undefined,
    }))
      .then((d) => { if (!cancelled) { setMaps(d.items || []); setMapTotal(d.total); } })
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [kind, supplierId, appliedQ, page, perPage, tick]);

  // Filters changed — go back to the first page.
  useEffect(() => { setPage(1); }, [kind, supplierId, appliedQ]);

  const sortedMaps = useMemo(() => {
    const dir = sortDir === 'asc' ? 1 : -1;
    const val = (m: MappingRow): string | number => {
      switch (sortKey) {
        case 'id': return m.id;
        case 'supplier': return (m.supplier_name || '').toLowerCase();
        case 'catalog': return (m.catalog_name || '').toLowerCase();
        case 'status': return m.is_active ? 1 : 0;
      }
    };
    return [...maps].sort((a, b) => {
      const av = val(a);
      const bv = val(b);
      if (av < bv) return -dir;
      if (av > bv) return dir;
      return a.id - b.id; // stable tiebreaker
    });
  }, [maps, sortKey, sortDir]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortKey(key); setSortDir('asc'); }
  };

  useEffect(() => {
    let cancelled = false;
    setItemsLoading(true);
    const params: Record<string, string | number | boolean | undefined> = { unmapped: true, per_page: 30, q: itemsQ || undefined };
    if (kind === 'values') { /* values are filtered by supplier attribute below */ }
    else if (supplierId) params.supplier_id = supplierId;
    api.get<{ items: SupplierItem[] }>(PICKER_PATH[kind] + qs(params))
      .then((d) => !cancelled && setItems(d.items || []))
      .catch(() => !cancelled && setItems([]))
      .finally(() => !cancelled && setItemsLoading(false));
    return () => { cancelled = true; };
  }, [kind, supplierId, itemsQ]);

  const openMapping = (item: SupplierItem) => {
    setEditing(null);
    setMappingItem(item);
    setTargetId(''); setTargetAttrId(''); setTargetValues([]);
  };

  const openEdit = (m: MappingRow) => {
    setMappingItem(null);
    setEditing(m);
    setTargetId(String(m[CATALOG_FK[kind]] ?? ''));
    setTargetAttrId(''); setTargetValues([]);
  };

  const closeMappingModal = () => {
    setMappingItem(null);
    setEditing(null);
  };

  const loadCatalogValues = async (attrId: string) => {
    setTargetId('');
    if (!attrId) { setTargetValues([]); return; }
    try {
      const d = await api.get<{ items: ValueOpt[] }>(`/attributes/${attrId}/values`);
      setTargetValues(d.items || []);
    } catch { setTargetValues([]); }
  };

  const saveMapping = async () => {
    const catalogItemId = Number(targetId);
    if (kind !== 'values' && !catalogItemId) { toast.push('error', 'Оберіть об\'єкт каталогу'); return; }
    if (kind === 'values' && !catalogItemId) { toast.push('error', 'Оберіть значення каталогу'); return; }
    setSaving(true);
    try {
      if (editing) {
        await api.put(`/mappings/${kind}/${editing.id}`, { catalog_item_id: catalogItemId });
        toast.push('success', 'Відповідність оновлено');
      } else {
        if (!mappingItem) return;
        await api.post(`/mappings/${kind}`, {
          supplier_item_id: mappingItem.id,
          catalog_item_id: catalogItemId,
          is_active: true,
        });
        toast.push('success', 'Відповідність збережено');
        // refresh picker list
        setItems((prev) => prev.filter((i) => i.id !== mappingItem.id));
      }
      closeMappingModal();
      setTick((t) => t + 1);
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally { setSaving(false); }
  };

  const toggleActive = async (m: MappingRow) => {
    try {
      await api.put(`/mappings/${kind}/${m.id}`, { is_active: !m.is_active });
      setTick((t) => t + 1);
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    }
  };

  const doDelete = async () => {
    if (!deleting) return;
    try {
      await api.delete(`/mappings/${kind}/${deleting.id}`);
      toast.push('success', 'Відповідність видалено');
      setDeleting(null); setTick((t) => t + 1);
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
      setDeleting(null);
    }
  };

  const itemLabel = (i: SupplierItem) => i.supplier_name || i.supplier_value || `#${i.id}`;

  return (
    <div>
      <PageHeader title="Маппінг" />

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-gray-200">
        {(Object.keys(KIND_LABELS) as Kind[]).map((k) => (
          <button key={k} onClick={() => { setKind(k); setItemsQ(''); }}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition ${
              kind === k ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-800'
            }`}>
            {KIND_LABELS[k]}
          </button>
        ))}
      </div>

      {/* Shared filters */}
      <div className="bg-white border border-gray-200 rounded-lg p-3 mb-4 flex flex-wrap gap-3 items-end">
        <div className="w-52">
          <label className="block text-xs text-gray-500 mb-1">Постачальник</label>
          <Select value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
            <option value="">Усі постачальники</option>
            {suppliers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </Select>
        </div>
        <div className="w-56">
          <label className="block text-xs text-gray-500 mb-1">Пошук</label>
          <Input value={q} onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') setAppliedQ(q); }} placeholder="Назва..." />
        </div>
        <Button variant="secondary" onClick={() => setAppliedQ(q)}>Застосувати</Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Existing mappings */}
        <section>
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
            Існуючі відповідності {mapTotal > 0 && <span className="text-gray-400">({mapTotal})</span>}
          </h3>
          {error && <ErrorState message={error} />}
          {!error && loading && <LoadingState />}
          {!error && !loading && maps.length === 0 && <EmptyState title="Відповідностей немає" hint="Прив'яжіть записи постачальника праворуч." />}
          {!error && maps.length > 0 && (
            <>
              <Table head={
                <tr>
                  <Th>
                    <button type="button" onClick={() => toggleSort('id')} className="inline-flex items-center gap-1 uppercase tracking-wide hover:text-gray-800">
                      #<span className="text-[10px]" aria-hidden>{sortKey === 'id' ? (sortDir === 'asc' ? '▲' : '▼') : '↕'}</span>
                    </button>
                  </Th>
                  <Th>
                    <button type="button" onClick={() => toggleSort('supplier')} className="inline-flex items-center gap-1 uppercase tracking-wide hover:text-gray-800">
                      Постачальник<span className="text-[10px]" aria-hidden>{sortKey === 'supplier' ? (sortDir === 'asc' ? '▲' : '▼') : '↕'}</span>
                    </button>
                  </Th>
                  <Th>
                    <button type="button" onClick={() => toggleSort('catalog')} className="inline-flex items-center gap-1 uppercase tracking-wide hover:text-gray-800">
                      Каталог<span className="text-[10px]" aria-hidden>{sortKey === 'catalog' ? (sortDir === 'asc' ? '▲' : '▼') : '↕'}</span>
                    </button>
                  </Th>
                  <Th>
                    <button type="button" onClick={() => toggleSort('status')} className="inline-flex items-center gap-1 uppercase tracking-wide hover:text-gray-800">
                      Стан<span className="text-[10px]" aria-hidden>{sortKey === 'status' ? (sortDir === 'asc' ? '▲' : '▼') : '↕'}</span>
                    </button>
                  </Th>
                  <Th className="w-28"></Th>
                </tr>
              }>
                {sortedMaps.map((m) => (
                  <tr key={m.id} className="hover:bg-gray-50">
                    <Td className="font-mono text-xs text-gray-400">{m.id}</Td>
                    <Td className="text-sm">{m.supplier_name}</Td>
                    <Td className="text-sm">{m.catalog_name || <span className="text-gray-400">—</span>}</Td>
                    <Td>
                      <button onClick={() => toggleActive(m)} className="cursor-pointer" title="Перемкнути">
                        <Badge tone={m.is_active ? 'green' : 'gray'}>{m.is_active ? 'Активна' : 'Вимкнена'}</Badge>
                      </button>
                    </Td>
                    <Td>
                      <div className="flex gap-1">
                        <Button size="sm" variant="secondary" onClick={() => openEdit(m)}>Змінити</Button>
                        <Button size="sm" variant="ghost" className="text-red-600" onClick={() => setDeleting(m)}>✕</Button>
                      </div>
                    </Td>
                  </tr>
                ))}
              </Table>
              <Pagination
                page={page}
                pages={Math.max(1, Math.ceil(mapTotal / perPage))}
                total={mapTotal}
                onPage={(p) => setPage(p)}
                pageSize={perPage}
                onPageSizeChange={(n) => { setPerPage(n); setPage(1); }}
              />
            </>
          )}
        </section>

        {/* Unmapped picker */}
        <section>
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
            Неприв'язані записи постачальника
          </h3>
          <div className="flex gap-2 mb-2">
            <Input value={itemsQ} onChange={(e) => setItemsQ(e.target.value)} placeholder="Пошук серед неприв'язаних..." />
          </div>
          {itemsLoading ? (
            <LoadingState />
          ) : items.length === 0 ? (
            <EmptyState title="Неприв'язаних записів немає" />
          ) : (
            <div className="bg-white border border-gray-200 rounded-lg divide-y divide-gray-100 max-h-[480px] overflow-y-auto">
              {items.map((i) => (
                <div key={i.id} className="flex items-center gap-2 px-3 py-2 hover:bg-gray-50">
                  <span className="text-sm flex-1 truncate">{itemLabel(i)}</span>
                  <Button size="sm" variant="secondary" onClick={() => openMapping(i)}>Прив'язати</Button>
                </div>
              ))}
            </div>
          )}
          {itemsQ === '' && (
            <p className="text-xs text-gray-400 mt-2">Показано до 30 записів. Скористайтеся пошуком, щоб знайти інші.</p>
          )}
        </section>
      </div>

      {/* Mapping modal (create / edit) */}
      <Modal
        open={!!mappingItem || !!editing}
        title={editing ? `Редагувати відповідність #${editing.id}` : 'Нова відповідність'}
        onClose={closeMappingModal}
      >
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Запис постачальника</label>
            <div className="text-sm font-medium bg-gray-50 border border-gray-100 rounded px-3 py-2">
              {editing ? editing.supplier_name : mappingItem ? itemLabel(mappingItem) : ''}
            </div>
          </div>

          {kind === 'values' && (
            <div>
              <label className="block text-xs text-gray-500 mb-1">Атрибут каталогу *</label>
              <Select value={targetAttrId} onChange={(e) => loadCatalogValues(e.target.value)}>
                <option value="">Оберіть атрибут...</option>
                {attrs.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
              </Select>
            </div>
          )}

          <div>
            <label className="block text-xs text-gray-500 mb-1">
              {kind === 'categories' ? 'Категорія каталогу *' : kind === 'attributes' ? 'Атрибут каталогу *' : 'Значення каталогу *'}
            </label>
            {kind === 'categories' && (
              <Select value={targetId} onChange={(e) => setTargetId(e.target.value)}>
                <option value="">Оберіть...</option>
                {cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </Select>
            )}
            {kind === 'attributes' && (
              <Select value={targetId} onChange={(e) => setTargetId(e.target.value)}>
                <option value="">Оберіть...</option>
                {attrs.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
              </Select>
            )}
            {kind === 'values' && (
              <Select value={targetId} onChange={(e) => setTargetId(e.target.value)} disabled={!targetAttrId}>
                <option value="">{targetAttrId ? 'Оберіть...' : 'Спочатку оберіть атрибут'}</option>
                {targetValues.map((v) => <option key={v.id} value={v.id}>{v.value}</option>)}
              </Select>
            )}
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={closeMappingModal}>Скасувати</Button>
            <Button loading={saving} onClick={saveMapping}>{editing ? 'Зберегти зміни' : 'Зберегти'}</Button>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        title="Видалити відповідність?"
        message={deleting ? `«${deleting.supplier_name}» ↔ «${deleting.catalog_name || '—'}» буде відв'язано.` : ''}
        confirmLabel="Видалити" danger
        onConfirm={doDelete} onCancel={() => setDeleting(null)}
      />
    </div>
  );
}




