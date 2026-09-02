'use client';

import { useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { api, qs } from '@/lib/api';
import { PageHeader, LoadingState, EmptyState, useToast } from '@/components/ui';
import PricingTab from '@/components/PricingTab';

type Sup = { id: number; code: string; name: string; config: Record<string, string> };

export default function ImportSettingsPage() {
  const sp = useSearchParams();
  const router = useRouter();
  const tab = sp.get('tab') || 'settings';

  const setTab = (t: string) => {
    router.replace('/imports/settings' + (t === 'settings' ? '' : '?tab=' + t));
  };

  return (
    <div>
      <PageHeader title="Налаштування імпорту" />
      <div className="border-b border-gray-200 mb-4">
        <div className="flex gap-6 -mb-px">
          <button onClick={() => setTab('settings')}
            className={'pb-2 text-sm font-medium border-b-2 transition-colors ' + (tab === 'settings' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700')}>
            Налаштування
          </button>
          <button onClick={() => setTab('pricing')}
            className={'pb-2 text-sm font-medium border-b-2 transition-colors ' + (tab === 'pricing' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700')}>
            Ціноутворення
          </button>
        </div>
      </div>
      {tab === 'settings' && <SettingsTab />}
      {tab === 'pricing' && <PricingTab />}
    </div>
  );
}

/* =====================================================================
   TAB 1: Settings — per-supplier config
   ===================================================================== */
function SettingsTab() {
  const toast = useToast();
  const [suppliers, setSuppliers] = useState<Sup[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<number | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    setLoading(true);
    api.get<{ items: Sup[] }>('/suppliers' + qs({ per_page: 100 }))
      .then((d) => setSuppliers(d.items || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [tick]);

  const updateConfig = async (sid: number, config: Record<string, string>) => {
    setSaving(sid);
    try {
      await api.put('/suppliers/' + sid + '/config', { config });
      toast.push('success', 'Налаштування збережено');
      setTick((x) => x + 1);
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally {
      setSaving(null);
    }
  };

  if (loading) return <LoadingState label="Завантаження налаштувань..." />;

  return (
    <div className="space-y-4">
      <p className="text-xs text-gray-400 mb-4">
        Налаштування стосуються лише імпортованих товарів. Ручна завантаження зображень через редактор товару завжди використовує локальне сховище.
      </p>
      {suppliers.length === 0 ? (
        <EmptyState title="Постачальників не знайдено" />
      ) : (
        suppliers.map((s) => {
          const mode = s.config?.image_storage_mode || 'supplier_url';
          return (
            <div key={s.id} className="bg-white border border-gray-200 rounded-lg p-5">
              <h3 className="font-semibold text-gray-900 mb-3">{s.name} ({s.code})</h3>
              <div className="max-w-md">
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Зберігання зображень</label>
                <div className="flex gap-4">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name={'image_storage_' + s.id}
                      value="supplier_url"
                      checked={mode === 'supplier_url'}
                      onChange={() => updateConfig(s.id, { ...s.config, image_storage_mode: 'supplier_url' })}
                      className="accent-blue-600"
                    />
                    <span className="text-sm">Зображення постачальника</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name={'image_storage_' + s.id}
                      value="local"
                      checked={mode === 'local'}
                      onChange={() => updateConfig(s.id, { ...s.config, image_storage_mode: 'local' })}
                      className="accent-blue-600"
                    />
                    <span className="text-sm">Зберігати локально</span>
                  </label>
                </div>
                <p className="text-xs text-gray-400 mt-1.5">
                  {mode === 'supplier_url'
                    ? 'Зображення будуть зберігатися як зовнішні URL-адреси постачальника.'
                    : 'Зображення будуть завантажені та збережені локально в медіа-бібліотеці.'}
                </p>
              </div>
              {saving === s.id && <span className="text-xs text-blue-600 mt-2 block">Збереження...</span>}
            </div>
          );
        })
      )}
    </div>
  );
}
