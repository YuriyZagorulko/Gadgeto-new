'use client';

import { useEffect, useState } from 'react';
import { api, qs } from '@/lib/api';
import { PageHeader, Button, Input, Select, Table, Th, Td, Pagination, LoadingState, ErrorState, EmptyState, Modal, ConfirmDialog, Badge, useToast } from '@/components/ui';

type Filter = {
  id: number; category_id: number | null; attribute_id: number;
  position: number; enabled: boolean;
  attribute_name: string; category_name: string | null;
};
type ListResp = { items: Filter[]; total: number; page: number; per_page: number };
type Opt = { id: number; name: string };

const EMPTY_FORM = { category_id: '' as '' | number, attribute_id: '' as '' | number, position: 0 };

export default function FiltersPage() {
  const toast = useToast();
  const [q, setQ] = useState('');
  const [appliedQ, setAppliedQ] = useState('');
  const [catId, setCatId] = useState('');
  const [enabled, setEnabled] = useState('');
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ListResp | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tick, setTick] = useState(0);

  const [cats, setCats] = useState<Opt[]>([]);
  const [attrs, setAttrs] = useState<Opt[]>([]);

  const [modal, setModal] = useState<{ open: boolean; editing: Filter | null }>({ open: false, editing: null });
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<Filter | null>(null);

  useEffect(() => {
    api.get<{ items: Opt[] }>('/categories').then((d) => setCats(d.items || [])).catch(() => {});
    api.get<ListResp & { items: Opt[] }>('/attributes' + qs({ per_page: 100 }))
      .then((d) => setAttrs((d.items as unknown as Opt[]) || [])).catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError('');
    api.get<ListResp>('/filters' + qs({
      page, per_page: 50,
      q: appliedQ || undefined, category_id: catId || undefined,
      enabled: enabled === '' ? undefined : enabled === '1',
    }))
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [page, appliedQ, catId, enabled, tick]);

  const reload = () => setTick((t) => t + 1);

  const save = async () => {
    if (form.attribute_id === '') { toast.push('error', 'Оберіть атрибут'); return; }
    setSaving(true);
    try {
      if (modal.editing) {
        await api.patch(`/filters/${modal.editing.id}`, {
          category_id: form.category_id === '' ? null : Number(form.category_id),
          position: Number(form.position),
        });
      } else {
        await api.post('/filters', {
          category_id: form.category_id === '' ? null : Number(form.category_id),
          attribute_id: Number(form.attribute_id),
          position: Number(form.position),
        });
      }
      toast.push('success', modal.editing ? 'Фільтр оновлено' : 'Фільтр додано');
      setModal({ open: false, editing: null }); reload();
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally { setSaving(false); }
  };

  const toggleEnabled = async (f: Filter) => {
    try {
      await api.patch(`/filters/${f.id}`, { enabled: !f.enabled });
      reload();
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    }
  };

  const doDelete = async () => {
    if (!deleting) return;
    try {
      await api.delete(`/filters/${deleting.id}`);
      toast.push('success', 'Фільтр видалено');
      setDeleting(null); reload();
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
      setDeleting(null);
    }
  };

  return (
    <div>
      <PageHeader
        title="Фільтри категорій"
        actions={
          <Button onClick={() => { setForm(EMPTY_FORM); setModal({ open: true, editing: null }); }}>＋ Додати фільтр</Button>
        }
      />
      <p className="text-xs text-gray-400 mb-3">
        Керування наявною системою фільтрів каталогу: який атрибут і в якій категорії показувати у блоці «Фільтри» на фронті.
      </p>

      <div className="bg-white border border-gray-200 rounded-lg p-3 mb-4 flex flex-wrap gap-3 items-end">
        <div className="w-56">
          <label className="block text-xs text-gray-500 mb-1">Атрибут (пошук)</label>
          <Input value={q} onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { setPage(1); setAppliedQ(q); } }} placeholder="Назва атрибута..." />
        </div>
        <div className="w-56">
          <label className="block text-xs text-gray-500 mb-1">Категорія</label>
          <Select value={catId} onChange={(e) => { setPage(1); setCatId(e.target.value); }}>
            <option value="">Усі категорії</option>
            {cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </Select>
        </div>
        <div className="w-40">
          <label className="block text-xs text-gray-500 mb-1">Стан</label>
          <Select value={enabled} onChange={(e) => { setPage(1); setEnabled(e.target.value); }}>
            <option value="">Усі</option>
            <option value="1">Увімкнені</option>
            <option value="0">Вимкнені</option>
          </Select>
        </div>
        <Button variant="secondary" onClick={() => { setPage(1); setAppliedQ(q); }}>Застосувати</Button>
        <Button variant="ghost" onClick={() => { setQ(''); setAppliedQ(''); setCatId(''); setEnabled(''); setPage(1); }}>Скинути</Button>
      </div>

      {error && <ErrorState message={error} onRetry={reload} />}
      {!error && loading && !data && <LoadingState />}
      {!error && data?.items.length === 0 && <EmptyState title="Фільтрів не знайдено" hint="Додайте фільтр або змініть умови." />}
      {data && data.items.length > 0 && (
        <>
          <Table head={<tr><Th>Категорія</Th><Th>Атрибут</Th><Th>Позиція</Th><Th>Стан</Th><Th className="w-40"></Th></tr>}>
            {data.items.map((f) => (
              <tr key={f.id} className="hover:bg-gray-50">
                <Td>{f.category_name || <span className="text-gray-400">— усі категорії —</span>}</Td>
                <Td className="font-medium">{f.attribute_name}</Td>
                <Td>{f.position}</Td>
                <Td>
                  <button onClick={() => toggleEnabled(f)} title="Перемкнути" className="cursor-pointer">
                    <Badge tone={f.enabled ? 'green' : 'gray'}>{f.enabled ? 'Увімкнено' : 'Вимкнено'}</Badge>
                  </button>
                </Td>
                <Td>
                  <div className="flex gap-1">
                    <Button size="sm" variant="secondary" onClick={() => {
                      setForm({ category_id: f.category_id ?? '', attribute_id: f.attribute_id, position: f.position });
                      setModal({ open: true, editing: f });
                    }}>Змінити</Button>
                    <Button size="sm" variant="ghost" className="text-red-600" onClick={() => setDeleting(f)}>✕</Button>
                  </div>
                </Td>
              </tr>
            ))}
          </Table>
          {data.total > data.per_page && (
            <div className="mt-4">
              <Pagination page={page} pages={Math.max(1, Math.ceil(data.total / data.per_page))} total={data.total} onPage={setPage} />
            </div>
          )}
        </>
      )}

      <Modal open={modal.open} title={modal.editing ? `Редагування фільтра: ${modal.editing.attribute_name}` : 'Новий фільтр'}
        onClose={() => setModal({ open: false, editing: null })}>
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Категорія</label>
            <Select value={form.category_id} onChange={(e) => setForm({ ...form, category_id: e.target.value === '' ? '' : Number(e.target.value) })}>
              <option value="">— Усі категорії —</option>
              {cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </Select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Атрибут *</label>
            <Select value={form.attribute_id} disabled={!!modal.editing}
              onChange={(e) => setForm({ ...form, attribute_id: e.target.value === '' ? '' : Number(e.target.value) })}>
              <option value="">Оберіть атрибут...</option>
              {attrs.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            </Select>
            {attrs.length >= 100 && !modal.editing && (
              <p className="text-xs text-gray-400 mt-1">Показано перші 100 атрибутів.</p>
            )}
          </div>
          <div className="w-32">
            <label className="block text-xs text-gray-500 mb-1">Позиція</label>
            <Input type="number" value={form.position} onChange={(e) => setForm({ ...form, position: Number(e.target.value) })} />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setModal({ open: false, editing: null })}>Скасувати</Button>
            <Button loading={saving} onClick={save}>{modal.editing ? 'Зберегти' : 'Створити'}</Button>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        title="Видалити фільтр?"
        message={deleting ? `Фільтр «${deleting.attribute_name}» для категорії «${deleting.category_name || 'усі'}» буде видалено.` : ''}
        confirmLabel="Видалити" danger busy={saving}
        onConfirm={doDelete} onCancel={() => setDeleting(null)}
      />
    </div>
  );
}



