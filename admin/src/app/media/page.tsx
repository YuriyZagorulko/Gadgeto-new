'use client';

import { useCallback, useEffect, useState } from 'react';
import { api, qs } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import {
  PageHeader, Button, Input, Select, Table, Th, Td, Badge,
  Pagination, LoadingState, ErrorState, EmptyState, ConfirmDialog,
  Modal, useToast,
} from '@/components/ui';

type MediaRow = {
  id: number;
  filename: string;
  storage_path: string;
  url: string;
  mime_type: string;
  size_bytes: number;
  width: number | null;
  height: number | null;
  sha256: string | null;
  created_at: string;
  updated_at: string;
  usage_count: number;
  status: string;
};

type MediaDetail = {
  media: MediaRow;
  usage: Array<{ product_id: number; is_primary: boolean; product_name: string }>;
};

type ListResp = { items: MediaRow[]; total: number; page: number; pages: number };
type StatsResp = {
  total: number; total_size: number; used: number; unused: number;
  orphaned: number; orphaned_size: number;
};

function formatSize(bytes: number): string {
  if (bytes === 0) return '0 Б'; const k = 1024;
  const sizes = ['Б', 'КБ', 'МБ', 'ГБ'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function mimeShort(mime: string): string {
  const map: Record<string, string> = { 'image/jpeg': 'JPEG', 'image/png': 'PNG', 'image/webp': 'WebP', 'image/gif': 'GIF' };
  return map[mime] || (mime.startsWith('image/') ? 'Зобр.' : mime.split('/').pop() || mime);
}

const TYPES = [
  { value: '', label: 'Усі типи' }, { value: 'image/jpeg', label: 'JPEG' },
  { value: 'image/png', label: 'PNG' }, { value: 'image/webp', label: 'WebP' },
  { value: 'image/gif', label: 'GIF' },
];

const STATUS_FILTERS = [
  { value: 'all', label: 'Усі' }, { value: 'used', label: 'Використовується' },
  { value: 'unused', label: 'Не використовується' }, { value: 'missing', label: 'Файл відсутній' },
];

const SORT_KEYS = ['created_at', 'filename', 'size_bytes', 'mime_type', 'width', 'height', 'usage_count'];
const PER_PAGE_OPTIONS = [25, 50, 100];

export default function MediaPage() {
  const toast = useToast();
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(25);
  const [search, setSearch] = useState('');
  const [appliedSearch, setAppliedSearch] = useState('');
  const [mimeFilter, setMimeFilter] = useState('');
  const [usageFilter, setUsageFilter] = useState('all');
  const [sort, setSort] = useState('created_at');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');
  const [data, setData] = useState<ListResp | null>(null);
  const [stats, setStats] = useState<StatsResp | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tick, setTick] = useState(0);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [detail, setDetail] = useState<MediaDetail | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<MediaRow[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmCleanup, setConfirmCleanup] = useState(false);

  const fetchData = useCallback(() => {
    setLoading(true); setError('');
    api.get<ListResp>('/media' + qs({
      page, per_page: perPage, search: appliedSearch || undefined,
      mime_type: mimeFilter || undefined, usage: usageFilter, sort, order,
    }))
      .then((d) => setData(d))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [page, perPage, appliedSearch, mimeFilter, usageFilter, sort, order]);

  useEffect(() => { fetchData(); }, [fetchData, tick]);
  useEffect(() => {
    api.get<StatsResp>('/media/stats').then((d) => setStats(d)).catch(() => {});
  }, [tick]);

  const openDetail = async (mediaId: number) => {
    try { const d = await api.get<MediaDetail>('/media/' + mediaId); setDetail(d); }
    catch (e: unknown) { toast.push('error', (e as Error).message); }
  };

  const toggleSort = (key: string) => {
    if (sort === key) setOrder(order === 'asc' ? 'desc' : 'asc');
    else { setSort(key); setOrder('desc'); }
    setPage(1);
  };

  const toggleSelect = (id: number) => {
    setSelected((prev) => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  };

  const doDeleteSelected = async () => {
    if (!confirmDelete) return; setBusy(true);
    try {
      const ids = confirmDelete.map((m) => m.id);
      const res = await api.post<{ deleted: number; skipped: number; errors: string[] }>('/media/bulk-delete', { ids });
      toast.push('success', 'Видалено: ' + res.deleted + (res.skipped > 0 ? ', пропущено: ' + res.skipped : ''));
      setConfirmDelete(null); setSelected(new Set()); setTick((t) => t + 1);
    } catch (e: unknown) { toast.push('error', (e as Error).message); }
    finally { setBusy(false); }
  };

  const doCleanup = async () => {
    setBusy(true);
    try {
      const d = await api.post<{ deleted: number; deleted_size: number; errors: string[] }>('/media/cleanup-unused', {});
      toast.push('success', 'Очищено ' + d.deleted + ' файлів (' + formatSize(d.deleted_size) + ')');
      setConfirmCleanup(false); setTick((t) => t + 1);
    } catch (e: unknown) { toast.push('error', (e as Error).message); }
    finally { setBusy(false); }
  };

  const statusBadge = (s: string) => {
    const tones: Record<string, 'green' | 'gray' | 'red' | 'blue' | 'yellow'> = { used: 'green', unused: 'gray', missing: 'red' };
    const labels: Record<string, string> = { used: 'Використовується', unused: 'Не використовується', missing: 'Файл відсутній' };
    return <Badge tone={tones[s] || 'gray'}>{labels[s] || s}</Badge>;
  };

  return (
    <div>
      <PageHeader title="Медіа" actions={
        <div className="flex gap-2 items-center">
          {stats && (
            <span className="text-xs text-gray-500">
              {stats.total} файлів · {formatSize(stats.total_size)}
              {stats.unused > 0 && ' · ' + stats.unused + ' невикористаних'}
            </span>
          )}
          <Button variant="secondary" onClick={() => setConfirmCleanup(true)}>Очистити невикористані</Button>
          <Button variant="secondary" onClick={() => setTick((t) => t + 1)}>Оновити</Button>
        </div>
      } />

      <div className="bg-white border border-gray-200 rounded-lg p-3 mb-4 flex flex-wrap gap-3 items-end">
        <div className="w-56">
          <label className="block text-xs text-gray-500 mb-1">Пошук</label>
          <Input value={search} onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { setPage(1); setAppliedSearch(search); } }}
            placeholder="Назва файлу..." />
        </div>
        <div className="w-36">
          <label className="block text-xs text-gray-500 mb-1">Тип</label>
          <Select value={mimeFilter} onChange={(e) => { setPage(1); setMimeFilter(e.target.value); }}>
            {TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </Select>
        </div>
        <div className="w-44">
          <label className="block text-xs text-gray-500 mb-1">Статус</label>
          <Select value={usageFilter} onChange={(e) => { setPage(1); setUsageFilter(e.target.value); }}>
            {STATUS_FILTERS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
          </Select>
        </div>
        <Button variant="secondary" onClick={() => { setPage(1); setAppliedSearch(search); }}>Застосувати</Button>
        <Button variant="ghost" onClick={() => {
          setSearch(''); setAppliedSearch(''); setMimeFilter(''); setUsageFilter('all'); setPage(1);
        }}>Скинути</Button>
      </div>

      {error && <ErrorState message={error} onRetry={() => fetchData()} />}
      {!error && loading && !data && <LoadingState label="Завантаження медіа..." />}
      {!error && data && data.items.length === 0 && <EmptyState title="Медіа не знайдено" />}

      {selected.size > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 mb-4 flex items-center gap-4">
          <span className="text-sm font-medium text-blue-800">Вибрано: {selected.size}</span>
          <Button size="sm" variant="danger" onClick={() => {
            const items = data?.items.filter((m) => selected.has(m.id)) || [];
            setConfirmDelete(items);
          }}>Видалити вибране</Button>
          <Button size="sm" variant="ghost" onClick={() => setSelected(new Set())}>Скасувати вибір</Button>
        </div>
      )}

      {!error && data && data.items.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="px-3 py-2.5 text-left w-10">
                  <input type="checkbox" className="accent-blue-600"
                    checked={data.items.length > 0 && selected.size === data.items.length}
                    onChange={() => {
                      if (selected.size === data.items.length) setSelected(new Set());
                      else setSelected(new Set(data.items.map((m) => m.id)));
                    }} />
                </th>
                <th className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-gray-500">Превью</th>
                <th className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-gray-500 cursor-pointer hover:text-gray-900" onClick={() => toggleSort('filename')}>
                  Файл {sort === 'filename' ? (order === 'asc' ? '↑' : '↓') : ''}
                </th>
                <th className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-gray-500 cursor-pointer hover:text-gray-900" onClick={() => toggleSort('mime_type')}>
                  Тип {sort === 'mime_type' ? (order === 'asc' ? '↑' : '↓') : ''}
                </th>
                <th className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-gray-500 cursor-pointer hover:text-gray-900" onClick={() => toggleSort('size_bytes')}>
                  Розмір {sort === 'size_bytes' ? (order === 'asc' ? '↑' : '↓') : ''}
                </th>
                <th className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-gray-500 cursor-pointer hover:text-gray-900" onClick={() => toggleSort('usage_count')}>
                  Використання {sort === 'usage_count' ? (order === 'asc' ? '↑' : '↓') : ''}
                </th>
                <th className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-gray-500">Статус</th>
                <th className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-gray-500 cursor-pointer hover:text-gray-900" onClick={() => toggleSort('created_at')}>
                  Додано {sort === 'created_at' ? (order === 'asc' ? '↑' : '↓') : ''}
                </th>
                <th className="px-3 py-2.5 text-left w-16"></th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((m) => (
                <tr key={m.id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="px-3 py-2.5"><input type="checkbox" className="accent-blue-600"
                    checked={selected.has(m.id)} onChange={() => toggleSelect(m.id)} /></td>
                  <td className="px-3 py-2.5">
                    <div className="w-10 h-10 bg-gray-100 rounded overflow-hidden">
                      {m.mime_type.startsWith('image/') ? (
                        <img src={m.url} alt={m.filename} className="w-full h-full object-cover" loading="lazy" />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-gray-400 text-xs">?</div>
                      )}
                    </div>
                  </td>
                  <td className="px-3 py-2.5 text-sm font-medium truncate max-w-[200px]" title={m.filename}>{m.filename}</td>
                  <td className="px-3 py-2.5"><Badge tone="gray">{mimeShort(m.mime_type)}</Badge></td>
                  <td className="px-3 py-2.5 text-sm text-gray-600 tabular-nums whitespace-nowrap">{formatSize(m.size_bytes)}</td>
                  <td className="px-3 py-2.5"><Badge tone={m.usage_count > 0 ? 'green' : 'gray'}>{m.usage_count > 0 ? 'Так' : 'Ні'}</Badge></td>
                  <td className="px-3 py-2.5">{statusBadge(m.status || (m.usage_count > 0 ? 'used' : 'unused'))}</td>
                  <td className="px-3 py-2.5 text-sm text-gray-500 whitespace-nowrap">{formatDateTime(m.created_at)}</td>
                  <td className="px-3 py-2.5">
                    <button onClick={() => openDetail(m.id)} className="text-gray-400 hover:text-gray-700 text-lg" title="Деталі">⋯</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && (
        <div className="mt-4">
          <Pagination page={data.page} pages={data.pages} total={data.total}
            onPage={(p) => setPage(p)} pageSize={perPage}
            onPageSizeChange={(n) => { setPerPage(n); setPage(1); }}
            pageSizeOptions={PER_PAGE_OPTIONS} />
        </div>
      )}

      <Modal open={!!detail} title={detail?.media.filename || 'Деталі'} onClose={() => setDetail(null)} wide>
        {detail && (
          <div className="space-y-4">
            <div className="flex gap-4">
              {detail.media.mime_type.startsWith('image/') ? (
                <img src={detail.media.url} alt={detail.media.filename} className="w-48 h-48 object-cover rounded border" />
              ) : (
                <div className="w-48 h-48 bg-gray-100 flex items-center justify-center rounded border"><span className="text-4xl text-gray-400">📄</span></div>
              )}
              <div className="flex-1 text-sm space-y-1.5">
                <div><span className="text-gray-500">Файл:</span> {detail.media.filename}</div>
                <div><span className="text-gray-500">Тип:</span> {detail.media.mime_type}</div>
                <div><span className="text-gray-500">Розмір:</span> {formatSize(detail.media.size_bytes)}</div>
                {detail.media.width && detail.media.height && <div><span className="text-gray-500">Розміри:</span> {detail.media.width}×{detail.media.height}</div>}
                <div><span className="text-gray-500">Створено:</span> {formatDateTime(detail.media.created_at)}</div>
                <div><span className="text-gray-500">Шлях:</span> <code className="text-xs bg-gray-100 px-1 rounded">{detail.media.storage_path}</code></div>
                {detail.media.sha256 && <div><span className="text-gray-500">SHA-256:</span> <code className="text-xs bg-gray-100 px-1 rounded">{detail.media.sha256.substring(0, 16)}...</code></div>}
              </div>
            </div>
            <div><h3 className="font-medium text-sm text-gray-700 mb-2">Використання</h3>
              {detail.usage.length === 0 ? (
                <p className="text-sm text-gray-400 italic">Не використовується</p>
              ) : (
                <div className="space-y-1">
                  {detail.usage.map((u) => (
                    <div key={u.product_id} className="text-sm bg-gray-50 rounded px-3 py-1.5 flex items-center gap-2">
                      <Badge tone="green">Товар</Badge>
                      <span>{u.product_name}</span>
                      <span className="text-xs text-gray-400">(ID: {u.product_id})</span>
                      {u.is_primary && <Badge tone="blue">Осн.</Badge>}
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="flex justify-end gap-2 pt-2 border-t">
              {detail.usage.length === 0 && (
                <Button variant="danger" onClick={async () => {
                  await api.delete('/media/' + detail.media.id);
                  toast.push('success', 'Файл видалено'); setDetail(null); setTick((t) => t + 1);
                }}>Видалити файл</Button>
              )}
              <Button variant="secondary" onClick={() => setDetail(null)}>Закрити</Button>
            </div>
          </div>
        )}
      </Modal>

      <ConfirmDialog open={!!confirmDelete} title="Видалити файли?"
        message={confirmDelete ? (confirmDelete.length === 1 ? 'Файл буде остаточно видалено.' : 'Буде видалено ' + confirmDelete.length + ' файлів. Використовувані файли будуть пропущені.') : ''}
        confirmLabel="Видалити" danger busy={busy} onConfirm={doDeleteSelected}
        onCancel={() => setConfirmDelete(null)} />

      <ConfirmDialog open={confirmCleanup} title="Очистити невикористані медіа?"
        message="Будуть видалені всі локальні медіафайли, які не використовуються жодним товаром."
        confirmLabel="Очистити" danger busy={busy} onConfirm={doCleanup}
        onCancel={() => setConfirmCleanup(false)} />
    </div>
  );
}
