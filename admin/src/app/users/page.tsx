'use client';

import { useEffect, useState } from 'react';
import { api, qs } from '@/lib/api';
import { formatDateTime, USER_ROLE_LABELS, USER_STATUS_LABELS } from '@/lib/format';
import { PageHeader, Button, Input, Select, Table, Th, Td, Badge, Pagination, LoadingState, ErrorState, EmptyState, Modal, useToast } from '@/components/ui';

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

export default function UsersPage() {
  const toast = useToast();
  const [q, setQ] = useState('');
  const [appliedQ, setAppliedQ] = useState('');
  const [role, setRole] = useState('');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ListResp | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tick, setTick] = useState(0);

  const [detail, setDetail] = useState<Detail | null>(null);
  const [editRole, setEditRole] = useState('');
  const [editStatus, setEditStatus] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError('');
    api.get<ListResp>('/users' + qs({
      page, per_page: 20, q: appliedQ || undefined,
      role: role || undefined, status: status || undefined,
    }))
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [page, appliedQ, role, status, tick]);

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
          <Table head={<tr><Th>Email</Th><Th>Ім'я</Th><Th>Телефон</Th><Th>Роль</Th><Th>Статус</Th><Th>Замовлень</Th><Th>Останній вхід</Th><Th>Зареєстровано</Th></tr>}>
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
    </div>
  );
}


