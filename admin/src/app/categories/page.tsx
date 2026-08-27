'use client';

import { useEffect, useMemo, useState } from 'react';
import { api } from '@/lib/api';
import { PageHeader, Button, Input, Select, Textarea, LoadingState, ErrorState, EmptyState, Modal, ConfirmDialog, Badge, useToast, Table, Th, Td } from '@/components/ui';

type Cat = {
  id: number; parent_id: number | null; name: string; slug: string;
  is_active: boolean; sort_order: number; product_count?: number;
  children?: Cat[];
};

type CatAttr = {
  id: number; category_id: number; attribute_id: number;
  required: boolean; multiple: boolean; filterable: boolean;
  searchable: boolean; sort_order: number; filter_type: string | null;
  attribute_name: string; attribute_slug: string; attribute_type: string;
  values_count: number;
};

const EMPTY_FORM = { name: '', parent_id: '' as '' | number, description: '', sort_order: 0, is_active: true };

const FILTER_TYPES = ['', 'checkbox', 'multi_select', 'range', 'select'];
const FILTER_TYPE_LABELS: Record<string, string> = {
  '': '—', checkbox: 'Прапорець', multi_select: 'Мультивибір',
  range: 'Діапазон', select: 'Вибір',
};

export default function CategoriesPage() {
  const toast = useToast();
  const [cats, setCats] = useState<Cat[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [modal, setModal] = useState<{ open: boolean; editing: Cat | null }>({ open: false, editing: null });
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<Cat | null>(null);

  // Attribute management
  const [attrModal, setAttrModal] = useState<{ open: boolean; cat: Cat | null }>({ open: false, cat: null });
  const [catAttrs, setCatAttrs] = useState<CatAttr[]>([]);
  const [catAttrsLoading, setCatAttrsLoading] = useState(false);
  const [allAttrs, setAllAttrs] = useState<{ id: number; name: string }[]>([]);
  const [addAttrId, setAddAttrId] = useState('');
  const [addingAttr, setAddingAttr] = useState(false);
  const [attrSearch, setAttrSearch] = useState('');

  const load = () => {
    setLoading(true);
    api.get<{ items: Cat[] }>('/categories')
      .then((d) => setCats(d.items || []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  // Load all attributes for the add-attribute selector
  useEffect(() => {
    api.get<{ items: { id: number; name: string }[] }>('/attributes?per_page=500')
      .then((d) => setAllAttrs(d.items || []))
      .catch(() => {});
  }, []);

  const tree = useMemo<Cat[]>(() => {
    if (cats.length && cats[0]?.children !== undefined && cats.some((c) => c.parent_id === null)) return cats;
    const byId = new Map<number, Cat>();
    cats.forEach((c) => byId.set(c.id, { ...c, children: [] }));
    const roots: Cat[] = [];
    byId.forEach((c) => {
      if (c.parent_id && byId.has(c.parent_id)) byId.get(c.parent_id)!.children!.push(c);
      else roots.push(c);
    });
    return roots;
  }, [cats]);

  const matches = (c: Cat): boolean =>
    !search.trim() || c.name.toLowerCase().includes(search.trim().toLowerCase());

  const openCreate = (parent?: Cat) => {
    setForm({ ...EMPTY_FORM, parent_id: parent ? parent.id : '' });
    setModal({ open: true, editing: null });
  };
  const openEdit = (c: Cat) => {
    const flat = cats.find((x) => x.id === c.id)!;
    setForm({
      name: flat.name,
      parent_id: flat.parent_id ?? '',
      description: '',
      sort_order: flat.sort_order ?? 0,
      is_active: flat.is_active,
    });
    setModal({ open: true, editing: flat });
  };

  const openAttrs = async (cat: Cat) => {
    setAttrModal({ open: true, cat });
    setCatAttrsLoading(true);
    try {
      const d = await api.get<{ items: CatAttr[] }>(`/categories/${cat.id}/attributes`);
      setCatAttrs(d.items || []);
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
      setCatAttrs([]);
    } finally { setCatAttrsLoading(false); }
  };

  const reloadAttrs = async (catId: number) => {
    try {
      const d = await api.get<{ items: CatAttr[] }>(`/categories/${catId}/attributes`);
      setCatAttrs(d.items || []);
    } catch {}
  };

  const addAttribute = async () => {
    if (!addAttrId || !attrModal.cat) return;
    setAddingAttr(true);
    try {
      await api.post(`/categories/${attrModal.cat.id}/attributes`, {
        attribute_id: Number(addAttrId),
        required: false, multiple: false, filterable: true, searchable: false,
        sort_order: 0, filter_type: null,
      });
      toast.push('success', 'Атрибут додано до категорії');
      setAddAttrId('');
      await reloadAttrs(attrModal.cat.id);
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally { setAddingAttr(false); }
  };

  const removeAttribute = async (ca: CatAttr) => {
    if (!attrModal.cat) return;
    try {
      await api.delete(`/categories/${attrModal.cat.id}/attributes/${ca.id}`);
      toast.push('success', `Атрибут «${ca.attribute_name}» видалено з категорії`);
      await reloadAttrs(attrModal.cat.id);
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    }
  };

  // Value management for CategoryAttribute
  const [valueModal, setValueModal] = useState<{ open: boolean; ca: CatAttr | null }>({ open: false, ca: null });
  const [catValues, setCatValues] = useState<any[]>([]);
  const [catValuesLoading, setCatValuesLoading] = useState(false);
  const [availableNewValues, setAvailableNewValues] = useState<any[]>([]);
  const [selectedValueIds, setSelectedValueIds] = useState<number[]>([]);
  const [addingValues, setAddingValues] = useState(false);

  const openValues = async (ca: CatAttr) => {
    setValueModal({ open: true, ca });
    setCatValuesLoading(true);
    try {
      const d = await api.get<{ items: any[] }>(`/categories/${ca.category_id}/attributes/${ca.id}/values`);
      setCatValues(d.items || []);
    } catch { setCatValues([]); }
    finally { setCatValuesLoading(false); }
    // Load available
    try {
      const d = await api.get<{ items: any[] }>(`/categories/${ca.category_id}/attributes/${ca.id}/available-values`);
      setAvailableNewValues(d.items || []);
    } catch { setAvailableNewValues([]); }
    setSelectedValueIds([]);
  };

  const addSelectedValues = async () => {
    if (!valueModal.ca || selectedValueIds.length === 0) return;
    setAddingValues(true);
    try {
      await api.post(`/categories/${valueModal.ca.category_id}/attributes/${valueModal.ca.id}/values/bulk`, selectedValueIds);
      toast.push('success', 'Значення додані');
      await openValues(valueModal.ca);
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally { setAddingValues(false); }
  };

  const removeCatValue = async (cavid: number) => {
    if (!valueModal.ca) return;
    try {
      await api.delete(`/categories/${valueModal.ca.category_id}/attributes/${valueModal.ca.id}/values/${cavid}`);
      toast.push('success', 'Значення прибрано з категорії');
      await openValues(valueModal.ca);
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    }
  };

  const updateAttrConfig = async (ca: CatAttr, patch: Partial<CatAttr>) => {
    if (!attrModal.cat) return;
    try {
      await api.put(`/categories/${attrModal.cat.id}/attributes/${ca.id}`, patch);
      await reloadAttrs(attrModal.cat.id);
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    }
  };

  const save = async () => {
    if (!form.name.trim()) { toast.push('error', 'Вкажіть назву категорії'); return; }
    setSaving(true);
    const body = {
      name: form.name.trim(),
      parent_id: form.parent_id === '' ? null : Number(form.parent_id),
      description: form.description.trim() || null,
      sort_order: Number(form.sort_order) || 0,
      is_active: form.is_active,
    };
    try {
      if (modal.editing) await api.put(`/categories/${modal.editing.id}`, body);
      else await api.post('/categories', body);
      toast.push('success', modal.editing ? 'Категорію оновлено' : 'Категорію створено');
      setModal({ open: false, editing: null });
      load();
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally { setSaving(false); }
  };

  const doDelete = async () => {
    if (!deleting) return;
    try {
      await api.delete(`/categories/${deleting.id}`);
      toast.push('success', 'Категорію видалено');
      setDeleting(null); load();
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    }
  };

  const filteredAttrs = useMemo(() => {
    if (!attrSearch.trim()) return allAttrs;
    const q = attrSearch.trim().toLowerCase();
    return allAttrs.filter((a) => a.name.toLowerCase().includes(q));
  }, [allAttrs, attrSearch]);

  const availableAttrs = useMemo(() => {
    const assigned = new Set(catAttrs.map((ca) => ca.attribute_id));
    return filteredAttrs.filter((a) => !assigned.has(a.id));
  }, [filteredAttrs, catAttrs]);

  return (
    <div>
      <PageHeader title="Категорії" actions={
        <Button onClick={() => openCreate()}>+ Нова категорія</Button>
      } />

      {loading ? <LoadingState /> : error ? <ErrorState message={error} /> : (
        <div className="bg-white rounded-lg border border-gray-200">
          {tree.filter((c) => !search.trim() || matches(c)).map((c) => (
            <CatNode key={c.id} cat={c} depth={0} search={search}
              onEdit={openEdit} onDelete={(c) => setDeleting(c)}
              onAddChild={(c) => openCreate(c)}
              onManageAttrs={(c) => openAttrs(c)} />
          ))}
          {tree.length === 0 && <p className="text-sm text-gray-400 p-4">Категорій немає</p>}
        </div>
      )}

      <Modal open={modal.open} title={modal.editing ? 'Редагувати категорію' : 'Нова категорія'}
        onClose={() => setModal({ open: false, editing: null })}>
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Назва</label>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Батьківська категорія</label>
            <Select value={form.parent_id} onChange={(e) => setForm({ ...form, parent_id: e.target.value === '' ? '' : Number(e.target.value) })}>
              <option value="">— Коренева категорія —</option>
              {cats.filter((c) => c.id !== modal.editing?.id).map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </Select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Опис</label>
            <Textarea rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </div>
          <div className="flex items-end gap-4">
            <div className="w-32">
              <label className="block text-xs text-gray-500 mb-1">Порядок</label>
              <Input type="number" value={form.sort_order} onChange={(e) => setForm({ ...form, sort_order: Number(e.target.value) })} />
            </div>
            <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer pb-2">
              <input type="checkbox" className="rounded" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
              Активна
            </label>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setModal({ open: false, editing: null })}>Скасувати</Button>
            <Button loading={saving} onClick={save}>{modal.editing ? 'Зберегти' : 'Створити'}</Button>
          </div>
        </div>
      </Modal>

      {/* Attribute Management Modal */}
      <Modal open={attrModal.open} title={attrModal.cat ? `Атрибути: ${attrModal.cat.name}` : 'Атрибути'} wide
        onClose={() => setAttrModal({ open: false, cat: null })}>
        <div className="space-y-4">
          {catAttrsLoading ? <LoadingState /> : catAttrs.length === 0 ? (
            <div className="text-sm text-gray-400 py-4 text-center">Атрибути не налаштовані для цієї категорії.</div>
          ) : (
            <div className="overflow-x-auto border rounded-lg">
              <table className="w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <Th>Атрибут</Th>
                    <Th className="text-center">Обов'язк.</Th>
                    <Th className="text-center">Множ.</Th>
                    <Th className="text-center">Фільтр</Th>
                    <Th className="text-center">Тип фільтра</Th>
                    <Th className="text-right">Порядок</Th>
                    <Th className="text-right">Дії</Th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {catAttrs.map((ca) => (
                    <tr key={ca.id} className="hover:bg-gray-50">
                      <Td className="font-medium">{ca.attribute_name}</Td>
                      <Td className="text-center">
                        <input type="checkbox" checked={ca.required}
                          onChange={(e) => updateAttrConfig(ca, { required: e.target.checked })}
                          className="rounded" />
                      </Td>
                      <Td className="text-center">
                        <input type="checkbox" checked={ca.multiple}
                          onChange={(e) => updateAttrConfig(ca, { multiple: e.target.checked })}
                          className="rounded" />
                      </Td>
                      <Td className="text-center">
                        <input type="checkbox" checked={ca.filterable}
                          onChange={(e) => updateAttrConfig(ca, { filterable: e.target.checked })}
                          className="rounded" />
                      </Td>
                      <Td className="text-center">
                        <select value={ca.filter_type ?? ''}
                          onChange={(e) => updateAttrConfig(ca, { filter_type: e.target.value || null })}
                          className="input-field text-xs w-28">
                          {FILTER_TYPES.map((ft) => (
                            <option key={ft} value={ft}>{FILTER_TYPE_LABELS[ft]}</option>
                          ))}
                        </select>
                      </Td>
                      <Td className="text-right">
                        <input type="number" value={ca.sort_order}
                          onChange={(e) => updateAttrConfig(ca, { sort_order: Number(e.target.value) })}
                          className="input-field w-16 text-xs text-right" />
                      </Td>
                      <Td className="text-right">
                        <div className="flex gap-1 justify-end">
                          <Button size="sm" variant="secondary" onClick={() => openValues(ca)}>Значення</Button>
                          <Button size="sm" variant="ghost" className="text-red-600"
                            onClick={() => removeAttribute(ca)}>✕</Button>
                        </div>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Add attribute */}
          <div className="flex gap-2 items-end">
            <div className="flex-1">
              <label className="block text-xs text-gray-500 mb-1">Додати атрибут</label>
              <input
                value={addAttrId}
                onChange={(e) => setAddAttrId(e.target.value)}
                list="avail-attrs"
                placeholder="Пошук атрибута…"
                className="input-field w-full text-sm"
              />
              <datalist id="avail-attrs">
                {availableAttrs.map((a) => (
                  <option key={a.id} value={String(a.id)}>{a.name}</option>
                ))}
              </datalist>
              {addAttrId && (
                <div className="text-xs text-gray-400 mt-1">
                  Обрано: {allAttrs.find((a) => String(a.id) === addAttrId)?.name || '#' + addAttrId}
                </div>
              )}
            </div>
            <Button size="sm" onClick={addAttribute} loading={addingAttr}
              disabled={!addAttrId}>+ Додати</Button>
          </div>
        </div>
      </Modal>

      {/* Value Management Modal */}
      <Modal open={valueModal.open}
        title={valueModal.ca ? `Значення: ${valueModal.ca.attribute_name}` : ''}
        onClose={() => { setValueModal({ open: false, ca: null }); setSelectedValueIds([]); }} wide>
        <div className="space-y-4">
          {catValuesLoading ? <LoadingState /> : catValues.length === 0 ? (
            <div className="text-sm text-gray-400 py-4 text-center">Немає значень для цього атрибута в категорії.</div>
          ) : (
            <div className="overflow-x-auto border rounded-lg">
              <table className="w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Значення</th>
                    <th className="px-3 py-2 text-center text-xs font-medium text-gray-500">Товарів у категорії</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-gray-500">Дії</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {catValues.map((cv: any) => (
                    <tr key={cv.id} className="hover:bg-gray-50">
                      <td className="px-3 py-2 text-xs">{cv.value}</td>
                      <td className="px-3 py-2 text-center text-xs text-gray-500">{cv.product_count_in_category || 0}</td>
                      <td className="px-3 py-2 text-right">
                        <Button size="sm" variant="ghost" className="text-red-600"
                          onClick={() => removeCatValue(cv.id)}>Прибрати</Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Add new values */}
          {availableNewValues.length > 0 && (
            <div>
              <label className="block text-xs text-gray-500 mb-1">Додати значення</label>
              <div className="max-h-48 overflow-y-auto border rounded-lg p-2 space-y-1">
                {availableNewValues.map((av: any) => (
                  <label key={av.id} className="flex items-center gap-2 text-xs hover:bg-gray-50 px-2 py-1 rounded cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selectedValueIds.includes(av.id)}
                      onChange={(e) => {
                        if (e.target.checked) setSelectedValueIds([...selectedValueIds, av.id]);
                        else setSelectedValueIds(selectedValueIds.filter((id) => id !== av.id));
                      }}
                      className="rounded border-gray-300"
                    />
                    {av.value}
                  </label>
                ))}
              </div>
              <div className="flex justify-end mt-2">
                <Button size="sm" onClick={addSelectedValues} loading={addingValues}
                  disabled={selectedValueIds.length === 0}>
                  Додати вибрані ({selectedValueIds.length})
                </Button>
              </div>
            </div>
          )}
        </div>
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        title="Видалити категорію?"
        message={deleting ? `Категорію «${deleting.name}» буде видалено. Якщо до неї прив'язані товари або підкатегорії, сервер відмовить у видаленні.` : ''}
        confirmLabel="Видалити" danger busy={saving}
        onConfirm={doDelete} onCancel={() => setDeleting(null)}
      />
    </div>
  );
}

function CatNode({ cat, depth, search, onEdit, onDelete, onAddChild, onManageAttrs }: {
  cat: Cat; depth: number; search: string;
  onEdit: (c: Cat) => void; onDelete: (c: Cat) => void; onAddChild: (c: Cat) => void;
  onManageAttrs: (c: Cat) => void;
}) {
  const q = search.trim().toLowerCase();
  const children = (cat.children || []).filter((c) =>
    !q || c.name.toLowerCase().includes(q) ||
    (c.children || []).some((gc) => gc.name.toLowerCase().includes(q)),
  );
  return (
    <div>
      <div className={`flex items-center gap-3 px-4 py-2 hover:bg-gray-50 ${depth > 0 ? '' : 'bg-gray-50/60'}`}
        style={{ paddingLeft: `${16 + depth * 28}px` }}>
        <span className="text-sm font-medium text-gray-800 flex-1 truncate">{cat.name}</span>
        {!!cat.product_count && <span className="text-xs text-gray-400">{cat.product_count} тов.</span>}
        {!cat.is_active && <span className="text-xs text-red-500">неактивна</span>}
        <div className="flex gap-1">
          <Button size="sm" variant="ghost" onClick={() => onAddChild(cat)}>+ підкат.</Button>
          <Button size="sm" variant="secondary" onClick={() => onManageAttrs(cat)}>Атрибути</Button>
          <Button size="sm" variant="secondary" onClick={() => onEdit(cat)}>Змінити</Button>
          <Button size="sm" variant="ghost" className="text-red-600" onClick={() => onDelete(cat)}>✕</Button>
        </div>
      </div>
      {children.map((c) => (
        <CatNode key={c.id} cat={c} depth={depth + 1} search={search}
          onEdit={onEdit} onDelete={onDelete} onAddChild={onAddChild}
          onManageAttrs={onManageAttrs} />
      ))}
    </div>
  );
}
