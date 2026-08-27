'use client';

import { useEffect, useState, useCallback } from 'react';
import { api, qs } from '@/lib/api';
import { PageHeader, Button, Input, Select, Table, Th, Td, Pagination, LoadingState, ErrorState, EmptyState, Modal, ConfirmDialog, Badge, useToast, Spinner } from '@/components/ui';

type Attribute = {
  id: number; name: string; slug: string; type: string;
  is_filterable: boolean; sort_order: number;
  values_count: number; products_count: number;
  categories_count?: number;
};
type ListResp = { items: Attribute[]; total: number; page: number; per_page: number; total_pages: number };
type Value = { id: number; value: string; slug: string; is_active: boolean; products_count: number };
type CatOpt = { id: number; name: string; parent_id: number | null };
type CategoryConfig = {
  required: boolean; multiple: boolean; filterable: boolean;
  searchable: boolean; sort_order: number; filter_type: string;
};

const TYPES = ['select', 'text', 'number', 'boolean'];
const TYPE_LABELS: Record<string, string> = {
  select: 'Список', text: 'Текст', number: 'Число', boolean: 'Так/Ні',
};
const FILTER_TYPES = ['', 'checkbox', 'multi_select', 'range', 'select'];
const FILTER_TYPE_LABELS: Record<string, string> = {
  '': '—', checkbox: 'Прапорець', multi_select: 'Мультивибір',
  range: 'Діапазон', select: 'Вибір',
};
const DEFAULT_CONFIG: CategoryConfig = {
  required: false, multiple: false, filterable: true,
  searchable: false, sort_order: 0, filter_type: '',
};
const EMPTY_ATTR = { name: '', type: 'select', is_filterable: true };
const EMPTY_VALUE = { value: '', is_active: true };

export default function AttributesPage() {
  const toast = useToast();
  const [search, setSearch] = useState('');
  const [applied, setApplied] = useState('');
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ListResp | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tick, setTick] = useState(0);
  const [allCategories, setAllCategories] = useState<CatOpt[]>([]);

  const [modal, setModal] = useState<{ open: boolean; editing: Attribute | null }>({ open: false, editing: null });
  const [form, setForm] = useState(EMPTY_ATTR);
  const [selCatIds, setSelCatIds] = useState<number[]>([]);
  const [catConfigs, setCatConfigs] = useState<Record<number, CategoryConfig>>({});
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<Attribute | null>(null);

  // Values management
  const [expanded, setExpanded] = useState<number | null>(null);
  const [values, setValues] = useState<Value[]>([]);
  const [valuesLoading, setValuesLoading] = useState(false);
  const [valueModal, setValueModal] = useState<{ open: boolean; attrId: number; editing: Value | null }>({ open: false, attrId: 0, editing: null });
  const [valueForm, setValueForm] = useState(EMPTY_VALUE);
  const [deletingValue, setDeletingValue] = useState<{ aid: number; v: Value } | null>(null);

  // Load categories once
  useEffect(() => {
    api.get<{ items: CatOpt[] }>('/categories')
      .then((d) => setAllCategories(d.items || []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError('');
    api.get<ListResp>('/attributes' + qs({ page, per_page: 20, search: applied || undefined }))
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [page, applied, tick]);

  const reload = () => setTick((t) => t + 1);

  const loadValues = async (aid: number) => {
    setValuesLoading(true);
    try {
      const d = await api.get<{ items: Value[] }>(`/attributes/${aid}/values`);
      setValues(d.items || []);
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
      setValues([]);
    } finally { setValuesLoading(false); }
  };

  const toggleExpand = (aid: number) => {
    if (expanded === aid) { setExpanded(null); return; }
    setExpanded(aid);
    loadValues(aid);
  };

  const openCreate = () => {
    setForm({ name: '', type: 'select', is_filterable: true });
    setSelCatIds([]);
    setCatConfigs({});
    setModal({ open: true, editing: null });
  };

  const openEdit = async (attr: Attribute) => {
    setForm({ name: attr.name, type: attr.type, is_filterable: attr.is_filterable });
    // Load categories for this attribute
    try {
      const d = await api.get<{ items: any[] }>(`/attributes/${attr.id}/categories`);
      const cats = d.items || [];
      setSelCatIds(cats.map((c: any) => c.id));
      const configs: Record<number, CategoryConfig> = {};
      for (const c of cats) {
        configs[c.id] = {
          required: c.required ?? false,
          multiple: c.multiple ?? false,
          filterable: c.filterable ?? true,
          searchable: c.searchable ?? false,
          sort_order: c.sort_order ?? 0,
          filter_type: c.filter_type ?? '',
        };
      }
      setCatConfigs(configs);
    } catch {
      setSelCatIds([]);
      setCatConfigs({});
    }
    setModal({ open: true, editing: attr });
  };

  const saveAttr = async () => {
    const attrBody = { name: form.name.trim(), type: form.type, is_filterable: form.is_filterable };
    setSaving(true);
    try {
      let attrId: number;
      if (modal.editing) {
        await api.put(`/attributes/${modal.editing.id}`, attrBody);
        attrId = modal.editing.id;
      } else {
        const res = await api.post<{ id: number }>('/attributes', attrBody);
        attrId = res.id;
      }

      // Sync category assignments
      const currentCats = new Set<number>(selCatIds);
      // Get previously assigned categories from server
      const prevResp = await api.get<{ items: any[] }>(`/attributes/${attrId}/categories`);
      const prevCats = new Set((prevResp.items || []).map((c: any) => c.id));

      // Add new categories
      const toAdd = selCatIds.filter((id) => !prevCats.has(id));
      for (const cid of toAdd) {
        const cfg = catConfigs[cid] || DEFAULT_CONFIG;
        await api.post(`/attributes/${attrId}/categories`, [cid])
          .catch(() => {});
        // Also update config via category attributes endpoint
        await updateCatAttrConfig(attrId, cid, cfg);
      }

      // Remove categories no longer assigned
      const toRemove = [...prevCats].filter((id) => !currentCats.has(id));
      for (const cid of toRemove) {
        try {
          await api.delete(`/attributes/${attrId}/categories/${cid}`);
        } catch {}
      }

      // Update config for existing categories
      for (const cid of selCatIds) {
        if (prevCats.has(cid)) {
          const cfg = catConfigs[cid];
          if (cfg) await updateCatAttrConfig(attrId, cid, cfg);
        }
      }

      toast.push('success', modal.editing ? 'Атрибут оновлено' : 'Атрибут створено');
      setModal({ open: false, editing: null });
      reload();
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally { setSaving(false); }
  };

  const updateCatAttrConfig = async (attrId: number, catId: number, cfg: CategoryConfig) => {
    try {
      // Find the category_attribute id
      const caResp = await api.get<{ items: any[] }>(`/categories/${catId}/attributes`);
      const ca = (caResp.items || []).find((c: any) => c.attribute_id === attrId);
      if (ca) {
        await api.put(`/categories/${catId}/attributes/${ca.id}`, cfg);
      }
    } catch {}
  };

  const doDeleteAttr = async () => {
    if (!deleting) return;
    setSaving(true);
    try {
      await api.delete(`/attributes/${deleting.id}`);
      toast.push('success', 'Атрибут видалено');
      setDeleting(null); reload();
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally { setSaving(false); }
  };

  // Value CRUD
  const saveValue = async () => {
    if (!valueForm.value.trim()) { toast.push('error', 'Вкажіть значення'); return; }
    setSaving(true);
    const activeAttrId = expanded ?? valueModal.attrId;
    try {
      if (valueModal.editing) {
        await api.put(`/attributes/${activeAttrId}/values/${valueModal.editing.id}`, valueForm);
      } else {
        await api.post(`/attributes/${activeAttrId}/values`, valueForm);
      }
      toast.push('success', valueModal.editing ? 'Значення оновлено' : 'Значення створено');
      setValueModal({ open: false, attrId: 0, editing: null });
      loadValues(activeAttrId);
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally { setSaving(false); }
  };

  const doDeleteValue = async () => {
    if (!deletingValue) return;
    setSaving(true);
    try {
      await api.delete(`/attributes/${deletingValue.aid}/values/${deletingValue.v.id}`);
      toast.push('success', 'Значення видалено');
      setDeletingValue(null);
      loadValues(deletingValue.aid);
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally { setSaving(false); }
  };

  return (
    <div>
      <PageHeader title="Атрибути" actions={
        <Button onClick={openCreate}>+ Новий атрибут</Button>
      } />

      <div className="flex gap-2 mb-3">
        <Input value={search} placeholder="Пошук атрибуту..."
          onKeyDown={(e) => { if (e.key === 'Enter') { setApplied(search); setPage(1); } }}
          onChange={(e) => setSearch(e.target.value)} className="max-w-xs" />
        <Button variant="secondary" onClick={() => { setApplied(search); setPage(1); }}>Знайти</Button>
      </div>

      {loading ? <LoadingState /> : error ? <ErrorState message={error} /> : !data ? <EmptyState title="Атрибутів не знайдено" /> : (
        <>
          <Table head={
            <tr>
              <Th>Назва</Th>
              <Th className="text-gray-500 text-xs">Тип</Th>
              <Th className="text-gray-500 text-xs">Категорій</Th>
              <Th className="text-gray-500 text-xs">Значень</Th>
              <Th className="text-gray-500 text-xs">Товарів</Th>
              <Th className="text-gray-500 text-xs">Дії</Th>
            </tr>
          }>
              {data.items.map((attr) => (
                <AttributeRow key={attr.id} attr={attr}
                  expanded={expanded === attr.id}
                  onToggle={() => toggleExpand(attr.id)}
                  onEdit={() => openEdit(attr)}
                  onDelete={() => setDeleting(attr)}
                  onAddValue={() => setValueModal({ open: true, attrId: attr.id, editing: null })}
                  onEditValue={(v) => setValueModal({ open: true, attrId: attr.id, editing: v })}
                  onDeleteValue={(v) => setDeletingValue({ aid: attr.id, v })}
                  values={values} valuesLoading={valuesLoading} />
              ))}
          </Table>
          <div className="mt-4">
            <Pagination page={page} pages={data.total_pages} total={data.total} onPage={setPage} />
          </div>
        </>
      )}

      {/* Create/Edit Attribute Modal */}
      <Modal open={modal.open} title={modal.editing ? `Редагування: ${form.name}` : 'Новий атрибут'} wide
        onClose={() => setModal({ open: false, editing: null })}>
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Назва</label>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Напр., Бренд" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Тип</label>
            <Select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
              {TYPES.map((t) => <option key={t} value={t}>{TYPE_LABELS[t]}</option>)}
            </Select>
          </div>

          {/* Category Assignment */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">
              Категорії ({selCatIds.length} обрані)
            </label>
            <div className="flex flex-wrap gap-1.5 mb-2">
              {selCatIds.map((cid) => {
                const cat = allCategories.find((c) => c.id === cid);
                return (
                  <span key={cid} className="inline-flex items-center gap-1 bg-blue-900/60 border border-blue-700 text-blue-100 text-xs px-2 py-1 rounded">
                    {cat?.name || `#${cid}`}
                    <button type="button" onClick={() => setSelCatIds(selCatIds.filter((id) => id !== cid))} className="text-blue-300 hover:text-white ml-0.5" aria-label="Видалити">×</button>
                  </span>
                );
              })}
            </div>
            <div className="relative">
              <input
                list="cat-list-attr"
                className="input-field w-full text-sm"
                placeholder="+ Додати категорію…"
                onChange={(e) => {
                  const id = Number(e.target.value);
                  if (id && !selCatIds.includes(id)) {
                    setSelCatIds([...selCatIds, id]);
                    if (!catConfigs[id]) {
                      setCatConfigs({...catConfigs, [id]: { required: false, multiple: false, filterable: true, searchable: false, sort_order: 0, filter_type: '' }});
                    }
                  }
                  e.target.value = '';
                }}
              />
              <datalist id="cat-list-attr">
                {allCategories
                  .filter((c) => !selCatIds.includes(c.id))
                  .map((c) => <option key={c.id} value={String(c.id)}>{c.name}</option>)}
              </datalist>
            </div>
          </div>

          {/* Per-category configuration */}
          {selCatIds.length > 0 && (
            <div>
              <label className="block text-xs text-gray-500 mb-2">Налаштування для категорій</label>
              <div className="overflow-x-auto border rounded-lg">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Категорія</th>
                      <th className="px-3 py-2 text-center text-xs font-medium text-gray-500">Обов'язк.</th>
                      <th className="px-3 py-2 text-center text-xs font-medium text-gray-500">Множ.</th>
                      <th className="px-3 py-2 text-center text-xs font-medium text-gray-500">Фільтр</th>
                      <th className="px-3 py-2 text-center text-xs font-medium text-gray-500">Порядок</th>
                      <th className="px-3 py-2 text-center text-xs font-medium text-gray-500">Тип фільтра</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {selCatIds.map((cid) => {
                      const cat = allCategories.find((c) => c.id === cid);
                      const cfg = catConfigs[cid] || DEFAULT_CONFIG;
                      const setCfg = (patch: Partial<CategoryConfig>) => {
                        setCatConfigs({ ...catConfigs, [cid]: { ...cfg, ...patch } });
                      };
                      return (
                        <tr key={cid}>
                          <td className="px-3 py-2 text-xs font-medium">{cat?.name || `#${cid}`}</td>
                          <td className="px-3 py-2 text-center">
                            <input type="checkbox" checked={cfg.required}
                              onChange={(e) => setCfg({ required: e.target.checked })} className="rounded" />
                          </td>
                          <td className="px-3 py-2 text-center">
                            <input type="checkbox" checked={cfg.multiple}
                              onChange={(e) => setCfg({ multiple: e.target.checked })} className="rounded" />
                          </td>
                          <td className="px-3 py-2 text-center">
                            <input type="checkbox" checked={cfg.filterable}
                              onChange={(e) => setCfg({ filterable: e.target.checked })} className="rounded" />
                          </td>
                          <td className="px-3 py-2 text-center">
                            <input type="number" value={cfg.sort_order}
                              onChange={(e) => setCfg({ sort_order: Number(e.target.value) })}
                              className="input-field w-16 text-center text-xs" />
                          </td>
                          <td className="px-3 py-2">
                            <select value={cfg.filter_type}
                              onChange={(e) => setCfg({ filter_type: e.target.value })}
                              className="input-field text-xs">
                              {FILTER_TYPES.map((ft) => (
                                <option key={ft} value={ft}>{FILTER_TYPE_LABELS[ft]}</option>
                              ))}
                            </select>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setModal({ open: false, editing: null })}>Скасувати</Button>
            <Button loading={saving} onClick={saveAttr}>
              {modal.editing ? 'Зберегти зміни' : 'Створити'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Values modal */}
      <Modal open={valueModal.open}
        title={valueModal.editing ? 'Редагувати значення' : 'Нове значення'}
        onClose={() => setValueModal({ open: false, attrId: 0, editing: null })}>
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Значення</label>
            <Input value={valueForm.value}
              onChange={(e) => setValueForm({ ...valueForm, value: e.target.value })} />
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input type="checkbox" className="rounded" checked={valueForm.is_active}
              onChange={(e) => setValueForm({ ...valueForm, is_active: e.target.checked })} />
            Активне
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setValueModal({ open: false, attrId: 0, editing: null })}>Скасувати</Button>
            <Button loading={saving} onClick={saveValue}>{valueModal.editing ? 'Зберегти' : 'Створити'}</Button>
          </div>
        </div>
      </Modal>

      <ConfirmDialog open={!!deleting} title="Видалити атрибут?"
        message={deleting ? `Атрибут «${deleting.name}» буде видалено. Якщо він використовується товарами, сервер відмовить.` : ''}
        confirmLabel="Видалити" danger busy={saving}
        onConfirm={doDeleteAttr} onCancel={() => setDeleting(null)} />
      <ConfirmDialog open={!!deletingValue} title="Видалити значення?"
        message={deletingValue ? `Значення «${deletingValue.v.value}» буде видалено.` : ''}
        confirmLabel="Видалити" danger busy={saving}
        onConfirm={doDeleteValue} onCancel={() => setDeletingValue(null)} />
    </div>
  );
}

function AttributeRow({ attr, expanded, onToggle, onEdit, onDelete, onAddValue, onEditValue, onDeleteValue, values, valuesLoading }: {
  attr: Attribute; expanded: boolean;
  onToggle: () => void; onEdit: () => void; onDelete: () => void;
  onAddValue: () => void; onEditValue: (v: Value) => void; onDeleteValue: (v: Value) => void;
  values: Value[]; valuesLoading: boolean;
}) {
  return (
    <>
      <tr className="hover:bg-gray-50">
        <Td>
          <button onClick={onToggle} className="font-medium text-blue-600 hover:underline text-left">
            {attr.name}
          </button>
          <div className="text-xs text-gray-400">{attr.slug}</div>
        </Td>
        <Td><Badge tone="blue">{TYPE_LABELS[attr.type] || attr.type}</Badge></Td>
        <Td><Badge tone={attr.categories_count ? 'green' : 'gray'}>{attr.categories_count ?? 0}</Badge></Td>
        <Td><button onClick={onToggle} className="hover:text-blue-600">{attr.values_count}</button></Td>
        <Td>{attr.products_count}</Td>
        <Td>
          <div className="flex gap-1">
            <Button size="sm" variant="secondary" onClick={onAddValue}>+ значення</Button>
            <Button size="sm" variant="secondary" onClick={onEdit}>Змінити</Button>
            <Button size="sm" variant="ghost" className="text-red-600" onClick={onDelete}>✕</Button>
          </div>
        </Td>
      </tr>
      {expanded && (
        <tr className="bg-gray-50/60">
          <td colSpan={6} className="px-10 py-3 border-t border-gray-100">
            {valuesLoading ? (
              <Spinner />
            ) : values.length === 0 ? (
              <p className="text-sm text-gray-400 py-2">Значень немає — додайте перше.</p>
            ) : (
              <div className="max-h-64 overflow-y-auto">
                <table className="w-full text-sm">
                  <tbody className="divide-y divide-gray-100">
                    {values.map((v) => (
                      <tr key={v.id}>
                        <td className="py-1.5 pr-4">{v.value}</td>
                        <td className="py-1.5 pr-4 w-24">{v.is_active ? <Badge tone="green">активне</Badge> : <Badge tone="gray">вимк.</Badge>}</td>
                        <td className="py-1.5 pr-4 w-28 text-gray-400 text-xs">{v.products_count} тов.</td>
                        <td className="py-1.5 w-44">
                          <div className="flex gap-1 justify-end">
                            <Button size="sm" variant="secondary" onClick={() => onEditValue(v)}>Змінити</Button>
                            <Button size="sm" variant="ghost" className="text-red-600" onClick={() => onDeleteValue(v)}>✕</Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}
