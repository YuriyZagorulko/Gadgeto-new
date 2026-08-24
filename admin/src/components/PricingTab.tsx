'use client';

import { useState, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';
import { LoadingState, Button, Table, Th, Td, useToast } from '@/components/ui';

type Rule = {
  id: number; supplier_code: string; category_id: number | null;
  price_threshold: number; multiplier: number; is_active: boolean;
};
type PricingConfig = { usd_rate: number; rules: Rule[] };
type PreviewResult = {
  source_price: number; source_currency: string; usd_rate: number | null;
  base_price_uah: number; multiplier: number; markup_percent: number;
  final_price_uah: number; final_price_kopecks: number;
};

export default function PricingTab() {
  const toast = useToast();
  const [config, setConfig] = useState<PricingConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [usdRate, setUsdRate] = useState('44.3');
  const [savingUsd, setSavingUsd] = useState(false);
  const [newThreshold, setNewThreshold] = useState('');
  const [newMultiplier, setNewMultiplier] = useState('');
  const [creating, setCreating] = useState(false);
  const [previewPrice, setPreviewPrice] = useState('');
  const [previewCurrency, setPreviewCurrency] = useState('UAH');
  const [previewResult, setPreviewResult] = useState<PreviewResult | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
const loadConfig = useCallback(() => {
    setLoading(true);
    api.get<PricingConfig>('/pricing/config')
      .then((d) => { setConfig(d); setUsdRate(String(d.usd_rate)); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => { loadConfig(); }, [loadConfig]);

  const saveUsdRate = async () => {
    const rate = parseFloat(usdRate);
    if (isNaN(rate) || rate <= 0) return;
    setSavingUsd(true);
    try {
      await api.put('/pricing/usd-rate', { rate });
      toast.push('success', 'Курс USD збережено');
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally { setSavingUsd(false); }
  };

  const createRule = async () => {
    const threshold = parseInt(newThreshold, 10);
    const pct = parseFloat(newMultiplier);
    if (isNaN(threshold) || isNaN(pct)) return;
    const multiplier = pct / 100 + 1;
    setCreating(true);
    try {
      await api.post('/pricing/rules', { price_threshold: threshold, multiplier });
      toast.push('success', 'Правило додано');
      setNewThreshold(''); setNewMultiplier('');
      loadConfig();
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally { setCreating(false); }
  };

  const deleteRule = async (id: number) => {
    try {
      await api.delete('/pricing/rules/' + id);
      toast.push('success', 'Правило видалено');
      loadConfig();
    } catch (e: unknown) { toast.push('error', (e as Error).message); }
  };

  const toggleRule = async (r: Rule) => {
    try {
      await api.put('/pricing/rules/' + r.id, { is_active: !r.is_active });
      loadConfig();
    } catch (e: unknown) { toast.push('error', (e as Error).message); }
  };

  const runPreview = async () => {
    const price = parseFloat(previewPrice);
    if (isNaN(price) || price <= 0) return;
    setPreviewLoading(true);
    try {
      const result = await api.post<PreviewResult>('/pricing/preview', { price, currency: previewCurrency });
      setPreviewResult(result);
    } catch (e: unknown) { toast.push('error', (e as Error).message); }
    finally { setPreviewLoading(false); }
  };

  if (loading) return <LoadingState label="Завантаження налаштувань цін..." />;

  const sorted = [...(config?.rules || [])].sort((a, b) => a.price_threshold - b.price_threshold);
return (
    <div className="space-y-6">
      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <h3 className="font-semibold text-gray-900 mb-3">Курс USD → UAH</h3>
        <p className="text-xs text-gray-500 mb-3">Використовується для товарів, що мають ціну в USD.</p>
        <div className="flex items-end gap-3 max-w-xs">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1">Курс</label>
            <input type="number" step="0.01" min="0" value={usdRate}
              onChange={(e) => setUsdRate(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <Button onClick={saveUsdRate} loading={savingUsd}>Зберегти</Button>
        </div>
      </div>
<div className="bg-white border border-gray-200 rounded-lg p-5">
        <h3 className="font-semibold text-gray-900 mb-3">Налаштування цін</h3>
        <p className="text-xs text-gray-500 mb-3">
          Правила націнки оцінюються від найменшого порогу.
          Перше правило, де базова ціна ≤ порогу, застосовується.
        </p>
        <Table head={<tr><Th>До ціни (₴)</Th><Th>Націнка</Th><Th>Множник</Th><Th>Активне</Th><Th></Th></tr>}>
          {sorted.map((r) => (
            <tr key={r.id} className="hover:bg-gray-50">
              <Td className="text-sm tabular-nums">
                {r.price_threshold >= 999999999 ? 'Без обмеження' : r.price_threshold.toLocaleString('uk-UA')}
              </Td>
              <Td className="text-sm tabular-nums">{Math.round((r.multiplier - 1) * 100)}%</Td>
              <Td className="text-sm tabular-nums font-mono">×{r.multiplier}</Td>
              <Td>
                <input type="checkbox" checked={r.is_active}
                  onChange={() => toggleRule(r)}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
              </Td>
              <Td><Button size="sm" variant="ghost" onClick={() => deleteRule(r.id)}>🗑</Button></Td>
            </tr>
          ))}
        </Table>

        <div className="mt-4 flex items-end gap-3 max-w-lg">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">До ціни (₴)</label>
            <input type="number" min="0" value={newThreshold}
              onChange={(e) => setNewThreshold(e.target.value)}
              placeholder="напр. 500"
              className="w-28 border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Націнка (%)</label>
            <input type="number" step="1" min="0" value={newMultiplier}
              onChange={(e) => setNewMultiplier(e.target.value)}
              placeholder="напр. 45"
              className="w-28 border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <Button onClick={createRule} loading={creating}>Додати</Button>
        </div>
      </div>
<div className="bg-white border border-gray-200 rounded-lg p-5">
        <h3 className="font-semibold text-gray-900 mb-3">Калькулятор ціни</h3>
        <p className="text-xs text-gray-500 mb-3">
          Перевірте розрахунок ціни з поточними налаштуваннями.
        </p>
        <div className="flex items-end gap-3 max-w-md mb-4">
          <div className="flex-1">
            <label className="block text-xs font-medium text-gray-700 mb-1">Ціна постачальника</label>
            <input type="number" step="0.01" min="0" value={previewPrice}
              onChange={(e) => setPreviewPrice(e.target.value)}
              placeholder="напр. 100"
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <div className="w-24">
            <label className="block text-xs font-medium text-gray-700 mb-1">Валюта</label>
            <select value={previewCurrency}
              onChange={(e) => { setPreviewCurrency(e.target.value); setPreviewResult(null); }}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
              <option value="UAH">UAH</option>
              <option value="USD">USD</option>
            </select>
          </div>
          <Button onClick={runPreview} loading={previewLoading}>Розрахувати</Button>
        </div>

        {previewResult && (
          <div className="bg-gray-50 border border-gray-200 rounded-md p-4 max-w-md">
            <div className="text-sm space-y-1.5">
              <div className="flex justify-between">
                <span className="text-gray-600">Ціна постачальника:</span>
                <span className="font-medium">{previewResult.source_price} {previewResult.source_currency}</span>
              </div>
              {previewResult.usd_rate != null && (
                <div className="flex justify-between">
                  <span className="text-gray-600">Курс USD:</span>
                  <span className="font-medium">{previewResult.usd_rate}</span>
                </div>
              )}
              <div className="flex justify-between border-t border-gray-200 pt-1.5">
                <span className="text-gray-600">Базова ціна:</span>
                <span className="font-medium">{previewResult.base_price_uah.toLocaleString('uk-UA', { minimumFractionDigits: 2 })} ₴</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Націнка:</span>
                <span className="font-medium text-green-700">+{previewResult.markup_percent}% (×{previewResult.multiplier})</span>
              </div>
              <div className="flex justify-between border-t border-gray-200 pt-1.5 text-base">
                <span className="font-semibold text-gray-800">Фінальна ціна:</span>
                <span className="font-bold text-lg">{previewResult.final_price_uah.toLocaleString('uk-UA', { minimumFractionDigits: 2 })} ₴</span>
              </div>
              <div className="flex justify-between text-xs text-gray-400">
                <span>Зберігається як:</span>
                <span className="font-mono">{previewResult.final_price_kopecks} коп.</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
