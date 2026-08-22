'use client';

import { useEffect, useState } from 'react';
import { api, qs } from '@/lib/api';
import { PageHeader, Button, Input, Textarea, Table, Th, Td, Pagination, LoadingState, ErrorState, EmptyState, Modal, ConfirmDialog, Badge, useToast } from '@/components/ui';

type Brand = {
  id: number; name: string; slug: string; description: string | null;
  logo: string | null; is_active: boolean; products_count: number;
};
type ListResp = { items: Brand[]; total: number; page: number; per_page: number; total_pages: number };

const EMPTY_FORM = { name: '', description: '', logo: '', is_active: true };

export default function BrandsPage() {
  const toast = useToast();
  const [search, setSearch] = useState('');
  const [applied, setApplied] = useState('');
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ListResp | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [modal, setModal] = useState<{ open: boolean; editing: Brand | null }>({ open: false, editing: null });
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<Brand | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError('');
    api.get<ListResp>('/brands' + qs({ page, per_page: 20, search: applied || undefined }))
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [page, applied, tick]);

  const reload = () => setTick((t) => t + 1);

  const openCreate = () => { setForm(EMPTY_FORM); setModal({ open: true, editing: null }); };
  const openEdit = (b: Brand) => {
    setForm({ name: b.name, description: b.description || '', logo: b.logo || '', is_active: b.is_active });
    setModal({ open: true, editing: b });
  };

  const save = async () => {
    if (!form.name.trim()) { toast.push('error', 'Вкажіть назву бренду'); return; }
    setSaving(true);
    const body = {
      name: form.name.trim(),
      description: form.description.trim() || null,
      logo: form.logo.trim() || null,
      is_active: form.is_active,
    };
    try {
      if (modal.editing) await api.put(`/brands/${modal.editing.id}`, body);
      else await api.post('/brands', body);
      toast.push('success', modal.editing ? 'Бренд оновлено' : 'Бренд створено');
      setModal({ open: false, editing: null });
      reload();
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally { setSaving(false); }
  };

  const doDelete = async () => {
    if (!deleting) return;
    try {
      await api.delete(`/brands/${deleting.id}`);
      toast.push('success', 'Бренд видалено');
      setDeleting(null); reload();
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
      setDeleting(null);
    }
  };

  return (
    <div>
      <PageHeader
        title="Бренди"
        actions={
          <div className="flex gap-2">
            <Input value={search} onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') { setPage(1); setApplied(search); } }}
              placeholder="Пошук..." />
            <Button variant="secondary" onClick={() => { setPage(1); setApplied(search); }}>Знайти</Button>
            <Button onClick={openCreate}>＋ Додати</Button>
          </div>
        }
      />

      {error && <ErrorState message={error} onRetry={reload} />}
      {!error && loading && !data && <LoadingState />}
      {!error && data?.items.length === 0 && (
        <EmptyState title="Брендів не знайдено" hint="Змініть умови пошуку або додайте новий бренд." />
      )}
      {data && data.items.length > 0 && (
        <>
          <Table head={<tr><Th>Назва</Th><Th>Slug</Th><Th>Товарів</Th><Th>Статус</Th><Th className="w-40"></Th></tr>}>
            {data.items.map((b) => (
              <tr key={b.id} className="hover:bg-gray-50">
                <Td>
                  <div className="flex items-center gap-2">
                    {b.logo && (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={b.logo} alt="" className="w-8 h-8 rounded object-contain bg-gray-50 border border-gray-100" />
                    )}
                    <span className="font-medium">{b.name}</span>
                  </div>
                  {b.description && <div className="text-xs text-gray-400 line-clamp-1 max-w-md mt-0.5">{b.description}</div>}
                </Td>
                <Td className="text-xs text-gray-400">{b.slug}</Td>
                <Td>{b.products_count}</Td>
                <Td><Badge tone={b.is_active ? 'green' : 'gray'}>{b.is_active ? 'Активний' : 'Неактивний'}</Badge></Td>
                <Td>
                  <div className="flex gap-1">
                    <Button size="sm" variant="secondary" onClick={() => openEdit(b)}>Змінити</Button>
                    <Button size="sm" variant="ghost" className="text-red-600" onClick={() => setDeleting(b)}>✕</Button>
                  </div>
                </Td>
              </tr>
            ))}
          </Table>
          <div className="mt-4">
            <Pagination page={data.page} pages={data.total_pages} total={data.total} onPage={setPage} />
          </div>
        </>
      )}

      <Modal open={modal.open} title={modal.editing ? `Редагування: ${modal.editing.name}` : 'Новий бренд'}
        onClose={() => setModal({ open: false, editing: null })}>
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Назва *</label>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} autoFocus />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Опис</label>
            <Textarea rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">URL логотипа</label>
            <Input value={form.logo} onChange={(e) => setForm({ ...form, logo: e.target.value })} placeholder="https://..." />
          </div>
          {/* is_active toggle */}
          <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
            <input type="checkbox" className="rounded" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
            Активний
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setModal({ open: false, editing: null })}>Скасувати</Button>
            <Button loading={saving} onClick={save}>{modal.editing ? 'Зберегти' : 'Створити'}</Button>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        title="Видалити бренд?"
        message={deleting ? `Бренд «${deleting.name}» буде видалено. Якщо до нього прив'язані товари, сервер відмовить у видаленні.` : ''}
        confirmLabel="Видалити" danger busy={saving}
        onConfirm={doDelete} onCancel={() => setDeleting(null)}
      />
    </div>
  );
}


