'use client';

import { useEffect, useState } from 'react';
import { api, qs } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import {
  PageHeader, Button, Input, Select, Table, Th, Td,
  Badge, LoadingState, ErrorState, Pagination, useToast,
} from '@/components/ui';

type Kind = 'categories' | 'attributes' | 'values';

const TABS: { key: Kind; label: string }[] = [
  { key: 'categories', label: 'Категорії' },
  { key: 'attributes', label: 'Атрибути' },
  { key: 'values', label: 'Значення атрибутів' },
];

type Row = {
  id: number; internal_id: number; internal_name: string;
  external_id: string | null; external_name: string | null;
  status: string; confidence: number | null; source: string;
  created_at: string; updated_at: string;
};
type ListResp = { items: Row[]; total: number; page: number; per_page: number };

const statusBadge: Record<string, { tone: 'gray' | 'green' | 'blue' | 'yellow'; label: string }> = {
  accepted: { tone: 'green', label: 'Прийнято' },
  proposed: { tone: 'blue', label: 'Запропоновано' },
  excluded: { tone: 'yellow', label: 'Виключено' },
};

export default function RozetkaMappingPage() {
  const toast = useToast();
  const [kind, setKind] = useState<Kind>('categories');
  const [rows, setRows] = useState<Row[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [q, setQ] = useState(''); const [appliedQ, setAppliedQ] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  const pages = Math.max(1, Math.ceil(total / perPage));

  const load = () => {
    setLoading(true); setError('');
    api.get<ListResp>(`/export/channels/rozetka/mappings/${kind}` + qs({
      page, per_page: perPage,
      q: appliedQ || undefined,
      status: statusFilter || undefined,
    }))
      .then((d) => { setRows(d.items); setTotal(d.total); })
      .catch((e) => setError(e.message || 'Не вдалось завантажити'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [page, perPage, appliedQ, statusFilter, kind]);

  const handleDelete = async (id: number) => {
    try { await api.delete(`/export/channels/rozetka/mappings/${kind}/${id}`); load(); }
    catch (e: any) { toast.push('error', e.message); }
  };

  const handleStatusToggle = async (r: Row) => {
    const ns = r.status === 'accepted' ? 'excluded' : 'accepted';
    try { await api.put(`/export/channels/rozetka/mappings/${kind}/${r.id}`, { status: ns }); load(); }
    catch (e: any) { toast.push('error', e.message); }
  };

  return (
    <div>
      <PageHeader title="Маппінг Rozetka" />

      <div className="flex gap-1 mb-4 border-b border-gray-200">
        {TABS.map((t) => (
          <button key={t.key}
            onClick={() => { setKind(t.key); setPage(1); }}
            className={`px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
              kind === t.key
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-end gap-3 mb-4">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Пошук</label>
          <Input value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="Назва" className="w-48"
            onKeyDown={(e) => { if (e.key === 'Enter') { setAppliedQ(q); setPage(1); } }} />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Статус</label>
          <Select value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}>
            <option value="">Усі</option>
            <option value="proposed">Запропоновано</option>
            <option value="accepted">Прийнято</option>
            <option value="excluded">Виключено</option>
          </Select>
        </div>
        <Button onClick={() => { setAppliedQ(q); setPage(1); }}>Пошук</Button>
      </div>

      {loading ? <LoadingState /> : error ? <ErrorState message={error} onRetry={load} /> : (
        <>
          <Table head={<>
            <Th>Внутрішня</Th><Th>→ Зовнішня</Th><Th>Статус</Th>
            <Th>Впевненість</Th><Th>Джерело</Th><Th>Оновлено</Th><Th className="w-20">Дії</Th>
          </>}>
            {rows.length === 0 ? (
              <tr><td colSpan={7} className="p-6 text-center text-gray-400">Немає відповідностей</td></tr>
            ) : rows.map((r) => {
              const sb = statusBadge[r.status] || { tone: 'gray' as const, label: r.status };
              return (
                <tr key={r.id} className="hover:bg-gray-50">
                  <Td className="max-w-48 truncate font-medium">
                    <span title={r.internal_name}>{r.internal_name}</span></Td>
                  <Td className="max-w-48 truncate text-gray-600">
                    <span title={r.external_name || ''}>{r.external_name || '—'}</span></Td>
                  <Td><Badge tone={sb.tone}>{sb.label}</Badge></Td>
                  <Td className="text-xs">
                    {r.confidence != null ? `${Math.round(r.confidence * 100)}%` : '—'}</Td>
                  <Td className="text-xs">{r.source === 'auto' ? 'Авто' : 'Вручну'}</Td>
                  <Td className="text-xs whitespace-nowrap">
                    {r.updated_at ? formatDateTime(r.updated_at) : '—'}</Td>
                  <Td>
                    <div className="flex gap-1">
                      <button onClick={() => handleStatusToggle(r)}
                        className="text-xs text-blue-600 hover:underline">
                        {r.status === 'accepted' ? 'Викл.' : 'Прийн.'}</button>
                      <button onClick={() => handleDelete(r.id)}
                        className="text-xs text-red-600 hover:underline">Вид.</button>
                    </div>
                  </Td>
                </tr>
              );
            })}
          </Table>
          <Pagination page={page} pages={pages} total={total} onPage={setPage}
            onGoToPage={(p) => setPage(Math.min(Math.max(p, 1), pages))}
            pageSize={perPage}
            onPageSizeChange={(n) => { setPerPage(n); setPage(1); }} />
        </>
      )}
    </div>
  );
}