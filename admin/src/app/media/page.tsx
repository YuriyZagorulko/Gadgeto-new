'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
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
  created_at: string;
  usage_count: number;
};

type MediaDetail = {
  media: MediaRow;
  usage: Array<{
    product_id: number;
    is_primary: boolean;
    product_name: string;
  }>;
};

type ListResp = {
  items: MediaRow[];
  total: number;
  page: number;
  pages: number;
};

type StatsResp = {
  total: number;
  total_size: number;
  used: number;
  unused: number;
  orphaned: number;
  orphaned_size: number;
};

function formatSize(bytes: number): string {
  if (bytes === 0) return '0 Б';
  const k = 1024;
  const sizes = ['Б', 'КБ', 'МБ', 'ГБ'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function mimeIcon(mime: string): string {
  if (mime.startsWith('image/')) return '🖼️';
  if (mime.startsWith('video/')) return '🎬';
  return '📄';
}

const TYPES = [
  { value: '', label: 'Усі типи' },
  { value: 'image/jpeg', label: 'JPEG' },
  { value: 'image/png', label: 'PNG' },
  { value: 'image/webp', label: 'WebP' },
  { value: 'image/gif', label: 'GIF' },
];

const USAGE_FILTERS = [
  { value: 'all', label: 'Усі' },
  { value: 'used', label: 'Використовується' },
  { value: 'unused', label: 'Не використовується' },
];
export default function MediaPage() {
  const toast = useToast();
  const [page, setPage] = useState(1);
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
  const [detail, setDetail] = useState<MediaDetail | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<MediaRow | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmCleanup, setConfirmCleanup] = useState(false);
  const [cleanupStats, setCleanupStats] = useState<{ count: number; size: number } | null>(null);

  const fetchData = useCallback(() => {
    setLoading(true); setError('');
    api.get<ListResp>('/media' + qs({
      page, per_page: 24,
      search: appliedSearch || undefined,
      mime_type: mimeFilter || undefined,
      usage: usageFilter,
      sort, order,
    }))
      .then((d) => setData(d))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [page, appliedSearch, mimeFilter, usageFilter, sort, order]);

  useEffect(() => {
    fetchData();
  }, [fetchData, tick]);

  useEffect(() => {
    api.get<StatsResp>('/media/stats')
      .then((d) => setStats(d))
      .catch(() => {});
  }, [tick]);

  const openDetail = async (mediaId: number) => {
    try {
      const d = await api.get<MediaDetail>(`/media/${mediaId}`);
      setDetail(d);
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    }
  };

  const doDelete = async () => {
    if (!confirmDelete) return;
    setBusy(true);
    try {
      await api.delete(`/media/${confirmDelete.id}`);
      toast.push('success', 'Файл видалено');
      setConfirmDelete(null);
      setTick((t) => t + 1);
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const checkCleanup = async () => {
    setBusy(true);
    try {
      const d = await api.post<{ deleted: number; deleted_size: number; errors: string[] }>('/media/cleanup-unused', {});
      toast.push('success', `Очищено ${d.deleted} файлів (${formatSize(d.deleted_size)})`);
      if (d.errors.length > 0) {
        toast.push('error', `Помилки: ${d.errors.join(', ')}`);
      }
      setConfirmCleanup(false);
      setTick((t) => t + 1);
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally {
      setBusy(false);
    }
  };
return (
    <div>
      <PageHeader
        title="Медіа"
        actions={
          <div className="flex gap-2">
            {stats && (
              <span className="text-xs text-gray-500 self-center">
                {stats.total} файлів · {formatSize(stats.total_size)}
                {stats.unused > 0 && ` · ${stats.unused} невикористаних`}
                {stats.orphaned > 0 && ` · ${stats.orphaned} сиріт`}
              </span>
            )}
            <Button
              variant="secondary"
              onClick={async () => {
                setBusy(true);
                try {
                  const r = await api.get<StatsResp>('/media/stats');
                  setCleanupStats({ count: r.unused, size: r.total_size });
                  setConfirmCleanup(true);
                } catch (e: unknown) {
                  toast.push('error', (e as Error).message);
                } finally {
                  setBusy(false);
                }
              }}
              loading={busy && confirmCleanup === false}
            >
              🗑️ Очистити невикористані
            </Button>
            <Button variant="secondary" onClick={() => setTick((t) => t + 1)}>
              🔄 Оновити
            </Button>
          </div>
        }
      />

      <div className="bg-white border border-gray-200 rounded-lg p-3 mb-4 flex flex-wrap gap-3 items-end">
        <div className="w-56">
          <label className="block text-xs text-gray-500 mb-1">Пошук</label>
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { setPage(1); setAppliedSearch(search); } }}
            placeholder="Назва файлу..."
          />
        </div>
        <div className="w-36">
          <label className="block text-xs text-gray-500 mb-1">Тип</label>
          <Select value={mimeFilter} onChange={(e) => { setPage(1); setMimeFilter(e.target.value); }}>
            {TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </Select>
        </div>
        <div className="w-44">
          <label className="block text-xs text-gray-500 mb-1">Використання</label>
          <Select value={usageFilter} onChange={(e) => { setPage(1); setUsageFilter(e.target.value); }}>
            {USAGE_FILTERS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
          </Select>
        </div>
        <Button variant="secondary" onClick={() => { setPage(1); setAppliedSearch(search); }}>
          Застосувати
        </Button>
        <Button variant="ghost" onClick={() => {
          setSearch(''); setAppliedSearch(''); setMimeFilter('');
          setUsageFilter('all'); setPage(1);
        }}>
          Скинути
        </Button>
      </div>

      {error && <ErrorState message={error} onRetry={() => fetchData()} />}
      {!error && loading && !data && <LoadingState label="Завантаження медіа..." />}
      {!error && data?.items.length === 0 && <EmptyState title="Медіа не знайдено" />}
      {!error && data && data.items.length > 0 && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
            {data.items.map((m) => (
              <div
                key={m.id}
                className="bg-white border border-gray-200 rounded-lg overflow-hidden hover:shadow-md transition-shadow cursor-pointer group"
                onClick={() => openDetail(m.id)}
              >
                <div className="aspect-square bg-gray-100 flex items-center justify-center overflow-hidden">
                  {m.mime_type.startsWith('image/') ? (
                    <img
                      src={m.url}
                      alt={m.filename}
                      className="w-full h-full object-cover"
                      loading="lazy"
                    />
                  ) : (
                    <span className="text-3xl text-gray-400">{mimeIcon(m.mime_type)}</span>
                  )}
                </div>
                <div className="p-2">
                  <p className="text-xs truncate font-medium text-gray-800" title={m.filename}>
                    {m.filename}
                  </p>
                  <div className="flex items-center gap-1 mt-1">
                    <Badge tone={m.usage_count > 0 ? 'green' : 'gray'}>
                      {m.usage_count > 0 ? `${m.usage_count}` : '0'}
                    </Badge>
                    <span className="text-xs text-gray-400">{formatSize(m.size_bytes)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4">
            <Pagination
              page={data.page}
              pages={data.pages}
              total={data.total}
              onPage={(p) => setPage(p)}
              pageSize={24}
            />
          </div>
          </>
        )}

        {/* Detail modal */}
      <Modal open={!!detail} title={detail?.media.filename || 'Деталі'} onClose={() => setDetail(null)} wide>
        {detail && (
          <div className="space-y-4">
            <div className="flex gap-4">
              {detail.media.mime_type.startsWith('image/') ? (
                <img
                  src={detail.media.url}
                  alt={detail.media.filename}
                  className="w-48 h-48 object-cover rounded border"
                />
              ) : (
                <div className="w-48 h-48 bg-gray-100 flex items-center justify-center rounded border">
                  <span className="text-4xl text-gray-400">{mimeIcon(detail.media.mime_type)}</span>
                </div>
              )}
              <div className="flex-1 text-sm space-y-1.5">
                <div><span className="text-gray-500">Файл:</span> {detail.media.filename}</div>
                <div><span className="text-gray-500">Тип:</span> {detail.media.mime_type}</div>
                <div><span className="text-gray-500">Розмір:</span> {formatSize(detail.media.size_bytes)}</div>
                {detail.media.width && detail.media.height && (
                  <div><span className="text-gray-500">Розміри:</span> {detail.media.width}×{detail.media.height}</div>
                )}
                <div><span className="text-gray-500">Створено:</span> {formatDateTime(detail.media.created_at)}</div>
                <div><span className="text-gray-500">Шлях:</span> <code className="text-xs bg-gray-100 px-1 rounded">{detail.media.storage_path}</code></div>
              </div>
            </div>

            <div>
              <h3 className="font-medium text-sm text-gray-700 mb-2">Використання</h3>
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
                <Button
                  variant="danger"
                  onClick={() => {
                    const found = data?.items.find((m) => m.id === detail.media.id);
                    setConfirmDelete(found || null);
                    setDetail(null);
                  }}
                >
                  Видалити файл
                </Button>
              )}
              <Button variant="secondary" onClick={() => setDetail(null)}>
                Закрити
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* Delete confirmation */}
      <ConfirmDialog
        open={!!confirmDelete}
        title="Видалити файл?"
        message={
          confirmDelete
            ? `Файл «${confirmDelete.filename}» буде остаточно видалено. Цю дію неможливо скасувати.${
                confirmDelete.usage_count > 0
                  ? `\n\nУВАГА: файл використовується ${confirmDelete.usage_count} товарами!`
                  : ''
              }`
            : ''
        }
        confirmLabel="Видалити назавжди"
        danger
        busy={busy}
        onConfirm={doDelete}
        onCancel={() => setConfirmDelete(null)}
      />

      {/* Cleanup unused */}
      <ConfirmDialog
        open={confirmCleanup}
        title="Очистити невикористані медіа?"
        message={
          cleanupStats
            ? `Знайдено ${cleanupStats.count} невикористаних файлів (${formatSize(cleanupStats.size)}). Вони не мають жодних активних посилань. Видалити їх назавжди?`
            : 'Перевірка невикористаних файлів...'
        }
        confirmLabel="Очистити"
        danger
        busy={busy}
        onConfirm={checkCleanup}
        onCancel={() => setConfirmCleanup(false)}
      />
    </div>
  );
}