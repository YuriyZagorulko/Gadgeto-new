'use client';

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';
import {
  PageHeader, Button, Select, Input, LoadingState, ErrorState, useToast,
} from '@/components/ui';

type Setting = { id: number; key: string; value: string | null; is_secret: boolean };
type SettingsResp = { items: Setting[] };
type TabName = 'general' | 'export';

const TABS: { key: TabName; label: string }[] = [
  { key: 'general', label: 'Основні' },
  { key: 'export', label: 'Експорт' },
];

export default function RozetkaSettingsPage() {
  const toast = useToast();
  const [tab, setTab] = useState<TabName>('general');
  const [settings, setSettings] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    setLoading(true); setError('');
    api.get<SettingsResp>('/export/channels/rozetka/settings')
      .then((d) => {
        const map: Record<string, string> = {};
        for (const s of d.items) map[s.key] = s.value ?? '';
        setSettings(map);
      })
      .catch((e: any) => setError(e.message || 'Не вдалось завантажити налаштування'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const updateSetting = async (key: string, value: string) => {
    setSaving(true);
    try {
      await api.put('/export/channels/rozetka/settings', { key, value, is_secret: false });
      setSettings((prev) => ({ ...prev, [key]: value }));
      toast.push('success', 'Збережено');
    } catch (e: any) {
      toast.push('error', e.message || 'Помилка збереження');
    } finally {
      setSaving(false);
    }
  };

  const SettingRow = ({
    label, hint, skey, type = 'text',
  }: {
    label: string; hint?: string; skey: string; type?: 'text' | 'number' | 'select';
  }) => {
    const val = settings[skey] ?? '';
    const [draft, setDraft] = useState(val);
    const [changed, setChanged] = useState(false);

    useEffect(() => { setDraft(val); setChanged(false); }, [val]);

    const save = () => {
      if (draft === val) return;
      updateSetting(skey, draft);
      setChanged(false);
    };

    return (
      <div className="flex items-start justify-between py-4 border-b border-gray-100 last:border-0">
        <div className="flex-1 mr-4">
          <label className="block text-sm font-medium text-gray-900">{label}</label>
          {hint && <p className="text-xs text-gray-500 mt-0.5">{hint}</p>}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {type === 'select' ? (
            <Select
              value={draft}
              onChange={(e) => { setDraft(e.target.value); setChanged(true); }}
              className="w-40"
            >
              <option value="percentage">Відсоток</option>
              <option value="fixed">Фіксована</option>
            </Select>
          ) : (
            <Input type={type} value={draft}
              onChange={(e) => { setDraft(e.target.value); setChanged(true); }}
              className="w-32 text-right" />
          )}
          <Button size="sm" onClick={save}
            disabled={!changed || saving}
            variant={changed ? 'primary' : 'ghost'}>
            {saving ? '…' : 'Зберегти'}
          </Button>
        </div>
      </div>
    );
  };

  if (loading) return <LoadingState label="Завантаження налаштувань..." />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div>
      <PageHeader title="Налаштування Rozetka" />

      <div className="flex gap-1 mb-6 border-b border-gray-200">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition -mb-px ${tab === t.key ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'general' && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <p className="text-gray-600 text-sm">Загальні налаштування каналу Rozetka.</p>
          {Object.keys(settings).length > 0 && (
            <div className="mt-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">Збережені параметри</h3>
              <div className="space-y-1">
                {Object.entries(settings).map(([k, v]) => (
                  <div key={k} className="flex items-center gap-3 text-sm">
                    <span className="font-mono text-xs text-gray-500 w-48 truncate">{k}</span>
                    <span className="text-gray-700">{v || '—'}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {tab === 'export' && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-base font-semibold text-gray-900 mb-4">Налаштування експорту товарів</h2>
          <p className="text-xs text-gray-500 mb-6">Ці налаштування застосовуються під час експорту товарів до Rozetka.</p>

          <div className="divide-y divide-gray-100">
            <SettingRow skey="price_markup_type" label="Тип націнки" hint="Відсоток від ціни або фіксована сума" type="select" />
            <SettingRow skey="price_markup_value" label="Розмір націнки" hint="15 = 15% або 15 грн" type="number" />
            <SettingRow skey="price_rounding" label="Округлення ціни" hint="До найближчого X (0 = без округлення)" type="number" />
            <SettingRow skey="min_stock_for_export" label="Мінімальний залишок" hint="Не експортувати товари з кількістю менше" type="number" />
            <SettingRow skey="export_out_of_stock" label="Експорт без залишку" hint="Експортувати товари з нульовою кількістю" type="select" />
          </div>

          <div className="mt-6 pt-4 border-t border-gray-100">
            <h3 className="text-sm font-semibold text-gray-700 mb-2">Поточні значення</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
              <div className="bg-gray-50 rounded px-3 py-2">
                <span className="text-gray-500 text-xs">Тип націнки</span>
                <div className="font-medium">{settings.price_markup_type === 'fixed' ? 'Фіксована' : 'Відсоток'}</div>
              </div>
              <div className="bg-gray-50 rounded px-3 py-2">
                <span className="text-gray-500 text-xs">Розмір націнки</span>
                <div className="font-medium">{settings.price_markup_value || '0'}{settings.price_markup_type === 'fixed' ? ' грн' : '%'}</div>
              </div>
              <div className="bg-gray-50 rounded px-3 py-2">
                <span className="text-gray-500 text-xs">Округлення</span>
                <div className="font-medium">{settings.price_rounding ? `до ${settings.price_rounding}` : '—'}</div>
              </div>
              <div className="bg-gray-50 rounded px-3 py-2">
                <span className="text-gray-500 text-xs">Мін. залишок</span>
                <div className="font-medium">{settings.min_stock_for_export ? `≥ ${settings.min_stock_for_export}` : '—'}</div>
              </div>
              <div className="bg-gray-50 rounded px-3 py-2">
                <span className="text-gray-500 text-xs">Експорт без залишку</span>
                <div className="font-medium">{settings.export_out_of_stock === 'true' ? 'Так' : 'Ні'}</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
