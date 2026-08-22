'use client';

import { useEffect, useState } from 'react';
import { api, qs } from '@/lib/api';
import { PageHeader, Button, Input, Select, Table, Th, Td, Pagination, LoadingState, ErrorState, EmptyState, Modal, ConfirmDialog, Badge, useToast, Spinner } from '@/components/ui';

type Attribute = {
  id: number; name: string; slug: string; type: string;
  is_filterable: boolean; sort_order: number;
  values_count: number; products_count: number;
};
type ListResp = { items: Attribute[]; total: number; page: number; per_page: number; total_pages: number };
type Value = { id: number; value: string; slug: string; is_active: boolean; products_count: number };

const TYPES = ['select', 'text', 'number', 'boolean'];
const TYPE_LABELS: Record<string, string> = {
  select: 'Список', text: 'Текст', number: 'Число', boolean: 'Так/Ні',
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

  const [modal, setModal] = useState<{ open: boolean; editing: Attribute | null }>({ open: false, editing: null });
  const [form, setForm] = useState(EMPTY_ATTR);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<Attribute | null>(null);

  // Values management
  const [expanded, setExpanded] = useState<number | null>(null);
  const [values, setValues] = useState<Value[]>([]);
  const [valuesLoading, setValuesLoading] = useState(false);
  const [valueModal, setValueModal] = useState<{ open: boolean; attrId: number; editing: Value | null }>({ open: false, attrId: 0, editing: null });
  const [valueForm, setValueForm] = useState(EMPTY_VALUE);
  const [deletingValue, setDeletingValue] = useState<{ aid: number; v: Value } | null>(null);

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

  const saveAttr = async () => {
    if (!form.name.trim()) { toast.push('error', 'Вкажіть назву атрибута'); return; }
    setSaving(true);
    const body = { name: form.name.trim(), type: form.type, is_filterable: form.is_filterable };
    try {
      if (modal.editing) await api.put(`/attributes/${modal.editing.id}`, body);
      else await api.post('/attributes', body);
      toast.push('success', modal.editing ? 'Атрибут оновлено' : 'Атрибут створено');
      setModal({ open: false, editing: null }); reload();
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally { setSaving(false); }
  };

  const doDeleteAttr = async () => {
    if (!deleting) return;
    try {
      await api.delete(`/attributes/${deleting.id}`);
      toast.push('success', 'Атрибут видалено');
      setDeleting(null); reload();
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
      setDeleting(null);
    }
  };

  const saveValue = async () => {
    if (!valueForm.value.trim()) { toast.push('error', 'Вкажіть значення'); return; }
    setSaving(true);
    const body = { value: valueForm.value.trim(), is_active: valueForm.is_active };
    try {
      if (valueModal.editing) await api.put(`/attributes/${valueModal.attrId}/values/${valueModal.editing.id}`, body);
      else await api.post(`/attributes/${valueModal.attrId}/values`, body);
      toast.push('success', 'Значення збережено');
      setValueModal({ open: false, attrId: 0, editing: null });
      loadValues(valueModal.attrId); reload();
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally { setSaving(false); }
  };

  const doDeleteValue = async () => {
    if (!deletingValue) return;
    try {
      await api.delete(`/attributes/${deletingValue.aid}/values/${deletingValue.v.id}`);
      toast.push('success', 'Значення видалено');
      setDeletingValue(null);
      loadValues(deletingValue.aid); reload();
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
      setDeletingValue(null);
    }
  };

  const openValueModal = (attrId: number, editing: Value | null) => {
    setValueForm(editing ? { value: editing.value, is_active: editing.is_active } : EMPTY_VALUE);
    setValueModal({ open: true, attrId, editing });
  };

  return (
    <div>
      <PageHeader
        title="Атрибути"
        actions={
          <div className="flex gap-2">
            <Input value={search} onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') { setPage(1); setApplied(search); } }}
              placeholder="Пошук..." />
            <Button variant="secondary" onClick={() => { setPage(1); setApplied(search); }}>Знайти</Button>
            <Button onClick={() => { setForm(EMPTY_ATTR); setModal({ open: true, editing: null }); }}>＋ Додати</Button>
          </div>
        }
      />

      {error && <ErrorState message={error} onRetry={reload} />}
      {!error && loading && !data && <LoadingState />}
      {!error && data?.items.length === 0 && <EmptyState title="Атрибутів не знайдено" />}
      {data && data.items.length > 0 && (
        <>
          <Table head={<tr><Th>Назва</Th><Th>Тип</Th><Th>Фільтр</Th><Th>Значень</Th><Th>Товарів</Th><Th className="w-52"></Th></tr>}>
            {data.items.map((a) => (
              <AttributeRow key={a.id} attr={a} expanded={expanded === a.id}
                onToggle={() => toggleExpand(a.id)}
                onEdit={() => { setForm({ name: a.name, type: a.type, is_filterable: a.is_filterable }); setModal({ open: true, editing: a }); }}
                onDelete={() => setDeleting(a)}
                onAddValue={() => openValueModal(a.id, null)}
                onEditValue={(v) => openValueModal(a.id, v)}
                onDeleteValue={(v) => setDeletingValue({ aid: a.id, v })}
                values={values} valuesLoading={valuesLoading} />
            ))}
          </Table>
          <div className="mt-4">
            <Pagination page={data.page} pages={data.total_pages} total={data.total} onPage={setPage} />
          </div>
        </>
      )}

      <Modal open={modal.open} title={modal.editing ? `Редагування: ${modal.editing.name}` : 'Новий атрибут'}
        onClose={() => setModal({ open: false, editing: null })}>
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Назва *</label>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} autoFocus />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Тип</label>
            <Select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
              {TYPES.map((t) => <option key={t} value={t}>{TYPE_LABELS[t] || t}</option>)}
            </Select>
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
            <input type="checkbox" className="rounded" checked={form.is_filterable} onChange={(e) => setForm({ ...form, is_filterable: e.target.checked })} />
            Використовується у фільтрах
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setModal({ open: false, editing: null })}>Скасувати</Button>
            <Button loading={saving} onClick={saveAttr}>{modal.editing ? 'Зберегти' : 'Створити'}</Button>
          </div>
        </div>
      </Modal>

      {/* Value create/edit modal */}
      <Modal open={valueModal.open} title={valueModal.editing ? 'Редагувати значення' : 'Нове значення'}
        onClose={() => setValueModal({ open: false, attrId: 0, editing: null })}>
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Значення *</label>
            <Input value={valueForm.value} onChange={(e) => setValueForm({ ...valueForm, value: e.target.value })} autoFocus />
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
            <input type="checkbox" className="rounded" checked={valueForm.is_active} onChange={(e) => setValueForm({ ...valueForm, is_active: e.target.checked })} />
            Активне
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setValueModal({ open: false, attrId: 0, editing: null })}>Скасувати</Button>
            <Button loading={saving} onClick={saveValue}>Зберегти</Button>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        title="Видалити атрибут?"
        message={deleting ? `Атрибут «${deleting.name}» та всі його значення буде видалено. Якщо він використовується товарами, сервер відмовить.` : ''}
        confirmLabel="Видалити" danger busy={saving}
        onConfirm={doDeleteAttr} onCancel={() => setDeleting(null)}
      />
      <ConfirmDialog
        open={!!deletingValue}
        title="Видалити значення?"
        message={deletingValue ? `Значення «${deletingValue.v.value}» буде видалено. Якщо воно використовується товарами, сервер відмовить.` : ''}
        confirmLabel="Видалити" danger busy={saving}
        onConfirm={doDeleteValue} onCancel={() => setDeletingValue(null)}
      />
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
        <Td>{attr.is_filterable ? <Badge tone="green">Так</Badge> : <Badge tone="gray">Ні</Badge>}</Td>
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




