'use client';

import { useEffect, useState } from 'react';
import { api, qs } from '@/lib/api';
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

  useEffect(() => { load(); }, []);

  const handleRefreshTaxonomy = async () => {
    setTaxRefreshing(true); setTaxResult('');
    try {
      const res = await api.post<{ categories?: number }>('/export/channels/rozetka/taxonomy/refresh');
      setTaxResult(`Таксономію оновлено: +${res.categories ?? 0} категорій`);
    } catch (e: any) {
      setTaxResult(e.message || 'Помилка');
    } finally {
      setTaxRefreshing(false);
      load();
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
        <Button onClick={handleRefreshTaxonomy} disabled={taxRefreshing}>
          {taxRefreshing ? 'Оновлення...' : 'Оновити таксономію'}
        </Button>
        {taxResult && (
          <p className={`text-sm mt-2 ${taxResult.startsWith('Помилка') || taxResult.startsWith('501') ? 'text-red-600' : 'text-green-600'}`}>
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