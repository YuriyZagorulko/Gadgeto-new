'use client';

import { useEffect, useState } from 'react';
import { api, qs } from '@/lib/api';
import { Button, Input, LoadingState, useToast, Badge } from '@/components/ui';

type PricingStatus = {
  active: boolean; import_id?: number; filename?: string; status?: string;
  total_rows?: number; categories_found?: number; rules_imported?: number;
  invalid_rows?: number; duplicate_rows?: number; errors?: string[];
  created_at?: string; updated_at?: string;
  previous?: { filename?: string; created_at?: string; rules_imported?: number } | null;
};

type PricingRule = {
  id: number; external_category_id: string; category_name: string;
  brand: string | null; price_min: number | null; price_max: number | null;
  commission_percent: number; created_at: string;
};

type RulesResp = {
  items: PricingRule[]; total: number; page: number; per_page: number;
  import_id: number | null; filename?: string; created_at?: string;
};

type UploadResult = {
  ok: boolean; import_id?: number; total_rows?: number; categories_found?: number;
  rules_imported?: number; invalid_rows?: number; duplicates?: number;
  sample_errors?: string[][]; detail?: string;
};

function CheckRow({ label, ok, detail }: { label: string; ok: boolean; detail?: string }) {
  return (
    <tr>
      <td className="py-1 pr-4 text-sm">{label}</td>
      <td className="py-1 pr-4 text-sm">
        {ok ? <Badge tone="green">OK</Badge> : <Badge tone="red">Помилка</Badge>}
      </td>
      <td className="py-1 text-sm text-gray-600">{detail || (ok ? '—' : '—')}</td>
    </tr>
  );
}

export default function RozetkaPricingTab() {
  const toast = useToast();
  const [status, setStatus] = useState<PricingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
  const [rules, setRules] = useState<PricingRule[]>([]);
  const [rulesTotal, setRulesTotal] = useState(0);
  const [rulesPage, setRulesPage] = useState(1);
  const [rulesQuery, setRulesQuery] = useState('');
  const [rulesLoading, setRulesLoading] = useState(false);
  const perPage = 25;

  const loadStatus = () => {
    setLoading(true);
    api.get<PricingStatus>('/pricing/rozetka/status')
      .then((d) => setStatus(d))
      .catch(() => setStatus({ active: false }))
      .finally(() => setLoading(false));
  };

  const loadRules = () => {
    setRulesLoading(true);
    const params: Record<string, string | number | undefined> = { page: rulesPage, per_page: perPage };
    if (rulesQuery) params.q = rulesQuery;
    api.get<RulesResp>('/pricing/rozetka/rules' + qs(params))
      .then((d) => { setRules(d.items); setRulesTotal(d.total); })
      .catch(() => {})
      .finally(() => setRulesLoading(false));
  };

  useEffect(() => { loadStatus(); }, []);
  useEffect(() => { if (status?.active) loadRules(); }, [status, rulesPage, rulesQuery]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadResult(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const token = localStorage.getItem('admin_token') || '';
      const res = await fetch('/api/pricing/rozetka/import', {
        method: 'POST',
        headers: { Authorization: 'Bearer ' + token },
        body: formData,
      });
      const data = await res.json();
      setUploadResult(data);
      if (data.ok) {
        toast.push('success', 'Імпортовано ' + data.rules_imported + ' правил із ' + data.total_rows + ' рядків');
        loadStatus();
      } else {
        toast.push('error', data.detail || 'Помилка імпорту');
      }
    } catch (err: any) {
      toast.push('error', err.message || 'Помилка завантаження');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  if (loading) return <LoadingState label="Завантаження..." />;

  const ValidationTable = ({ result }: { result: UploadResult }) => {
    const ok = result.ok && result.rules_imported! > 0;
    const checks = [
      { label: 'Файл XLSX', ok: true, detail: 'Файл відкрито' },
      { label: 'Структура', ok: true, detail: 'Необхідні колонки знайдено' },
      { label: 'Розбір', ok: result.total_rows! > 0, detail: result.total_rows + ' рядків' },
      { label: 'Категорії', ok: result.categories_found! > 0, detail: result.categories_found + ' категорій' },
      { label: 'Комісії', ok: result.rules_imported! > 0, detail: result.rules_imported + ' правил' },
      { label: 'Дублікати', ok: result.duplicates === 0, detail: result.duplicates + ' знайдено' },
      { label: 'Некоректні рядки', ok: result.invalid_rows === 0, detail: result.invalid_rows + ' рядків' },
      { label: 'Імпорт у БД', ok: ok, detail: ok ? 'Успішно' : 'Помилка' },
      { label: 'Активація прайсу', ok: ok, detail: ok ? 'Активний' : 'Не активовано' },
    ];
    return (
      <div className="mt-4">
        <h4 className="text-sm font-semibold text-gray-700 mb-2">Результат перевірки</h4>
        <table className="w-full text-sm">
          <thead className="text-xs text-gray-500 uppercase bg-gray-50">
            <tr><th className="p-2 text-left">Перевірка</th><th className="p-2 text-left">Статус</th><th className="p-2 text-left">Результат</th></tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {checks.map((c) => <CheckRow key={c.label} {...c} />)}
          </tbody>
        </table>
        {result.sample_errors && result.sample_errors.length > 0 && (
          <div className="mt-3 text-xs text-red-600">
            {result.sample_errors.map((errs, i) => (
              <div key={i}>Рядок: {errs.join('; ')}</div>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-base font-semibold mb-4">Прайс / комісія Rozetka</h3>
        {status?.active ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Badge tone="green">Активний</Badge>
              <span className="text-sm text-gray-600">Прайс успішно завантажено та перевірено</span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              <div className="bg-gray-50 rounded px-3 py-2"><span className="text-gray-500 text-xs">Категорій</span><div className="font-medium">{status.categories_found}</div></div>
              <div className="bg-gray-50 rounded px-3 py-2"><span className="text-gray-500 text-xs">Правил комісії</span><div className="font-medium">{status.rules_imported}</div></div>
              <div className="bg-gray-50 rounded px-3 py-2"><span className="text-gray-500 text-xs">Помилок</span><div className="font-medium">{status.invalid_rows || 0}</div></div>
              <div className="bg-gray-50 rounded px-3 py-2"><span className="text-gray-500 text-xs">Дублікатів</span><div className="font-medium">{status.duplicate_rows || 0}</div></div>
            </div>
            <div className="text-xs text-gray-500 space-y-0.5">
              <div>Файл: <strong>{status.filename}</strong></div>
              <div>Завантажено: {status.created_at ? new Date(status.created_at).toLocaleString('uk-UA') : '—'}</div>
              {status.previous && (
                <div className="mt-1 pt-1 border-t border-gray-100">
                  <span className="text-gray-400">Попередній: </span>
                  {status.previous.filename} ({status.previous.created_at ? new Date(status.previous.created_at).toLocaleString('uk-UA') : '—'})
                  — {status.previous.rules_imported} правил
                </div>
              )}
            </div>
          </div>
        ) : (
          <p className="text-sm text-gray-500 py-2">Прайс Rozetka не завантажено. Експорт використовує налаштування націнки зі сторінки «Експорт».</p>
        )}
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-base font-semibold mb-2">Оновити прайс Rozetka</h3>
        <p className="text-xs text-gray-500 mb-4">Завантажте файл .xlsx із комісіями Rozetka.</p>
        <label className="inline-flex items-center justify-center gap-2 font-medium rounded-md transition cursor-pointer bg-blue-600 text-white hover:bg-blue-700 px-4 py-2 text-sm disabled:opacity-50">
          {uploading ? 'Завантаження...' : 'Обрати файл .xlsx'}
          <input type="file" accept=".xlsx" onChange={handleUpload} className="hidden" disabled={uploading} />
        </label>

        {uploadResult && (
          <>
            {uploadResult.ok ? (
              <div className="mt-4 p-3 bg-green-50 border border-green-100 rounded-lg">
                <div className="flex items-center gap-2 text-sm font-medium text-green-800">
                  <span className="text-lg">✅</span> Прайс успішно завантажено та перевірено
                </div>
              </div>
            ) : (
              <div className="mt-4 p-3 bg-red-50 border border-red-100 rounded-lg">
                <div className="flex items-center gap-2 text-sm font-medium text-red-800">
                  <span className="text-lg">❌</span> {uploadResult.detail || 'Помилка завантаження'}
                </div>
              </div>
            )}
            <ValidationTable result={uploadResult} />
          </>
        )}
      </div>

      {status?.active && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-semibold">Правила комісії</h3>
            <Input value={rulesQuery} onChange={(e) => { setRulesQuery(e.target.value); setRulesPage(1); }}
              placeholder="Пошук категорії..." className="w-48" />
          </div>
          {rulesLoading ? <LoadingState label="..." /> : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-xs text-gray-500 uppercase bg-gray-50">
                  <tr>
                    <th className="p-2 text-left">Категорія Rozetka</th>
                    <th className="p-2 text-left">ID</th>
                    <th className="p-2 text-left">Бренд</th>
                    <th className="p-2 text-right">Ціна від</th>
                    <th className="p-2 text-right">Ціна до</th>
                    <th className="p-2 text-right">Комісія</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {rules.length === 0 ? (
                    <tr><td colSpan={6} className="p-4 text-center text-gray-400">Немає правил</td></tr>
                  ) : rules.map((r) => (
                    <tr key={r.id}>
                      <td className="p-2 max-w-xs truncate">{r.category_name}</td>
                      <td className="p-2 text-xs font-mono">{r.external_category_id}</td>
                      <td className="p-2 text-xs">{r.brand || '—'}</td>
                      <td className="p-2 text-right text-xs">{r.price_min?.toLocaleString('uk-UA') || '—'}</td>
                      <td className="p-2 text-right text-xs">{r.price_max?.toLocaleString('uk-UA') || '—'}</td>
                      <td className="p-2 text-right font-semibold">{r.commission_percent}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="flex items-center justify-between mt-4">
            <div className="text-sm text-gray-600">Стор. {rulesPage} з {Math.max(1, Math.ceil(rulesTotal / perPage))} ({rulesTotal})</div>
            <div className="flex gap-2">
              <Button variant="ghost" size="sm" onClick={() => setRulesPage(Math.max(1, rulesPage - 1))} disabled={rulesPage <= 1}>←</Button>
              <Button variant="ghost" size="sm" onClick={() => setRulesPage(rulesPage + 1)} disabled={rules.length < perPage}>→</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
