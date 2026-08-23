'use client';

import { useEffect, useState } from 'react';
import { api, qs } from '@/lib/api';
import { formatDateTime, USER_ROLE_LABELS, USER_STATUS_LABELS } from '@/lib/format';
import { PageHeader, Button, Input, Select, Table, Th, Td, Badge, Pagination, LoadingState, ErrorState, EmptyState, Modal, ConfirmDialog, useToast } from '@/components/ui';

type Row = {
  id: number; email: string; full_name: string | null; phone: string | null;
  role: string; status: string;
  email_verified_at: string | null; last_login_at: string | null;
  login_count: number; created_at: string; orders_count: number;
};
type Detail = Row & { orders_total?: number };
type ListResp = { items: Row[]; total: number; page: number; per_page: number };

const ROLES = ['CUSTOMER', 'STAFF', 'ADMIN'];
const STATUSES = ['ACTIVE', 'INACTIVE', 'PENDING', 'BANNED'];
const roleTone = (r: string): 'blue' | 'yellow' | 'gray' => (r === 'ADMIN' ? 'blue' : r === 'STAFF' ? 'yellow' : 'gray');
const statusTone = (s: string): 'green' | 'red' | 'yellow' | 'gray' => (s === 'ACTIVE' ? 'green' : s === 'BANNED' ? 'red' : s === 'PENDING' ? 'yellow' : 'gray');

/** Sortable column descriptor */
type SortCol = 'email' | 'name' | 'phone' | 'role' | 'status' | 'orders' | 'last_login' | 'registered';
const SORTABLE: { key: SortCol; label: string }[] = [
  { key: 'email', label: 'Email' },
  { key: 'name', label: "Ім'я" },
  { key: 'phone', label: 'Телефон' },
  { key: 'role', label: 'Роль' },
  { key: 'status', label: 'Статус' },
  { key: 'orders', label: 'Замовлень' },
  { key: 'last_login', label: 'Останній вхід' },
  { key: 'registered', label: 'Зареєстровано' },
];

export default function UsersPage() {
  const toast = useToast();
  const [q, setQ] = useState('');
  const [appliedQ, setAppliedQ] = useState('');
  const [role, setRole] = useState('');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState<SortCol | null>(null);
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [data, setData] = useState<ListResp | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tick, setTick] = useState(0);

  const [detail, setDetail] = useState<Detail | null>(null);
  const [editRole, setEditRole] = useState('');
  const [editStatus, setEditStatus] = useState('');
  const [saving, setSaving] = useState(false);

  const [deleteTarget, setDeleteTarget] = useState<Row | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError('');
    api.get<ListResp>('/users' + qs({
      page, per_page: 20, q: appliedQ || undefined,
      role: role || undefined, status: status || undefined,
      sort_by: sortBy || undefined, sort_order: sortOrder,
    }))
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [page, appliedQ, role, status, sortBy, sortOrder, tick]);

  /** Click handler for sortable column headers. */
  const handleSort = (col: SortCol) => {
    if (sortBy === col) {
      setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(col);
      setSortOrder('desc');
    }
    setPage(1);
  };

  /** Render a sort arrow for a column header. */
  const sortArrow = (col: SortCol): string => {
    if (sortBy !== col) return '';
    return sortOrder === 'asc' ? ' ↑' : ' ↓';
  };

  const openDetail = async (u: Row) => {
    try {
      const d = await api.get<Detail>(`/users/${u.id}`);
      setDetail(d); setEditRole(d.role); setEditStatus(d.status);
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    }
  };

  const saveUser = async () => {
    if (!detail) return;
    setSaving(true);
    try {
      await api.patch(`/users/${detail.id}`, {
        role: editRole !== detail.role ? editRole : undefined,
        status: editStatus !== detail.status ? editStatus : undefined,
      });
      toast.push('success', 'Користувача оновлено');
      setDetail(null); setTick((t) => t + 1);
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally { setSaving(false); }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await api.delete(`/users/${deleteTarget.id}`);
      toast.push('success', `Користувача ${deleteTarget.email} видалено.`);
      setDeleteTarget(null);
      // If we deleted the only item on the current page, go back one page
      if (data && data.items.length === 1 && page > 1) {
        setPage(page - 1);
      }
      setTick((t) => t + 1);
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
      setDeleteTarget(null);
    } finally { setDeleting(false); }
  };

  return (
    <div>
      <PageHeader title="Користувачі" />

      <div className="bg-white border border-gray-200 rounded-lg p-3 mb-4 flex flex-wrap gap-3 items-end">
        <div className="w-64">
          <label className="block text-xs text-gray-500 mb-1">Пошук</label>
          <Input value={q} onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { setPage(1); setAppliedQ(q); } }}
            placeholder="Email, ім'я або телефон..." />
        </div>
        <div className="w-44">
          <label className="block text-xs text-gray-500 mb-1">Роль</label>
          <Select value={role} onChange={(e) => { setPage(1); setRole(e.target.value); }}>
            <option value="">Усі ролі</option>
            {ROLES.map((r) => <option key={r} value={r}>{USER_ROLE_LABELS[r]}</option>)}
          </Select>
        </div>
        <div className="w-44">
          <label className="block text-xs text-gray-500 mb-1">Статус</label>
          <Select value={status} onChange={(e) => { setPage(1); setStatus(e.target.value); }}>
            <option value="">Усі статуси</option>
            {STATUSES.map((s) => <option key={s} value={s}>{USER_STATUS_LABELS[s]}</option>)}
          </Select>
        </div>
        <Button variant="secondary" onClick={() => { setPage(1); setAppliedQ(q); }}>Застосувати</Button>
        <Button variant="ghost" onClick={() => { setQ(''); setAppliedQ(''); setRole(''); setStatus(''); setPage(1); }}>Скинути</Button>
      </div>

      {error && <ErrorState message={error} onRetry={() => setTick((t) => t + 1)} />}
      {!error && loading && !data && <LoadingState label="Завантаження користувачів..." />}
      {!error && data?.items.length === 0 && <EmptyState title="Користувачів не знайдено" />}
      {data && data.items.length > 0 && (
        <>
          <Table head={<tr>{SORTABLE.map(({ key, label }) => (
                <Th key={key}>
                  <button type="button" onClick={() => handleSort(key)}
                    className="cursor-pointer select-none hover:text-gray-900 transition-colors w-full text-left font-medium">
                    {label}<span className="text-blue-500 text-xs ml-1">{sortArrow(key)}</span>
                  </button>
                </Th>
              ))}<Th className="text-right">Дії</Th></tr>}>
            {data.items.map((u) => (
              <tr key={u.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => openDetail(u)}>
                <Td className="font-medium text-blue-600">{u.email}</Td>
                <Td>{u.full_name || '—'}</Td>
                <Td className="text-sm whitespace-nowrap">{u.phone || '—'}</Td>
                <Td><Badge tone={roleTone(u.role)}>{USER_ROLE_LABELS[u.role] || u.role}</Badge></Td>
                <Td><Badge tone={statusTone(u.status)}>{USER_STATUS_LABELS[u.status] || u.status}</Badge></Td>
                <Td>{u.orders_count}</Td>
                <Td className="whitespace-nowrap text-xs text-gray-500">{formatDateTime(u.last_login_at)}</Td>
                <Td className="whitespace-nowrap text-xs text-gray-500">{formatDateTime(u.created_at)}</Td>
                  <Td className="text-right">
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); setDeleteTarget(u); }}
                      className="text-red-500 hover:text-red-700 hover:bg-red-50 rounded p-1 transition-colors"
                      title="Видалити користувача"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                        <path fillRule="evenodd" d="M8.75 1A2.75 2.75 0 006 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 10.23 1.482l.149-.022.841 10.518A2.75 2.75 0 007.596 19h4.807a2.75 2.75 0 002.742-2.53l.841-10.52.149.023a.75.75 0 00.23-1.482A41.03 41.03 0 0014 4.193V3.75A2.75 2.75 0 0011.25 1h-2.5zM10 4c-.84 0-1.673.025-2.5.075V3.75c0-.69.56-1.25 1.25-1.25h2.5c.69 0 1.25.56 1.25 1.25v.325C11.673 4.025 10.84 4 10 4zM8.58 7.72a.75.75 0 00-1.5.06l.3 7.5a.75.75 0 101.5-.06l-.3-7.5zm4.34.06a.75.75 0 10-1.5-.06l-.3 7.5a.75.75 0 101.5.06l.3-7.5z" clipRule="evenodd" />
                      </svg>
                    </button>
                  </Td>
              </tr>
            ))}
          </Table>
          <div className="mt-4">
            <Pagination page={data.page} pages={Math.max(1, Math.ceil(data.total / data.per_page))} total={data.total} onPage={setPage} />
          </div>
        </>
      )}

      {/* User detail / edit modal */}
      <Modal open={!!detail} title={detail ? `Користувач: ${detail.email}` : ''} onClose={() => setDetail(null)}>
        {detail && (
          <div className="space-y-4 text-sm">
            <div className="grid grid-cols-2 gap-2">
              <div><span className="text-gray-500">ID:</span> {detail.id}</div>
              <div><span className="text-gray-500">Ім'я:</span> {detail.full_name || '—'}</div>
              <div><span className="text-gray-500">Телефон:</span> {detail.phone || '—'}</div>
              <div><span className="text-gray-500">Замовлень:</span> {detail.orders_count}{detail.orders_total !== undefined ? ` (${(detail.orders_total / 100).toLocaleString('uk-UA')} ₴)` : ''}</div>
              <div><span className="text-gray-500">Входів:</span> {detail.login_count}</div>
              <div><span className="text-gray-500">Останній вхід:</span> {formatDateTime(detail.last_login_at)}</div>
              <div><span className="text-gray-500">Email підтверджено:</span> {detail.email_verified_at ? formatDateTime(detail.email_verified_at) : '—'}</div>
              <div><span className="text-gray-500">Зареєстровано:</span> {formatDateTime(detail.created_at)}</div>
            </div>

            <div className="border-t border-gray-100 pt-3 grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Роль</label>
                <Select value={editRole} onChange={(e) => setEditRole(e.target.value)}>
                  {ROLES.map((r) => <option key={r} value={r}>{USER_ROLE_LABELS[r]}</option>)}
                </Select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Статус</label>
                <Select value={editStatus} onChange={(e) => setEditStatus(e.target.value)}>
                  {STATUSES.map((s) => <option key={s} value={s}>{USER_STATUS_LABELS[s]}</option>)}
                </Select>
              </div>
            </div>

            <p className="text-xs text-gray-400">
              Паролі та інші секретні дані не зберігаються й не відображаються. Зміна власної ролі/статусу заборонена.
            </p>

            <div className="flex justify-end gap-2 pt-1">
              <Button variant="secondary" onClick={() => setDetail(null)}>Скасувати</Button>
              <Button loading={saving} disabled={editRole === detail.role && editStatus === detail.status} onClick={saveUser}>
                Зберегти
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* Delete confirmation dialog */}
      <ConfirmDialog
        open={!!deleteTarget}
        title="Видалити користувача?"
        message={
          deleteTarget
            ? `Ви впевнені, що хочете видалити користувача ${deleteTarget.email}? Цю дію неможливо скасувати.`
            : ''
        }
        confirmLabel="Видалити"
        danger
        busy={deleting}
        onConfirm={confirmDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}


