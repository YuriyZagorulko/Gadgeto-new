'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { PageHeader, Button, Textarea, Table, Th, Td, Badge, LoadingState, ErrorState, EmptyState, Modal, useToast } from '@/components/ui';

type Setting = { key: string; value: string | null; is_secret: boolean; has_value: boolean };

export default function SettingsPage() {
  const toast = useToast();
  const [items, setItems] = useState<Setting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [editing, setEditing] = useState<Setting | null>(null);
  const [draft, setDraft] = useState('');
  const [saving, setSaving] = useState(false);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError('');
    api.get<{ items: Setting[] }>('/settings')
      .then((d) => !cancelled && setItems(d.items || []))
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [tick]);

  const openEdit = (s: Setting) => {
    setEditing(s);
    setDraft(s.is_secret ? '' : s.value ?? '');
  };

  const save = async () => {
    if (!editing) return;
    setSaving(true);
    try {
      await api.put(`/settings/${encodeURIComponent(editing.key)}`, { value: draft });
      toast.push('success', 'Налаштування збережено');
      setEditing(null);
      setTick((t) => t + 1);
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally { setSaving(false); }
  };

  return (
    <div>
      <PageHeader title="Налаштування" />
      <p className="text-xs text-gray-400 mb-4">
        Бізнес-налаштування магазину, що зберігаються в базі даних. Секретні значення приховані — їх можна лише перезаписати.
        Інфраструктурні секрети (змінні середовища, ключі доступу) тут не відображаються і не редагуються.
      </p>

      {error && <ErrorState message={error} onRetry={() => setTick((t) => t + 1)} />}
      {loading && <LoadingState label="Завантаження налаштувань..." />}
      {!error && !loading && items.length === 0 && (
        <EmptyState title="Налаштувань немає" hint="Записи з'являться, коли бекенд збереже перші значення." />
      )}
      {!error && items.length > 0 && (
        <Table head={<tr><Th>Ключ</Th><Th>Значення</Th><Th>Тип</Th><Th className="w-24"></Th></tr>}>
          {items.map((s) => (
            <tr key={s.key} className="hover:bg-gray-50">
              <Td className="font-mono text-xs">{s.key}</Td>
              <Td>
                {s.is_secret ? (
                  <span className="text-gray-400">••••••{s.has_value ? '' : ' (не задано)'}</span>
                ) : (
                  <span className="break-all">{s.value !== null && s.value !== '' ? s.value : <span className="text-gray-400">— не задано —</span>}</span>
                )}
              </Td>
              <Td>{s.is_secret ? <Badge tone="yellow">секрет</Badge> : <Badge tone="gray">текст</Badge>}</Td>
              <Td>
                <Button size="sm" variant="secondary" onClick={() => openEdit(s)}>
                  {s.has_value ? 'Змінити' : 'Задати'}
                </Button>
              </Td>
            </tr>
          ))}
        </Table>
      )}

      <Modal open={!!editing} title={editing ? `Налаштування: ${editing.key}` : ''} onClose={() => setEditing(null)}>
        <div className="space-y-4">
          {editing?.is_secret && (
            <p className="text-xs text-yellow-700 bg-yellow-50 border border-yellow-100 rounded p-2">
              Це секретне налаштування. Поточне значення приховано; введіть нове значення, щоб перезаписати його.
            </p>
          )}
          <div>
            <label className="block text-xs text-gray-500 mb-1">Значення {editing?.is_secret ? '(нове)' : ''}</label>
            <Textarea rows={5} value={draft} onChange={(e) => setDraft(e.target.value)}
              className="font-mono text-xs" autoFocus />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="secondary" onClick={() => setEditing(null)}>Скасувати</Button>
            <Button loading={saving} onClick={save}>Зберегти</Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

