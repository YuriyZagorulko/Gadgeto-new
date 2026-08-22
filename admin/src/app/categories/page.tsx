'use client';

import { useEffect, useMemo, useState } from 'react';
import { api } from '@/lib/api';
import { PageHeader, Button, Input, Select, Textarea, LoadingState, ErrorState, EmptyState, Modal, ConfirmDialog, useToast } from '@/components/ui';

type Cat = {
  id: number; parent_id: number | null; name: string; slug: string;
  is_active: boolean; sort_order: number; product_count?: number;
  children?: Cat[];
};

const EMPTY_FORM = { name: '', parent_id: '' as '' | number, description: '', sort_order: 0, is_active: true };

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

  const load = () => {
    setLoading(true);
    api.get<{ items: Cat[] }>('/categories')
      .then((d) => setCats(d.items || []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  /** Builds the tree from the flat API list. */
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
    // need raw fields; find in flat list
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
      setDeleting(null);
    }
  };

  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div>
      <PageHeader
        title="Категорії"
        actions={
          <div className="flex gap-2">
            <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Пошук за назвою..." />
            <Button onClick={() => openCreate()}>＋ Додати</Button>
          </div>
        }
      />

      {loading ? (
        <LoadingState label="Завантаження категорій..." />
      ) : tree.length === 0 ? (
        <EmptyState title="Категорій немає" hint="Створіть першу категорію." />
      ) : (
        <div className="bg-white border border-gray-200 rounded-lg divide-y divide-gray-100">
          {tree.filter(matches).map((c) => (
            <CatNode key={c.id} cat={c} depth={0} search={search}
              onEdit={openEdit} onDelete={setDeleting} onAddChild={openCreate} />
          ))}
        </div>
      )}

      <Modal open={modal.open} title={modal.editing ? `Редагування: ${modal.editing.name}` : 'Нова категорія'}
        onClose={() => setModal({ open: false, editing: null })}>
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Назва *</label>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} autoFocus />
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

function CatNode({ cat, depth, search, onEdit, onDelete, onAddChild }: {
  cat: Cat; depth: number; search: string;
  onEdit: (c: Cat) => void; onDelete: (c: Cat) => void; onAddChild: (c: Cat) => void;
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
          <Button size="sm" variant="secondary" onClick={() => onEdit(cat)}>Змінити</Button>
          <Button size="sm" variant="ghost" className="text-red-600" onClick={() => onDelete(cat)}>✕</Button>
        </div>
      </div>
      {children.map((c) => (
        <CatNode key={c.id} cat={c} depth={depth + 1} search={search}
          onEdit={onEdit} onDelete={onDelete} onAddChild={onAddChild} />
      ))}
    </div>
  );
}




