'use client';

import { useEffect, useState } from 'react';
import { api, qs } from '@/lib/api';
import { PageHeader, Button, Input, Select, Table, Th, Td, Badge, LoadingState, ErrorState, EmptyState, Modal, ConfirmDialog, useToast } from '@/components/ui';

type Kind = 'categories' | 'attributes' | 'values';
const KIND_LABELS: Record<Kind, string> = {
  categories: 'Категорії', attributes: 'Атрибути', values: 'Значення',
};
const PICKER_PATH: Record<Kind, string> = {
  categories: '/mappings/supplier-categories',
  attributes: '/mappings/supplier-attributes',
  values: '/mappings/supplier-values',
};

type MappingRow = { id: number; is_active: boolean; supplier_name: string; catalog_name: string | null };
type SupplierItem = { id: number; supplier_name?: string; supplier_value?: string };
type Opt = { id: number; name: string };
type ValueOpt = { id: number; value: string };

export default function MappingsPage() {
  const toast = useToast();
  const [kind, setKind] = useState<Kind>('categories');
  const [supplierId, setSupplierId] = useState('');
  const [q, setQ] = useState('');
  const [appliedQ, setAppliedQ] = useState('');
  const [suppliers, setSuppliers] = useState<Opt[]>([]);
  const [cats, setCats] = useState<Opt[]>([]);
  const [attrs, setAttrs] = useState<Opt[]>([]);

  const [maps, setMaps] = useState<MappingRow[]>([]);
  const [mapTotal, setMapTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tick, setTick] = useState(0);

  const [items, setItems] = useState<SupplierItem[]>([]);
  const [itemsLoading, setItemsLoading] = useState(false);
  const [itemsQ, setItemsQ] = useState('');

  // Mapping modal
  const [mappingItem, setMappingItem] = useState<SupplierItem | null>(null);
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
      page: 1, per_page: 50, supplier_id: supplierId || undefined, q: appliedQ || undefined,
    }))
      .then((d) => { if (!cancelled) { setMaps(d.items || []); setMapTotal(d.total); } })
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [kind, supplierId, appliedQ, tick]);

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
    setMappingItem(item);
    setTargetId(''); setTargetAttrId(''); setTargetValues([]);
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
    const catalogItemId = kind === 'values' ? Number(targetId) : Number(targetId);
    if (!mappingItem) return;
    if (kind !== 'values' && !catalogItemId) { toast.push('error', 'Оберіть об\'єкт каталогу'); return; }
    if (kind === 'values' && !catalogItemId) { toast.push('error', 'Оберіть значення каталогу'); return; }
    setSaving(true);
    try {
      await api.post(`/mappings/${kind}`, {
        supplier_item_id: mappingItem.id,
        catalog_item_id: catalogItemId,
        is_active: true,
      });
      toast.push('success', 'Відповідність збережено');
      setMappingItem(null);
      setTick((t) => t + 1);
      // refresh picker list
      setItems((prev) => prev.filter((i) => i.id !== mappingItem.id));
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
      <PageHeader title="Відповідності" />

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
            <Table head={<tr><Th>Постачальник</Th><Th>Каталог</Th><Th>Стан</Th><Th className="w-24"></Th></tr>}>
              {maps.map((m) => (
                <tr key={m.id} className="hover:bg-gray-50">
                  <Td className="text-sm">{m.supplier_name}</Td>
                  <Td className="text-sm">{m.catalog_name || <span className="text-gray-400">—</span>}</Td>
                  <Td>
                    <button onClick={() => toggleActive(m)} className="cursor-pointer" title="Перемкнути">
                      <Badge tone={m.is_active ? 'green' : 'gray'}>{m.is_active ? 'Активна' : 'Вимкнена'}</Badge>
                    </button>
                  </Td>
                  <Td>
                    <Button size="sm" variant="ghost" className="text-red-600" onClick={() => setDeleting(m)}>✕</Button>
                  </Td>
                </tr>
              ))}
            </Table>
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

      {/* Mapping modal */}
      <Modal open={!!mappingItem} title="Нова відповідність" onClose={() => setMappingItem(null)}>
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Запис постачальника</label>
            <div className="text-sm font-medium bg-gray-50 border border-gray-100 rounded px-3 py-2">
              {mappingItem ? itemLabel(mappingItem) : ''}
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
            <Button variant="secondary" onClick={() => setMappingItem(null)}>Скасувати</Button>
            <Button loading={saving} onClick={saveMapping}>Зберегти</Button>
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




