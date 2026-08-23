'use client';

import { useEffect, useState } from 'react';
import { api, qs } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import { PageHeader, Button, Input, Textarea, Table, Th, Td, Pagination, LoadingState, ErrorState, EmptyState, Modal, ConfirmDialog, Badge, useToast } from '@/components/ui';

type Supplier = {
  id: number; code: string; name: string; enabled: boolean;
  products_count: number; categories_count: number; attributes_count: number;
  imports_count: number; last_import_at: string | null;
};
type ListResp = { items: Supplier[]; total: number; page: number; per_page: number };
type Detail = Supplier & { config?: Record<string, unknown> | null; imports_by_status?: Record<string, number>; config_json?: unknown };

const EMPTY_FORM = { code: '', name: '', enabled: true, config: '' };

export default function SuppliersPage() {
  const toast = useToast();
  const [search, setSearch] = useState('');
  const [applied, setApplied] = useState('');
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ListResp | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tick, setTick] = useState(0);

  const [modal, setModal] = useState<{ open: boolean; editing: Supplier | null }>({ open: false, editing: null });
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<Supplier | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError('');
    api.get<ListResp>('/suppliers' + qs({ page, per_page: 20, q: applied || undefined }))
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [page, applied, tick]);

  const reload = () => setTick((t) => t + 1);

  const openCreate = () => { setForm(EMPTY_FORM); setModal({ open: true, editing: null }); };
  const openEdit = async (s: Supplier) => {
    try {
      const d = await api.get<Detail>(`/suppliers/${s.id}`);
      setForm({
        code: d.code, name: d.name, enabled: d.enabled,
        config: d.config ? JSON.stringify(d.config, null, 2) : '',
      });
      setModal({ open: true, editing: s });
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    }
  };

  const showDetail = async (s: Supplier) => {
    try {
      const d = await api.get<Detail>(`/suppliers/${s.id}`);
      setDetail(d);
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    }
  };

  const save = async () => {
    if (!form.code.trim() || !form.name.trim()) { toast.push('error', 'Код та назва обов\'язкові'); return; }
    let config: unknown = null;
    if (form.config.trim()) {
      try { config = JSON.parse(form.config); }
      catch { toast.push('error', 'Конфігурація — не валідний JSON'); return; }
    }
    setSaving(true);
    const body = { code: form.code.trim(), name: form.name.trim(), enabled: form.enabled, config };
    try {
      if (modal.editing) await api.put(`/suppliers/${modal.editing.id}`, body);
      else await api.post('/suppliers', body);
      toast.push('success', modal.editing ? 'Постачальника оновлено' : 'Постачальника створено');
      setModal({ open: false, editing: null }); reload();
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally { setSaving(false); }
  };

  const doDelete = async () => {
    if (!deleting) return;
    try {
      await api.delete(`/suppliers/${deleting.id}`);
      toast.push('success', 'Постачальника видалено');
      setDeleting(null); reload();
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
      setDeleting(null);
    }
  };

  return (
    <div>
      <PageHeader
        title="Постачальники"
        actions={
          <div className="flex gap-2">
            <Input value={search} onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') { setPage(1); setApplied(search); } }}
              placeholder="Пошук за кодом або назвою..." />
            <Button variant="secondary" onClick={() => { setPage(1); setApplied(search); }}>Знайти</Button>
            <Button onClick={openCreate}>＋ Додати</Button>
          </div>
        }
      />

      {error && <ErrorState message={error} onRetry={reload} />}
      {!error && loading && !data && <LoadingState />}
      {!error && data?.items.length === 0 && <EmptyState title="Постачальників не знайдено" />}
      {data && data.items.length > 0 && (
        <>
          <Table head={<tr><Th>Код</Th><Th>Назва</Th><Th>Товарів</Th><Th>Категорій</Th><Th>Атрибутів</Th><Th>Імпортів</Th><Th>Останній імпорт</Th><Th>Стан</Th><Th className="w-40"></Th></tr>}>
            {data.items.map((s) => (
              <tr key={s.id} className="hover:bg-gray-50">
                <Td><button onClick={() => showDetail(s)} className="font-mono text-xs text-blue-600 hover:underline">{s.code}</button></Td>
                <Td className="font-medium">{s.name}</Td>
                <Td>{s.products_count}</Td>
                <Td>{s.categories_count}</Td>
                <Td>{s.attributes_count}</Td>
                <Td>{s.imports_count}</Td>
                <Td className="whitespace-nowrap text-xs text-gray-500">{formatDateTime(s.last_import_at)}</Td>
                <Td><Badge tone={s.enabled ? 'green' : 'gray'}>{s.enabled ? 'Активний' : 'Вимкнений'}</Badge></Td>
                <Td>
                  <div className="flex gap-1">
                    <Button size="sm" variant="secondary" onClick={() => openEdit(s)}>Змінити</Button>
                    <Button size="sm" variant="ghost" className="text-red-600" onClick={() => setDeleting(s)}>✕</Button>
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

      <Modal open={modal.open} title={modal.editing ? `Редагування: ${modal.editing.name}` : 'Новий постачальник'}
        onClose={() => setModal({ open: false, editing: null })}>
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Код *</label>
            <Input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} autoFocus placeholder="напр., itlink" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Назва *</label>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Конфігурація (JSON)</label>
            <Textarea rows={5} value={form.config} onChange={(e) => setForm({ ...form, config: e.target.value })}
              className="font-mono text-xs" placeholder='{"key": "value"}' />
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
            <input type="checkbox" className="rounded" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
            Активний
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setModal({ open: false, editing: null })}>Скасувати</Button>
            <Button loading={saving} onClick={save}>{modal.editing ? 'Зберегти' : 'Створити'}</Button>
          </div>
        </div>
      </Modal>

      {/* Detail modal */}
      <Modal open={!!detail} title={detail ? `Постачальник: ${detail.name}` : ''} onClose={() => setDetail(null)} wide>
        {detail && (
          <div className="space-y-4 text-sm">
            <div className="grid grid-cols-2 gap-3">
              <div><span className="text-gray-500">Код:</span> <span className="font-mono">{detail.code}</span></div>
              <div>
                <span className="text-gray-500">Стан:</span>{' '}
                <Badge tone={detail.enabled ? 'green' : 'gray'}>{detail.enabled ? 'Активний' : 'Вимкнений'}</Badge>
              </div>
              <div><span className="text-gray-500">Товарів:</span> {detail.products_count}</div>
              <div><span className="text-gray-500">Останній імпорт:</span> {formatDateTime(detail.last_import_at)}</div>
            </div>
            {detail.imports_by_status && Object.keys(detail.imports_by_status).length > 0 && (
              <div>
                <div className="text-gray-500 mb-1">Імпорти за статусами:</div>
                <div className="flex gap-2 flex-wrap">
                  {Object.entries(detail.imports_by_status).map(([k, v]) => (
                    <Badge key={k} tone="blue">{k}: {v}</Badge>
                  ))}
                </div>
              </div>
            )}
            {detail.config && (
              <div>
                <div className="text-gray-500 mb-1">Конфігурація:</div>
                <pre className="bg-gray-50 border border-gray-100 rounded p-3 text-xs overflow-x-auto max-h-60">
                  {JSON.stringify(detail.config, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        title="Видалити постачальника?"
        message={deleting ? `Постачальника «${deleting.name}» буде видалено разом з його довідниками. Якщо існують пов'язані товари або імпорти, сервер відмовить.` : ''}
        confirmLabel="Видалити" danger busy={saving}
        onConfirm={doDelete} onCancel={() => setDeleting(null)}
      />
    </div>
  );
}



