'use client';

import { useEffect, useState } from 'react';
import { api, qs } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import {
  PageHeader, Table, Th, Td, Badge, Button, Input,
  LoadingState, ErrorState, Pagination, Select,
} from '@/components/ui';

type ListingRow = {
  id: number;
  product_id: number;
  publication_status: string;
  sync_status: string;
  external_id: string | null;
  last_synced_at: string | null;
  last_error_type: string | null;
  last_error_message: string | null;
  product_name: string;
  product_sku: string;
};

type ListResp = { items: ListingRow[]; total: number; page: number; per_page: number };

const pubBadge: Record<string, { tone: 'gray' | 'green' | 'blue' | 'yellow'; label: string }> = {
  published: { tone: 'green', label: 'Опубліковано' },
  ready: { tone: 'blue', label: 'Готовий' },
  draft: { tone: 'gray', label: 'Чернетка' },
  disabled: { tone: 'yellow', label: 'Вимкнено' },
};

const syncBadge: Record<string, { tone: 'gray' | 'green' | 'red' | 'blue'; label: string }> = {
  success: { tone: 'green', label: 'Успішно' },
  syncing: { tone: 'blue', label: 'Синхронізація' },
  error: { tone: 'red', label: 'Помилка' },
  idle: { tone: 'gray', label: 'Очікує' },
};

export default function RozetkaProductsPage() {
  const [rows, setRows] = useState<ListingRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [q, setQ] = useState('');
  const [appliedQ, setAppliedQ] = useState('');
  const [pubFilter, setPubFilter] = useState('');
  const [syncFilter, setSyncFilter] = useState('');

  const pages = Math.max(1, Math.ceil(total / perPage));

  const load = () => {
    setLoading(true); setError('');
    api.get<ListResp>('/export/channels/rozetka/listings' + qs({
      page, per_page: perPage,
      q: appliedQ || undefined,
      publication_status: pubFilter || undefined,
      sync_status: syncFilter || undefined,
    }))
      .then((d) => { setRows(d.items); setTotal(d.total); })
      .catch((e) => setError(e.message || 'Не вдалось завантажити список'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [page, perPage, appliedQ, pubFilter, syncFilter]);
return (
    <div>
      <PageHeader title="Товари Rozetka" />

      <div className="flex flex-wrap items-end gap-3 mb-4">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Пошук</label>
          <Input value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="Назва або SKU" className="w-48"
            onKeyDown={(e) => { if (e.key === 'Enter') { setAppliedQ(q); setPage(1); } }} />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Статус публікації</label>
          <Select value={pubFilter}
            onChange={(e) => { setPubFilter(e.target.value); setPage(1); }}>
            <option value="">Усі</option>
            <option value="published">Опубліковано</option>
            <option value="ready">Готовий</option>
            <option value="draft">Чернетка</option>
            <option value="disabled">Вимкнено</option>
          </Select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Статус синхронізації</label>
          <Select value={syncFilter}
            onChange={(e) => { setSyncFilter(e.target.value); setPage(1); }}>
            <option value="">Усі</option>
            <option value="success">Успішно</option>
            <option value="syncing">Синхронізація</option>
            <option value="error">Помилка</option>
            <option value="idle">Очікує</option>
          </Select>
        </div>
        <Button onClick={() => { setAppliedQ(q); setPage(1); }}>Пошук</Button>
      </div>

      {loading ? <LoadingState label="Завантаження товарів..." /> :
       error ? <ErrorState message={error} onRetry={load} /> : (
        <>
          <Table head={<>
            <Th className="w-12">ID</Th><Th>Товар</Th><Th>SKU</Th>
            <Th>Публікація</Th><Th>Синхронізація</Th><Th>Зовнішній ID</Th>
            <Th>Остання синхр.</Th><Th>Помилка</Th>
          </>}>
            {rows.length === 0 ? (
              <tr><td colSpan={8} className="p-6 text-center text-gray-400">
                Немає лістингів</td></tr>
            ) : rows.map((r) => {
              const pb = pubBadge[r.publication_status] ||
                { tone: 'gray' as const, label: r.publication_status };
              const sb = syncBadge[r.sync_status] ||
                { tone: 'gray' as const, label: r.sync_status };
              return (
                <tr key={r.id} className="hover:bg-gray-50">
                  <Td className="text-xs">{r.product_id}</Td>
                  <Td className="max-w-60 truncate">
                    <span title={r.product_name}>{r.product_name || '—'}</span></Td>
                  <Td className="text-xs font-mono">{r.product_sku || '—'}</Td>
                  <Td><Badge tone={pb.tone}>{pb.label}</Badge></Td>
                  <Td><Badge tone={sb.tone}>{sb.label}</Badge></Td>
                  <Td className="text-xs font-mono">{r.external_id || '—'}</Td>
                  <Td className="text-xs">
                    {r.last_synced_at ? formatDateTime(r.last_synced_at) : '—'}</Td>
                  <Td className="max-w-32 truncate text-xs text-red-600">
                    <span title={r.last_error_message || ''}>
                    {r.sync_status === 'error' ? (r.last_error_type || 'помилка') : '—'}
                    </span></Td>
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