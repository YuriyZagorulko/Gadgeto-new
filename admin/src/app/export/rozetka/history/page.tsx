'use client';

import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { api, qs } from '@/lib/api';
import {
  PageHeader, Button, Select, Badge,
  Pagination, LoadingState, ErrorState, EmptyState, ConfirmDialog, useToast,
} from '@/components/ui';

type ExportRun = {
  id: number; channel_id: number; run_type: string; status: string;
  started_at: string | null; finished_at: string | null; created_at: string;
  total_count: number; processed_count: number;
  created_count: number; updated_count: number;
  failed_count: number; skipped_count: number;
  current_stage: string | null;
  cancel_requested: boolean; triggered_by_user_id: number | null;
  duration: number | null;
};

type ListResp = { items: ExportRun[]; total: number; page: number; per_page: number };

const STATUSES = ['queued', 'running', 'succeeded', 'partial', 'failed', 'cancelled'];
const STATUS_LABELS: Record<string, string> = {
  queued: 'У черзі', running: 'Виконується', succeeded: 'Успішно',
  partial: 'З помилками', failed: 'Помилка', cancelled: 'Скасовано',
};
const STATUS_TONE: Record<string, 'gray' | 'blue' | 'green' | 'yellow' | 'red'> = {
  queued: 'gray', running: 'blue', succeeded: 'green',
  partial: 'yellow', failed: 'red', cancelled: 'gray',
};

const nf = new Intl.NumberFormat('uk-UA');

function fmtDate(ts?: string | null): string {
  if (!ts) return '—';
  const d = new Date(ts);
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleDateString('uk-UA', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

function fmtTime(ts?: string | null): string {
  if (!ts) return '—';
  const d = new Date(ts);
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function fmtDuration(seconds?: number | null): string {
  if (!seconds && seconds !== 0) return '—';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  const parts: string[] = [];
  if (h > 0) parts.push(`${h}г`);
  if (m > 0) parts.push(`${m}хв`);
  parts.push(`${s}с`);
  return parts.join(' ');
}

function activeStatus(s: string): boolean {
  return ['queued', 'running'].includes((s || '').toLowerCase());
}

export default function ExportHistoryPage() {
  const toast = useToast();
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ListResp | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState('');
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [confirmDel, setConfirmDel] = useState<number | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    const p: Record<string, string | number> = { page, per_page: 25 };
    if (statusFilter) p.status = statusFilter;
    api.get<ListResp>('/export/channels/rozetka/history' + qs(p))
      .then((d) => setData(d))
      .catch((e) => setError(e.message || 'Помилка завантаження'))
      .finally(() => setLoading(false));
  }, [page, statusFilter]);

  useEffect(() => { load(); }, [load]);

  const handleDelete = async () => {
    if (!confirmDel) return;
    setDeletingId(confirmDel);
    try {
      await api.delete('/export/channels/rozetka/history/' + confirmDel);
      toast.push('success', 'Експорт видалено');
      load();
    } catch (e: any) {
      toast.push('error', e.message || 'Помилка видалення');
    } finally {
      setDeletingId(null);
      setConfirmDel(null);
    }
  };

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.per_page)) : 1;

  return (
    <div>
      <PageHeader title="Історія експортів Rozetka" />

      <div className="flex items-center gap-3 mb-4">
        <Select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="w-40"
        >
          <option value="">Усі статуси</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>{STATUS_LABELS[s] || s}</option>
          ))}
        </Select>
        {data && (
          <span className="text-sm text-gray-500">
            {nf.format(data.total)} записів
          </span>
        )}
        <Link href="/export/rozetka/settings" className="ml-auto text-sm text-blue-600 hover:text-blue-800 font-medium">
          ← Налаштування експорту
        </Link>
      </div>

      {loading ? (
        <LoadingState label="Завантаження історії..." />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : !data || data.items.length === 0 ? (
        <EmptyState title="Немає експортів" hint="Експорт на Rozetka ще не запускався." />
      ) : (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="text-xs text-gray-500 uppercase bg-gray-50">
              <tr>
                <th className="p-2 text-left">ID</th>
                <th className="p-2 text-left">Дата</th>
                <th className="p-2 text-left">Статус</th>
                <th className="p-2 text-right">Всього</th>
                <th className="p-2 text-right">Оброблено</th>
                <th className="p-2 text-right">Створено</th>
                <th className="p-2 text-right">Оновлено</th>
                <th className="p-2 text-right">Пропущено</th>
                <th className="p-2 text-right">Помилки</th>
                <th className="p-2 text-left">Тривалість</th>
                <th className="p-2 text-left">Дії</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {data.items.map((r) => {
                const s = (r.status || '').toLowerCase();
                const isActive = activeStatus(s);
                return (
                  <tr key={r.id} className={`hover:bg-gray-50 ${isActive ? 'bg-blue-50' : ''}`}>
                    <td className="p-2">
                      <Link href={`/export/rozetka/history/${r.id}`} className="text-blue-600 hover:text-blue-800 font-mono">
                        #{r.id}
                      </Link>
                    </td>
                    <td className="p-2">
                      <div>{fmtDate(r.started_at || r.created_at)}</div>
                      <div className="text-gray-400 text-xs">{fmtTime(r.started_at || r.created_at)}</div>
                    </td>
                    <td className="p-2">
                      <Badge tone={STATUS_TONE[s] || 'gray'}>{STATUS_LABELS[s] || s}</Badge>
                      {r.cancel_requested && <span className="ml-1 text-xs text-gray-400">(скасування)</span>}
                    </td>
                    <td className="p-2 text-right">{nf.format(r.total_count || 0)}</td>
                    <td className="p-2 text-right">{nf.format(r.processed_count || 0)}</td>
                    <td className="p-2 text-right">{nf.format(r.created_count || 0)}</td>
                    <td className="p-2 text-right">{nf.format(r.updated_count || 0)}</td>
                    <td className="p-2 text-right">{nf.format(r.skipped_count || 0)}</td>
                    <td className="p-2 text-right">
                      {(r.failed_count || 0) > 0
                        ? <span className="text-red-600 font-medium">{nf.format(r.failed_count)}</span>
                        : nf.format(0)}
                    </td>
                    <td className="p-2 text-xs text-gray-500">{fmtDuration(r.duration)}</td>
                    <td className="p-2">
                      <div className="flex gap-2">
                        <Link
                          href={`/export/rozetka/history/${r.id}`}
                          className="text-blue-600 hover:text-blue-800 text-xs font-medium"
                        >
                          Деталі
                        </Link>
                        {!isActive && (
                          <button
                            onClick={() => setConfirmDel(r.id)}
                            disabled={deletingId === r.id}
                            className="text-red-600 hover:text-red-800 text-xs font-medium disabled:opacity-50"
                          >
                            {deletingId === r.id ? '...' : 'Видалити'}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          <div className="p-4 border-t border-gray-100">
            <Pagination
              page={page}
              pages={totalPages}
              total={data.total}
              onPage={(p) => setPage(p)}
            />
          </div>
        </div>
      )}

      <ConfirmDialog
        open={!!confirmDel}
        title="Видалити експорт?"
        message={`Видалити експорт #${confirmDel}? Товари та список Rozetka не зміняться.`}
        confirmLabel="Видалити"
        danger
        onConfirm={handleDelete}
        onCancel={() => setConfirmDel(null)}
      />
    </div>
  );
}
