'use client';

import { useEffect, useState } from 'react';
import { api, qs } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import { PageHeader, Button, Badge, LoadingState, ErrorState } from '@/components/ui';

type Stats = {
  channel_id: number;
  channel_code: string;
  channel_enabled: boolean;
  total_products: number;
  total_listings_with_channel: number;
  published: number;
  ready: number;
  blocked: number;
  errors: number;
  last_sync: { started_at: string | null; finished_at: string | null; status: string } | null;
};

type TaxonomyStats = {
  categories: number;
  attributes: number;
  values: number;
};

const statusLabel = (s: string) => {
  switch (s) {
    case 'succeeded': return { label: 'Успішно', tone: 'green' as const };
    case 'running': return { label: 'Виконується', tone: 'blue' as const };
    case 'failed': return { label: 'Помилка', tone: 'red' as const };
    case 'partial': return { label: 'Частково', tone: 'yellow' as const };
    default: return { label: '—', tone: 'gray' as const };
  }
};

function fmtDuration(seconds?: number | null): string {
  if (seconds == null || seconds < 0) return '—';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  const parts: string[] = [];
  if (h > 0) parts.push(`${h}г`);
  if (m > 0 || h > 0) parts.push(`${m}хв`);
  parts.push(`${s}с`);
  return parts.join(' ');
}

function StatCard({ label, value, tone = 'gray' }: { label: string; value: string | number; tone?: 'gray' | 'green' | 'red' | 'blue' | 'yellow' }) {
  const colors: Record<string, string> = {
    gray: 'bg-gray-50 text-gray-700 border-gray-200',
    green: 'bg-green-50 text-green-700 border-green-200',
    red: 'bg-red-50 text-red-700 border-red-200',
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
    yellow: 'bg-yellow-50 text-yellow-800 border-yellow-200',
  };
  return (
    <div className={`rounded-lg border p-4 ${colors[tone] || colors.gray}`}>
      <div className="text-2xl font-bold">{typeof value === 'number' ? value.toLocaleString('uk-UA') : value}</div>
      <div className="text-sm mt-1 opacity-80">{label}</div>
    </div>
  );
}

export default function RozetkaOverviewPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [taxData, setTaxData] = useState<TaxonomyStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [taxRefreshing, setTaxRefreshing] = useState(false);
  const [taxResult, setTaxResult] = useState('');
  const [runStatus, setRunStatus] = useState<any>(null);

  const load = () => {
    setLoading(true); setError('');
    Promise.all([
      api.get<Stats>('/export/channels/rozetka/stats'),
      api.get<{ items: TaxonomyStats }>('/export/channels/rozetka/taxonomy'),
    ])
      .then(([s, t]) => { setStats(s); setTaxData(t.items); })
      .catch((e) => setError(e.message || 'Не вдалось завантажити статистику'))
      .finally(() => setLoading(false));
  };

  const loadRunStatus = () => {
    api.get<any>('/export/channels/rozetka/taxonomy/status')
      .then((d) => {
        if (d && d.status) d.status = d.status.toLowerCase();
        setRunStatus(d);
      })
      .catch(() => {});
  };

  useEffect(() => { load(); loadRunStatus(); }, []);

  const isRunActive = runStatus && (runStatus.status === 'running' || runStatus.status === 'queued');

  // Poll for run status while a refresh is active
  useEffect(() => {
    if (!isRunActive) return;
    const interval = setInterval(() => { loadRunStatus(); }, 5000);
    return () => clearInterval(interval);
  }, [isRunActive]);

  const handleRefreshTaxonomy = async () => {
    setTaxRefreshing(true); setTaxResult('');
    try {
      const res = await api.post<{ run_id: number }>('/export/channels/rozetka/taxonomy/refresh');
      setTaxResult('Оновлення таксономії запущено у фоновому режимі');
      loadRunStatus();
    } catch (e: any) {
      setTaxResult(e.message || 'Помилка');
    } finally {
      setTaxRefreshing(false);
    }
  };

  if (loading) return <LoadingState label="Завантаження статистики..." />;
  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />;
  if (!stats) return <ErrorState message="Немає даних про канал Rozetka" />;

  const lastSync = stats.last_sync;
  const syncInfo = lastSync ? statusLabel(lastSync.status) : null;

  return (
    <div>
      <PageHeader title="Rozetka" />

      {/* Channel status */}
      <div className="mb-4">
        <Badge tone={stats.channel_enabled ? 'green' : 'gray'}>
          {stats.channel_enabled ? 'Канал увімкнено' : 'Канал вимкнено'}
        </Badge>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard label="Товарів у каталозі" value={stats.total_products} tone="blue" />
        <StatCard label="Опубліковано" value={stats.published} tone="green" />
        <StatCard label="Готові" value={stats.ready} tone="blue" />
        <StatCard label="Заблоковано" value={stats.blocked} tone="yellow" />
        {stats.errors > 0 && <StatCard label="Помилок синхронізації" value={stats.errors} tone="red" />}
        <StatCard label="Усього лістингів" value={stats.total_listings_with_channel} tone="gray" />
      </div>

      {/* Taxonomy stats */}
      <div className="bg-white border border-gray-200 rounded-lg p-4 mb-6">
        <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">Таксономія Rozetka</h3>
        {taxData ? (
          <div className="grid grid-cols-3 gap-4 mb-3">
            <div>
              <div className="text-lg font-semibold">{taxData.categories.toLocaleString('uk-UA')}</div>
              <div className="text-xs text-gray-500">Категорій</div>
            </div>
            <div>
              <div className="text-lg font-semibold">{taxData.attributes.toLocaleString('uk-UA')}</div>
              <div className="text-xs text-gray-500">Атрибутів</div>
            </div>
            <div>
              <div className="text-lg font-semibold">{taxData.values.toLocaleString('uk-UA')}</div>
              <div className="text-xs text-gray-500">Значень</div>
            </div>
          </div>
        ) : (
          <p className="text-gray-400 italic text-sm mb-3">Таксономія не завантажена</p>
        )}

        {/* Active run status */}
        {isRunActive && runStatus && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-3">
            <div className="flex items-center gap-2 mb-2">
              <span className="inline-block w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
              <span className="text-sm font-medium text-blue-800">Оновлення таксономії виконується</span>
            </div>
            <div className="grid grid-cols-3 gap-3 text-sm">
              <div>
                <span className="text-gray-500">Категорії:</span>{' '}
                {runStatus.categories.total} всього, {runStatus.categories.processed} оброблено
              </div>
              <div>
                <span className="text-gray-500">Атрибути:</span>{' '}
                {runStatus.attributes.total}
              </div>
              <div>
                <span className="text-gray-500">Значення:</span>{' '}
                {runStatus.values.total}
              </div>
              {runStatus.errors > 0 && (
                <div className="text-red-600">
                  <span className="text-gray-500">Помилки:</span> {runStatus.errors}
                </div>
              )}
            </div>
            {runStatus.current_operation && (
              <div className="text-xs text-gray-600 mt-1">{runStatus.current_operation}</div>
            )}
          </div>
        )}

        {/* Last run result */}
        {runStatus && !isRunActive && runStatus.status !== 'never' && (
          <div className="flex items-center gap-2 text-sm text-gray-600 mb-3">
            <Badge tone={runStatus.status === 'succeeded' ? 'green' : runStatus.status === 'partial' ? 'yellow' : 'red'}>
              {runStatus.status === 'succeeded' ? 'Успішно' : runStatus.status === 'partial' ? 'Частково' : 'Помилка'}
            </Badge>
            {runStatus.finished_at && <span>Завершено: {formatDateTime(runStatus.finished_at)}</span>}
            {runStatus.duration_seconds != null && <span>Тривалість: {fmtDuration(runStatus.duration_seconds)}</span>}
            {runStatus.errors > 0 && <span className="text-red-600">Помилок: {runStatus.errors}</span>}
          </div>
        )}

        <div className="flex items-center gap-3">
          <Button onClick={handleRefreshTaxonomy} disabled={taxRefreshing || isRunActive}>
            {taxRefreshing ? 'Оновлення...' : isRunActive ? 'Виконується...' : 'Оновити таксономію'}
          </Button>
          <a href="/export/rozetka/taxonomy" className="text-sm text-blue-600 hover:underline">
            Детальніше →
          </a>
        </div>
        {taxResult && (
          <p className={`text-sm mt-2 ${taxResult.startsWith('Помилка') ? 'text-red-600' : 'text-green-600'}`}>
            {taxResult}
          </p>
        )}
        {!taxResult && taxData && taxData.categories === 0 && (
          <p className="text-xs text-gray-400 mt-1">
            Для завантаження таксономії потрібні облікові дані API Rozetka (будуть додані у наступних фазах).
          </p>
        )}
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-3">
                <Button disabled>Валідувати каталог</Button>
        <Button disabled>Синхронізувати зараз</Button>
        <a
          href="/export/rozetka/mapping"
          className="inline-flex items-center justify-center rounded-md bg-white border border-gray-300 px-3 py-1.5 text-sm text-gray-900 hover:bg-gray-50"
        >
          Маппинг
        </a>
        <a
          href="/export/rozetka/taxonomy"
          className="inline-flex items-center justify-center rounded-md bg-white border border-gray-300 px-3 py-1.5 text-sm text-gray-900 hover:bg-gray-50"
        >
          Таксономия
        </a>
        <a
          href="/export/rozetka/products"
          className="inline-flex items-center justify-center rounded-md bg-white border border-gray-300 px-3 py-1.5 text-sm text-gray-900 hover:bg-gray-50"
        >
          Переглянути товари
        </a>
      </div>
      <p className="text-xs text-gray-400 mt-2">
        Валідація та синхронізація стануть доступні в наступних фазах.
      </p>
    </div>
  );
}