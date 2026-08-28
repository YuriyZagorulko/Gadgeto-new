'use client';

import { useEffect, useState, useCallback } from 'react';
import { api, qs } from '@/lib/api';
import {
  PageHeader, Button, Input, LoadingState, ErrorState, useToast, Badge,
} from '@/components/ui';

type Slide = { id: number; image: string; title: string | null; subtitle: string | null;
  button_text: string | null; url: string; is_active: boolean; sort_order: number };
type RecItem = { id: number; product_id: number; sort_order: number;
  name: string; sku: string; slug: string; price: number; image: string | null };
type ProductRow = { id: number; sku: string; name: string; price: number };

function SlideFormModal({ slide, saving, onSave, onClose }: {
  slide: Slide; saving: boolean; onSave: (s: Slide) => void; onClose: () => void;
}) {
  const [draft, setDraft] = useState<Slide>(slide);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative z-10 w-full max-w-lg bg-white rounded-xl shadow-2xl p-6">
        <h3 className="text-lg font-semibold mb-4">{slide.id === 0 ? 'Новий слайд' : 'Редагувати слайд'}</h3>
        <div className="space-y-3">
          <div><label className="block text-xs text-gray-500 mb-1">URL зображення *</label>
            <Input value={draft.image} onChange={(e) => setDraft({ ...draft, image: e.target.value })} placeholder="https://..." /></div>
          {draft.image && (
            <div className="w-full h-32 bg-gray-100 rounded overflow-hidden">
              <img src={draft.image} alt="" className="w-full h-full object-cover"
                onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
            </div>
          )}
          <div><label className="block text-xs text-gray-500 mb-1">Заголовок</label>
            <Input value={draft.title || ''} onChange={(e) => setDraft({ ...draft, title: e.target.value })} /></div>
          <div><label className="block text-xs text-gray-500 mb-1">Підзаголовок</label>
            <Input value={draft.subtitle || ''} onChange={(e) => setDraft({ ...draft, subtitle: e.target.value })} /></div>
          <div><label className="block text-xs text-gray-500 mb-1">Текст кнопки</label>
            <Input value={draft.button_text || ''} onChange={(e) => setDraft({ ...draft, button_text: e.target.value })} /></div>
          <div><label className="block text-xs text-gray-500 mb-1">URL призначення *</label>
            <Input value={draft.url} onChange={(e) => setDraft({ ...draft, url: e.target.value })} placeholder="/catalog/ноутбуки" /></div>
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={draft.is_active}
                onChange={(e) => setDraft({ ...draft, is_active: e.target.checked })} className="rounded border-gray-300" />
              Активний
            </label>
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-6">
          <Button variant="secondary" onClick={onClose}>Скасувати</Button>
          <Button onClick={() => onSave(draft)} disabled={saving || !draft.image || !draft.url}>
            {saving ? 'Збереження...' : 'Зберегти'}
          </Button>
        </div>
      </div>
    </div>
  );
}

function RecSelectionModal({ selectedRecs, recResults, recLoading, recPage, saving,
  setRecAppliedQ, setRecPage, toggleRec, moveRec, removeRec,
  saveRecs, onClose }: {
  selectedRecs: RecItem[]; recResults: ProductRow[]; recLoading: boolean; recPage: number; saving: boolean;
  setRecAppliedQ: (v: string) => void; setRecPage: (v: number) => void;
  toggleRec: (id: number, row: ProductRow) => void;
  moveRec: (i: number, d: -1 | 1) => void; removeRec: (id: number) => void;
  saveRecs: () => void; onClose: () => void;
}) {
  const [search, setSearch] = useState('');
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-12">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative z-10 w-full max-w-3xl bg-white rounded-xl shadow-2xl max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold">Рекомендовані товари ({selectedRecs.length}/12)</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">&times;</button>
        </div>
        <div className="px-6 py-3 border-b border-gray-100">
          <Input value={search} onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { setRecAppliedQ(search); setRecPage(1); } }}
            placeholder="Пошук товарів..." className="w-full" />
        </div>
        <div className="flex-1 flex overflow-hidden">
          <div className="flex-1 overflow-y-auto border-r border-gray-100">
            {recLoading ? <LoadingState label="..." /> : (
              <table className="w-full text-sm">
                <thead className="text-xs text-gray-500 uppercase bg-gray-50">
                  <tr><th className="w-10 p-2"></th><th className="p-2 text-left">SKU</th><th className="p-2 text-left">Назва</th><th className="p-2 text-right w-24">Ціна</th></tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {recResults.map((r) => {
                    const isSel = selectedRecs.some((s) => s.product_id === r.id);
                    return (
                      <tr key={r.id} className={'hover:bg-gray-50 cursor-pointer ' + (isSel ? 'bg-blue-50' : '')}
                        onClick={() => toggleRec(r.id, r)}>
                        <td className="p-2 text-center"><input type="checkbox" checked={isSel} readOnly className="rounded border-gray-300" /></td>
                        <td className="p-2 text-xs font-mono">{r.sku || '—'}</td>
                        <td className="p-2 max-w-xs truncate">{r.name}</td>
                        <td className="p-2 text-right text-xs">{r.price?.toLocaleString('uk-UA')}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
          <div className="w-64 overflow-y-auto p-3">
            <h3 className="text-xs font-semibold text-gray-500 uppercase mb-2">Обрані ({selectedRecs.length})</h3>
            {selectedRecs.length === 0 ? (
              <p className="text-xs text-gray-400">Оберіть товари зі списку</p>
            ) : (
              <div className="space-y-1">
                {selectedRecs.map((r, i) => (
                  <div key={r.product_id} className="flex items-center gap-1 bg-gray-50 rounded px-2 py-1 group">
                    <span className="text-xs text-gray-400 w-4">{i + 1}</span>
                    <span className="text-xs flex-1 truncate">{r.name}</span>
                    <div className="flex gap-0.5 opacity-0 group-hover:opacity-100">
                      <button onClick={() => moveRec(i, -1)} disabled={i === 0} className="text-xs text-gray-400 hover:text-gray-600 px-0.5">↑</button>
                      <button onClick={() => moveRec(i, 1)} disabled={i >= selectedRecs.length - 1} className="text-xs text-gray-400 hover:text-gray-600 px-0.5">↓</button>
                      <button onClick={() => removeRec(r.product_id)} className="text-xs text-red-400 hover:text-red-600 px-0.5">×</button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
        <div className="px-6 py-3 border-t border-gray-200 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-md border border-gray-200 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50">Скасувати</button>
          <button onClick={saveRecs} disabled={saving || selectedRecs.length === 0}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
            {saving ? 'Збереження...' : 'Зберегти'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function HomepageContentPage() {
  const toast = useToast();
  const [slides, setSlides] = useState<Slide[]>([]);
  const [recs, setRecs] = useState<RecItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [slideModal, setSlideModal] = useState<Slide | null>(null);
  const [recModal, setRecModal] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      api.get<{ items: Slide[] }>('/content/homepage/slides'),
      api.get<{ items: RecItem[] }>('/content/homepage/recommended'),
    ]).then(([s, r]) => {
      setSlides(s.items || []);
      setRecs(r.items || []);
    }).catch((e: any) => setError(e.message || 'Помилка завантаження'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const saveSlide = async (slide: Slide) => {
    setSaving(true);
    try {
      if (slide.id === 0) {
        await api.post('/content/homepage/slides', slide);
      } else {
        await api.put('/content/homepage/slides/' + slide.id, slide);
      }
      toast.push('success', 'Слайд збережено');
      setSlideModal(null);
      load();
    } catch (e: any) { toast.push('error', e.message); }
    finally { setSaving(false); }
  };

  const deleteSlide = async (id: number) => {
    if (!confirm('Видалити слайд?')) return;
    try {
      await api.delete('/content/homepage/slides/' + id);
      toast.push('success', 'Слайд видалено');
      load();
    } catch (e: any) { toast.push('error', e.message); }
  };

  const toggleSlide = async (id: number, active: boolean) => {
    try {
      await api.put('/content/homepage/slides/' + id, { is_active: active });
      toast.push('success', active ? 'Слайд активовано' : 'Слайд деактивовано');
      load();
    } catch (e: any) { toast.push('error', e.message); }
  };

  const [recSearch, setRecSearch] = useState('');
  const [recAppliedQ, setRecAppliedQ] = useState('');
  const [recResults, setRecResults] = useState<ProductRow[]>([]);
  const [recLoading, setRecLoading] = useState(false);
  const [selectedRecs, setSelectedRecs] = useState<RecItem[]>([]);
  const [recPage, setRecPage] = useState(1);

  useEffect(() => {
    if (!recModal) return;
    setRecLoading(true);
    const params: Record<string, string | number | undefined> = { page: recPage, per_page: 10 };
    if (recAppliedQ) params.q = recAppliedQ;
    api.get<{ items: ProductRow[]; total: number }>('/export/channels/rozetka/products' + qs(params))
      .then((d) => setRecResults(d.items))
      .catch(() => {})
      .finally(() => setRecLoading(false));
  }, [recModal, recPage, recAppliedQ]);

  const openRecModal = () => {
    setSelectedRecs([...recs]);
    setRecModal(true);
  };

  const toggleRec = (productId: number, row: ProductRow) => {
    setSelectedRecs((prev) => {
      if (prev.find((r) => r.product_id === productId)) return prev.filter((r) => r.product_id !== productId);
      if (prev.length >= 12) { toast.push('error', 'Максимум 12 товарів'); return prev; }
      return [...prev, { id: 0, product_id: productId, sort_order: prev.length,
        name: row.name, sku: row.sku || '', slug: '', price: row.price, image: null }];
    });
  };

  const removeRec = (productId: number) => setSelectedRecs((prev) => prev.filter((r) => r.product_id !== productId));

  const moveRec = (index: number, direction: -1 | 1) => {
    const newIdx = index + direction;
    if (newIdx < 0 || newIdx >= selectedRecs.length) return;
    setSelectedRecs((prev) => {
      const next = [...prev];
      [next[index], next[newIdx]] = [next[newIdx], next[index]];
      return next.map((r, i) => ({ ...r, sort_order: i }));
    });
  };

  const saveRecs = async () => {
    setSaving(true);
    try {
      const ids = [...new Set(selectedRecs.map((r) => r.product_id))].slice(0, 12);
      await api.put('/content/homepage/recommended', { product_ids: ids });
      toast.push('success', 'Рекомендовані товари збережено');
      setRecModal(false);
      load();
    } catch (e: any) { toast.push('error', e.message); }
    finally { setSaving(false); }
  };

  if (loading) return <LoadingState label="Завантаження контенту..." />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div>
      <PageHeader title="Головна сторінка" />

      <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold">Слайдер</h2>
          <Button onClick={() => setSlideModal({ id: 0, image: '', title: '', subtitle: '', button_text: '', url: '', is_active: true, sort_order: slides.length })}>
            + Додати слайд
          </Button>
        </div>
        {slides.length === 0 ? (
          <p className="text-sm text-gray-500 py-4">Слайдер не налаштовано.</p>
        ) : (
          <div className="space-y-2">
            {slides.map((s, i) => (
              <div key={s.id} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                <span className="text-sm text-gray-400 w-6">{i + 1}</span>
                <div className="w-20 h-14 bg-gray-200 rounded overflow-hidden shrink-0">
                  {s.image && <img src={s.image} alt="" className="w-full h-full object-cover" />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">{s.title || '(без назви)'}</div>
                  <div className="text-xs text-gray-500 truncate">{s.url}</div>
                </div>
                <Badge tone={s.is_active ? 'green' : 'gray'}>{s.is_active ? 'Активний' : 'Неактивний'}</Badge>
                <div className="flex gap-1 shrink-0">
                  <Button size="sm" variant="ghost" onClick={() => toggleSlide(s.id, !s.is_active)}>
                    {s.is_active ? 'Вимкнути' : 'Увімкнути'}
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setSlideModal({ ...s })}>Редагувати</Button>
                  <Button size="sm" variant="ghost" onClick={() => deleteSlide(s.id)}>Видалити</Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold">Рекомендовані товари</h2>
          <Button onClick={openRecModal}>Керувати товарами</Button>
        </div>
        {recs.length === 0 ? (
          <p className="text-sm text-gray-500 py-4">Рекомендовані товари не налаштовано.</p>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {recs.map((r) => (
              <div key={r.product_id} className="bg-gray-50 rounded-lg p-2 flex items-center gap-2">
                <div className="w-10 h-10 bg-gray-200 rounded shrink-0 overflow-hidden">
                  {r.image && <img src={r.image} alt="" className="w-full h-full object-cover" />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-medium truncate">{r.name}</div>
                  <div className="text-xs text-gray-500">{r.price?.toLocaleString('uk-UA')} ₴</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {slideModal && <SlideFormModal slide={slideModal} saving={saving} onSave={saveSlide} onClose={() => setSlideModal(null)} />}

      {recModal && (
        <RecSelectionModal
          selectedRecs={selectedRecs} recResults={recResults}
          recLoading={recLoading} recPage={recPage} saving={saving}
          setRecAppliedQ={setRecAppliedQ} setRecPage={setRecPage}
          toggleRec={toggleRec} moveRec={moveRec} removeRec={removeRec}
          saveRecs={saveRecs} onClose={() => setRecModal(false)}
        />
      )}
    </div>
  );
}
