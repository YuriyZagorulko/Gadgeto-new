'use client';

import { useEffect, useState, useCallback } from 'react';
import { api, qs } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import {
  PageHeader, Button, Input, Select, Table, Th, Td, Badge,
  Pagination, LoadingState, ErrorState, EmptyState, Modal, ConfirmDialog,
  useToast,
} from '@/components/ui';

type Row = {
  id: number;
  product_id: number;
  product_name: string;
  product_sku: string | null;
  user_id: number | null;
  user_name: string | null;
  user_email: string | null;
  author_name: string;
  rating: number;
  content: string | null;
  status: string;
  created_at: string;
  moderated_at: string | null;
  moderator_name: string | null;
};

type ListResp = { items: Row[]; total: number; page: number; per_page: number };

const STATUS_OPTIONS = [
  { value: '', label: 'Усі статуси' },
  { value: 'PENDING', label: 'На модерації' },
  { value: 'APPROVED', label: 'Схвалено' },
  { value: 'REJECTED', label: 'Відхилено' },
];

const RATING_OPTIONS = [
  { value: '', label: 'Усі оцінки' },
  { value: '5', label: '★★★★★' },
  { value: '4', label: '★★★★☆' },
  { value: '3', label: '★★★☆☆' },
  { value: '2', label: '★★☆☆☆' },
  { value: '1', label: '★☆☆☆☆' },
];

const STATUS_LABELS: Record<string, string> = {
  PENDING: 'На модерації',
  APPROVED: 'Схвалено',
  REJECTED: 'Відхилено',
};

function statusTone(status: string): 'yellow' | 'green' | 'red' | 'gray' {
  if (status === 'PENDING') return 'yellow';
  if (status === 'APPROVED') return 'green';
  if (status === 'REJECTED') return 'red';
  return 'gray';
}

function StarRating({ rating }: { rating: number }) {
  return (
    <span className="text-amber-500" aria-label={`${rating} з 5 зірок`}>
      {'★'.repeat(rating)}
      {'☆'.repeat(5 - rating)}
    </span>
  );
}

export default function ReviewsPage() {
  const [q, setQ] = useState('');
  const [appliedQ, setAppliedQ] = useState('');
  const [status, setStatus] = useState('');
  const [rating, setRating] = useState('');
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ListResp | null>(null);
  const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
  const [tick, setTick] = useState(0);
  const toast = useToast();

  const [selectedReview, setSelectedReview] = useState<Row | null>(null);
  const [moderateId, setModerateId] = useState<number | null>(null);
  const [moderateStatus, setModerateStatus] = useState<'APPROVED' | 'REJECTED' | null>(null);
  const [moderateBusy, setModerateBusy] = useState(false);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);

  const fetchReviews = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    setError('');
    api.get<ListResp>('/reviews' + qs({
      page, per_page: 20,
      status: status || undefined,
      rating: rating || undefined,
      q: appliedQ || undefined,
    }))
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [page, status, rating, appliedQ]);

  useEffect(() => { fetchReviews(); }, [fetchReviews, tick]);

  const handleModerate = async () => {
    if (!moderateId || !moderateStatus) return;
    setModerateBusy(true);
        try {
      await api.patch(`/reviews/${moderateId}`, { status: moderateStatus });
      setModerateId(null);
      setModerateStatus(null);
      setError('');
      toast.push('success', moderateStatus === 'APPROVED' ? 'Відгук схвалено' : 'Відгук відхилено');
      setTick((t) => t + 1);
    } catch (e: any) { setError(e.message); toast.push('error', e.message); }
    finally { setModerateBusy(false); }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    setDeleteBusy(true);
    try {
            await api.delete(`/reviews/${deleteId}`);
      setDeleteId(null);
      if (selectedReview?.id === deleteId) setSelectedReview(null);
      setError('');
      toast.push('success', 'Відгук видалено');
      setTick((t) => t + 1);
    } catch (e: any) { setError(e.message); }
    finally { setDeleteBusy(false); }
  };

  return (
    <div>
      <PageHeader title="Відгуки" />
      <div className="bg-white border border-gray-200 rounded-lg p-3 mb-4 flex flex-wrap gap-3 items-end">
        <div className="w-64">
          <label className="block text-xs text-gray-500 mb-1">Пошук</label>
          <Input value={q} onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { setPage(1); setAppliedQ(q); } }}
            placeholder="Товар, користувач, текст..." />
        </div>
        <div className="w-48">
          <label className="block text-xs text-gray-500 mb-1">Статус</label>
          <Select value={status} onChange={(e) => { setPage(1); setStatus(e.target.value); }}>
            {STATUS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </Select>
        </div>
        <div className="w-40">
          <label className="block text-xs text-gray-500 mb-1">Оцінка</label>
          <Select value={rating} onChange={(e) => { setPage(1); setRating(e.target.value); }}>
            {RATING_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </Select>
        </div>
        <Button variant="secondary" onClick={() => { setPage(1); setAppliedQ(q); }}>Застосувати</Button>
        <Button variant="ghost" onClick={() => { setQ(''); setAppliedQ(''); setStatus(''); setRating(''); setPage(1); }}>Скинути</Button>
      </div>

      {error && <ErrorState message={error} onRetry={() => setTick((t) => t + 1)} />}
      {!error && loading && !data && <LoadingState label="Завантаження відгуків..." />}
      {!error && data?.items.length === 0 && <EmptyState title="Відгуків не знайдено" />}
      {data && data.items.length > 0 && (
        <>
          <Table head={(
            <tr><Th>Товар</Th><Th>Користувач</Th><Th>Оцінка</Th><Th>Відгук</Th><Th>Статус</Th><Th>Створено</Th><Th>Дії</Th></tr>
          )}>
            {data.items.map((r) => (
              <tr key={r.id} className="hover:bg-gray-50">
                <Td>
                  <button onClick={() => setSelectedReview(r)} className="text-blue-600 hover:underline font-medium text-left">{r.product_name}</button>
                  {r.product_sku && <div className="text-xs text-gray-400">SKU: {r.product_sku}</div>}
                </Td>
                <Td>{r.user_name || r.author_name}{r.user_email && <div className="text-xs text-gray-400">{r.user_email}</div>}</Td>
                <Td><StarRating rating={r.rating} /></Td>
                <Td className="max-w-xs"><div className="truncate text-sm text-gray-600">{r.content || '—'}</div></Td>
                <Td><Badge tone={statusTone(r.status)}>{STATUS_LABELS[r.status] || r.status}</Badge></Td>
                <Td className="whitespace-nowrap text-xs text-gray-500">{formatDateTime(r.created_at)}</Td>
                <Td>
                  <div className="flex gap-1">
                    {r.status === 'PENDING' && (
                      <>
                        <Button size="sm" variant="primary" onClick={() => { setModerateId(r.id); setModerateStatus('APPROVED'); }}>Схвалити</Button>
                        <Button size="sm" variant="danger" onClick={() => { setModerateId(r.id); setModerateStatus('REJECTED'); }}>Відхилити</Button>
                      </>
                    )}
                    <Button size="sm" variant="ghost" onClick={() => setSelectedReview(r)}>Деталі</Button>
                  </div>
                </Td>
              </tr>
            ))}
          </Table>
          <div className="mt-4">
            <Pagination page={data.page} pages={Math.max(1, Math.ceil(data.total / data.per_page))} total={data.total} onPage={(p) => setPage(p)} />
          </div>
        </>
      )}

      <Modal open={!!selectedReview} title="Деталі відгуку" onClose={() => setSelectedReview(null)} wide>
        {selectedReview && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div><div className="text-xs text-gray-500">Товар</div><div className="font-medium">{selectedReview.product_name}</div>{selectedReview.product_sku && <div className="text-sm text-gray-500">SKU: {selectedReview.product_sku}</div>}</div>
              <div><div className="text-xs text-gray-500">Користувач</div><div className="font-medium">{selectedReview.user_name || selectedReview.author_name}</div>{selectedReview.user_email && <div className="text-sm text-gray-500">{selectedReview.user_email}</div>}</div>
              <div><div className="text-xs text-gray-500">Оцінка</div><div><StarRating rating={selectedReview.rating} /></div></div>
              <div><div className="text-xs text-gray-500">Статус</div><Badge tone={statusTone(selectedReview.status)}>{STATUS_LABELS[selectedReview.status] || selectedReview.status}</Badge></div>
              <div><div className="text-xs text-gray-500">Створено</div><div>{formatDateTime(selectedReview.created_at)}</div></div>
              <div><div className="text-xs text-gray-500">Модерація</div><div>{selectedReview.moderated_at ? `${formatDateTime(selectedReview.moderated_at)} (${selectedReview.moderator_name || 'адмін'})` : '—'}</div></div>
            </div>
            <div><div className="text-xs text-gray-500 mb-1">Текст відгуку</div><div className="bg-gray-50 rounded p-3 text-sm whitespace-pre-wrap">{selectedReview.content || '—'}</div></div>
                        <div className="flex justify-between pt-2 border-t">
              <Button variant="danger" onClick={() => setDeleteId(selectedReview.id)}>Видалити</Button>
              {selectedReview.status === 'PENDING' && (
                <div className="flex gap-2">
                  <Button variant="secondary" onClick={() => { setModerateId(selectedReview.id); setModerateStatus('REJECTED'); }}>Відхилити</Button>
                  <Button variant="primary" onClick={() => { setModerateId(selectedReview.id); setModerateStatus('APPROVED'); }}>Схвалити</Button>
                </div>
              )}
              {selectedReview.status === 'APPROVED' && (
                <Button variant="danger" onClick={() => { setModerateId(selectedReview.id); setModerateStatus('REJECTED'); }}>Відхилити</Button>
              )}
              {selectedReview.status === 'REJECTED' && (
                <Button variant="primary" onClick={() => { setModerateId(selectedReview.id); setModerateStatus('APPROVED'); }}>Схвалити</Button>
              )}
            </div>
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={!!moderateId && !!moderateStatus}
        title={moderateStatus === 'APPROVED' ? 'Схвалити відгук?' : 'Відхилити відгук?'}
        message={moderateStatus === 'APPROVED' ? 'Відгук буде опублікований на сторінці товару.' : 'Відгук буде прихований і не з\'явиться на сторінці товару.'}
        confirmLabel={moderateStatus === 'APPROVED' ? 'Схвалити' : 'Відхилити'}
        danger={moderateStatus === 'REJECTED'}
        busy={moderateBusy}
        onConfirm={handleModerate}
        onCancel={() => { setModerateId(null); setModerateStatus(null); }}
      />

      <ConfirmDialog
        open={!!deleteId}
        title="Видалити відгук?"
        message="Цю дію неможливо скасувати. Відгук буде видалено остаточно."
        confirmLabel="Видалити"
        danger
        busy={deleteBusy}
        onConfirm={handleDelete}
        onCancel={() => setDeleteId(null)}
      />
    </div>
  );
}
