'use client';

import { useEffect, useState } from 'react';
import { api, qs } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import {
  PageHeader,
  Button,
  Input,
  Select,
  Table,
  Th,
  Td,
  Badge,
  LoadingState,
  ErrorState,
  Pagination,
  Modal,
  ConfirmDialog,
  useToast,
} from '@/components/ui';

type Kind = 'attributes' | 'values' | 'categories';

const TABS: { key: Kind; label: string }[] = [
  { key: 'attributes', label: 'Маппінг атрибутів' },
  { key: 'values', label: 'Маппінг значень атрибутів' },
  { key: 'categories', label: 'Маппінг категорій' },
];

const COLUMN_LABELS: Record<Kind, { supplierItem: string; catalog: string; attribute?: string }> = {
  attributes: { supplierItem: 'Атрибут постачальника', catalog: 'Внутрішній атрибут' },
  values: { supplierItem: 'Значення постачальника', catalog: 'Внутрішнє значення', attribute: 'Атрибут' },
  categories: { supplierItem: 'Категорія постачальника', catalog: 'Внутрішня категорія' },
};

type Row = {
  id: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  supplier_id: number | null;
  supplier_code: string | null;
  supplier_name: string | null;
  is_global: boolean;
  supplier_item_id: number;
  supplier_item_name: string;
  holder_name?: string | null;
  catalog_item_id: number | null;
  catalog_name: string | null;
};
type ListResp = { items: Row[]; total: number; page: number; per_page: number };
type Opt = { id: number; name: string };
type ValOpt = { id: number; value: string };
type SupOpt = { id: number; code: string; name: string };

type SortKey = 'id' | 'supplier' | 'attribute' | 'supplier_item' | 'catalog' | 'status' | 'updated_at';
type SortDir = 'asc' | 'desc';

export default function MappingsPage() {
  const toast = useToast();
  const [kind, setKind] = useState<Kind>('attributes');
  const [q, setQ] = useState('');
  const [appliedQ, setAppliedQ] = useState('');
  const [sortBy, setSortBy] = useState<SortKey>('updated_at');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);

  const [rows, setRows] = useState<Row[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tick, setTick] = useState(0);

  const [suppliers, setSuppliers] = useState<SupOpt[]>([]);
  const [cats, setCats] = useState<Opt[]>([]);
  const [attrs, setAttrs] = useState<Opt[]>([]);
  const [valOpts, setValOpts] = useState<ValOpt[]>([]);

  // create / edit modal
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Row | null>(null);
  const [fScope, setFScope] = useState('');            // '' = global (default)
  const [fStatus, setFStatus] = useState('');          // '' | 'true' | 'false'
  const [fMapped, setFMapped] = useState('');          // '' | 'true' | 'false
  const [fItemName, setFItemName] = useState('');
  const [fParentName, setFParentName] = useState('');       // values: holder attr
  const [fInternalAttrId, setFInternalAttrId] = useState(''); // values only
  const [fCatalogId, setFCatalogId] = useState('');
  const [fActive, setFActive] = useState(true);
  const [saving, setSaving] = useState(false);
  const [togglingId, setTogglingId] = useState<number | null>(null);

  const [deleting, setDeleting] = useState<Row | null>(null);

  useEffect(() => {
    api.get<{ items: SupOpt[] }>('/suppliers' + qs({ per_page: 100 }))
      .then((d) => setSuppliers((d.items || []).filter((s) => s.code === 'itlink' || s.code === 'dclink')))
      .catch(() => {});
    api.get<{ items: Opt[] }>('/categories')
      .then((d) => setCats(d.items || [])).catch(() => {});
    api.get<{ items: Opt[] }>('/attributes' + qs({ per_page: 100 }))
      .then((d) => setAttrs(d.items || [])).catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError('');
    const scopeSup = fScope && fScope !== 'global'
      ? suppliers.find((x) => x.code === fScope)?.id : undefined;
    api.get<ListResp>(`/mappings/${kind}` + qs({
      page, per_page: perPage,
      q: appliedQ || undefined,
      sort_by: sortBy, sort_dir: sortDir,
      active: fStatus === '' ? undefined : fStatus === 'true',
      mapped: fMapped === '' ? undefined : fMapped === 'true',
      scope: fScope === 'global' ? 'global' : (fScope ? 'supplier' : undefined),
      supplier_id: scopeSup,
    }))
      .then((d) => { if (!cancelled) { setRows(d.items || []); setTotal(d.total); } })
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [kind, appliedQ, sortBy, sortDir, page, perPage, tick, fScope, fStatus, fMapped, suppliers]);

  useEffect(() => { setPage(1); }, [kind, appliedQ, sortBy, sortDir, perPage, fScope, fStatus, fMapped]);

  const resetFilters = () => {
    setQ(''); setAppliedQ(''); setFStatus(''); setFMapped(''); setFScope('');
  };

  const hasFilters = !!(appliedQ || fStatus || fMapped || fScope);

  const toggleSort = (key: SortKey) => {
    if (sortBy === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortBy(key); setSortDir('asc'); }
  };

  const reload = () => setTick((t) => t + 1);

  const toggleStatus = async (row: Row) => {
    setTogglingId(row.id);
    try {
      // rows without an internal target keep it (null) when deactivating;
      // activating a target-less row is rejected by the API with a hint
      await api.put(`/mappings/${kind}/${row.id}`, {
        catalog_item_id: row.catalog_item_id,
        is_active: !row.is_active,
      });
      reload();
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally { setTogglingId(null); }
  };

  const doDelete = async () => {
    if (!deleting) return;
    try {
      await api.delete(`/mappings/${kind}/${deleting.id}`);
      toast.push('success', 'Маппінг видалено');
      setDeleting(null); reload();
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
      setDeleting(null);
    }
  };
const openCreate = () => {
    setEditing(null);
    setFScope('');
    setFItemName(''); setFParentName('');
    setFInternalAttrId(''); setFCatalogId(''); setFActive(true); setValOpts([]);
    setModalOpen(true);
  };

  const openEdit = (row: Row) => {
    setEditing(row);
    setFScope(row.is_global ? '' : (row.supplier_code || ''));
    setFItemName(row.supplier_item_name);
    setFParentName('');
    setFInternalAttrId('');
    setFCatalogId(row.catalog_item_id ? String(row.catalog_item_id) : '');
    setFActive(row.is_active);
    // seed the current option so the select can display it even without context
    setValOpts(kind === 'values' && row.catalog_item_id
      ? [{ id: row.catalog_item_id, value: row.catalog_name || `#${row.catalog_item_id}` }]
      : []);
    setModalOpen(true);
  };

  const closeMappingModal = () => setModalOpen(false);

  const loadValuesForAttr = (attrId: string) => {
    setFInternalAttrId(attrId);
    setFCatalogId('');
    if (!attrId) { setValOpts([]); return; }
    api.get<{ items: ValOpt[] }>(`/attributes/${attrId}/values`)
      .then((d) => setValOpts(d.items || []))
      .catch(() => setValOpts([]));
  };

  const save = async () => {
    const name = fItemName.trim();
    const catId = fCatalogId ? Number(fCatalogId) : null;
    if (!editing) {
      if (!name) { toast.push('error', 'Вкажіть запис постачальника'); return; }
      if (kind === 'values' && !fParentName.trim()) {
        toast.push('error', "Вкажіть атрибут, до якого належить значення"); return;
      }
      if (fActive && !catId) {
        toast.push('error', "Оберіть внутрішній об'єкт або статус «Не імпортувати»");
        return;
      }
    }
    setSaving(true);
    try {
      if (editing) {
        await api.put(`/mappings/${kind}/${editing.id}`, {
          catalog_item_id: catId,   // explicit null clears the target
          is_active: fActive,
        });
        toast.push('success', 'Маппінг оновлено');
      } else {
        await api.post(`/mappings/${kind}`, {
          ...(fScope ? { supplier_code: fScope } : {}),
          supplier_item_name: name,
          ...(kind === 'values' ? { supplier_parent_name: fParentName.trim() } : {}),
          catalog_item_id: catId,
          is_active: fActive,
        });
        toast.push('success', 'Маппінг створено');
      }
      closeMappingModal(); reload();
    } catch (e: unknown) {
      toast.push('error', (e as Error).message);
    } finally { setSaving(false); }
  };

  const sortIndicator = (key: SortKey) =>
    sortBy === key ? (sortDir === 'asc' ? '▲' : '▼') : '↕';

  return (
    <div>
      <PageHeader title="Маппінг" />
      <p className="text-xs text-gray-400 mb-4">
        Нормалізація даних постачальників під час імпорту товарів.
        Статус <Badge tone="green">Маппінг</Badge> — запис перетворюється на внутрішній;
        <Badge tone="red">Не імпортувати</Badge> — запис пропускається під час імпорту.
      </p>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-gray-200 flex-wrap">
        {TABS.map((t) => (
          <button key={t.key} onClick={() => { setKind(t.key); setAppliedQ(''); setQ(''); }}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition ${
              kind === t.key ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-800'
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Toolbar */}
      <div className="bg-white border border-gray-200 rounded-lg p-3 mb-4 flex flex-wrap gap-3 items-end">
        <div className="w-64">
          <label className="block text-xs text-gray-500 mb-1">Пошук</label>
          <Input value={q} onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') setAppliedQ(q); }}
            placeholder={`Постачальник, ${COLUMN_LABELS[kind].supplierItem.toLowerCase()}…`} />
        </div>
        <div className="w-40">
          <label className="block text-xs text-gray-500 mb-1">Статус</label>
          <Select value={fStatus} onChange={(e) => setFStatus(e.target.value)}>
            <option value="">Усі</option>
            <option value="true">Маппінг</option>
            <option value="false">Не імпортувати</option>
          </Select>
        </div>
        <div className="w-44">
          <label className="block text-xs text-gray-500 mb-1">Прив&apos;язка</label>
          <Select value={fMapped} onChange={(e) => setFMapped(e.target.value)}>
            <option value="">Усі</option>
            <option value="true">Прив&apos;язано</option>
            <option value="false">Без прив&apos;язки</option>
          </Select>
        </div>
        <div className="w-44">
          <label className="block text-xs text-gray-500 mb-1">Область</label>
          <Select value={fScope} onChange={(e) => setFScope(e.target.value)}>
            <option value="">Усі</option>
            <option value="global">Глобальний</option>
            {suppliers.map((sp) => <option key={sp.code} value={sp.code}>{sp.name}</option>)}
          </Select>
        </div>
        <Button variant="secondary" onClick={() => setAppliedQ(q)}>Застосувати</Button>
        {hasFilters && (
          <Button variant="ghost" onClick={resetFilters}>Скинути фільтри</Button>
        )}
        <div className="ml-auto">
          <Button onClick={openCreate}>＋ Додати маппінг</Button>
        </div>
      </div>

      {error && <ErrorState message={error} onRetry={reload} />}
      {!error && loading && <LoadingState label="Завантаження маппінгу..." />}
      {!error && !loading && rows.length === 0 && (
        <p className="text-sm text-gray-400 py-8 text-center">Записів не знайдено.</p>
      )}
      {!error && !loading && rows.length > 0 && (
        <>
          <Table
            head={
              <tr>
                <Th>
                  <button type="button" onClick={() => toggleSort('id')}
                    className="inline-flex items-center gap-1 uppercase tracking-wide hover:text-gray-800">
                    #<span className="text-[10px]" aria-hidden>{sortIndicator('id')}</span>
                  </button>
                </Th>
                <Th>
                  <button type="button" onClick={() => toggleSort('supplier')}
                    className="inline-flex items-center gap-1 uppercase tracking-wide hover:text-gray-800">
                    Область<span className="text-[10px]" aria-hidden>{sortIndicator('supplier')}</span>
                  </button>
                </Th>
                {kind === 'values' && (
                  <Th>
                    <button type="button" onClick={() => toggleSort('attribute')}
                      className="inline-flex items-center gap-1 uppercase tracking-wide hover:text-gray-800">
                      {COLUMN_LABELS[kind].attribute}
                      <span className="text-[10px]" aria-hidden>{sortIndicator('attribute')}</span>
                    </button>
                  </Th>
                )}
                <Th>
                  <button type="button" onClick={() => toggleSort('supplier_item')}
                    className="inline-flex items-center gap-1 uppercase tracking-wide hover:text-gray-800">
                    {COLUMN_LABELS[kind].supplierItem}
                    <span className="text-[10px]" aria-hidden>{sortIndicator('supplier_item')}</span>
                  </button>
                </Th>
                <Th>
                  <button type="button" onClick={() => toggleSort('catalog')}
                    className="inline-flex items-center gap-1 uppercase tracking-wide hover:text-gray-800">
                    {COLUMN_LABELS[kind].catalog}
                    <span className="text-[10px]" aria-hidden>{sortIndicator('catalog')}</span>
                  </button>
                </Th>
                <Th>
                  <button type="button" onClick={() => toggleSort('status')}
                    className="inline-flex items-center gap-1 uppercase tracking-wide hover:text-gray-800">
                    Статус<span className="text-[10px]" aria-hidden>{sortIndicator('status')}</span>
                  </button>
                </Th>
                <Th>
                  <button type="button" onClick={() => toggleSort('updated_at')}
                    className="inline-flex items-center gap-1 uppercase tracking-wide hover:text-gray-800">
                    Оновлено<span className="text-[10px]" aria-hidden>{sortIndicator('updated_at')}</span>
                  </button>
                </Th>
                <Th className="w-32"></Th>
              </tr>
            }
          >
            {rows.map((row) => (
              <tr key={row.id} className="hover:bg-gray-50">
                <Td className="font-mono text-xs text-gray-400">{row.id}</Td>
                <Td className="text-sm">
                  {row.is_global
                    ? <Badge tone="blue">Глобальний</Badge>
                    : <>{row.supplier_name}
                        <span className="block font-mono text-[10px] text-gray-400">{row.supplier_code}</span></>}
                </Td>
                {kind === 'values' && (
                  <Td className="text-sm break-all max-w-[200px]">
                    {row.holder_name || <span className="text-gray-400">—</span>}
                  </Td>
                )}
                <Td className="text-sm break-all max-w-[280px]">{row.supplier_item_name}</Td>
                <Td className="text-sm break-all max-w-[280px]">
                  {row.catalog_name || <span className="text-gray-400">—</span>}
                </Td>
                <Td>
                  <button
                    type="button"
                    onClick={() => toggleStatus(row)}
                    disabled={togglingId === row.id}
                    title={row.is_active
                      ? 'Перемкнути у статус «Не імпортувати»'
                      : row.catalog_item_id
                        ? 'Перемкнути у статус «Маппінг»'
                        : 'Підключіть внутрішній об’єкт (Змінити), щоб активувати'}
                    className={`cursor-pointer disabled:opacity-50 ${row.is_active ? '' : 'opacity-80'}`}
                  >
                    {row.is_active
                      ? <Badge tone="green">Маппінг</Badge>
                      : <Badge tone="red">Не імпортувати</Badge>}
                  </button>
                </Td>
                <Td className="whitespace-nowrap text-xs text-gray-500">
                  {formatDateTime(row.updated_at)}
                </Td>
                <Td>
                  <div className="flex gap-1">
                    <Button size="sm" variant="secondary" onClick={() => openEdit(row)}>Змінити</Button>
                    <Button size="sm" variant="ghost" className="text-red-600"
                      onClick={() => setDeleting(row)}>✕</Button>
                  </div>
                </Td>
              </tr>
            ))}
          </Table>
          <Pagination
            page={page}
            pages={Math.max(1, Math.ceil(total / perPage))}
            total={total}
            onPage={(p) => setPage(p)}
            pageSize={perPage}
            onPageSizeChange={(n) => { setPerPage(n); setPage(1); }}
          />
        </>
      )}
      {/* Create / edit modal */}
      <Modal
        open={modalOpen}
        title={editing ? `Редагувати маппінг #${editing.id}` : 'Новий маппінг'}
        onClose={closeMappingModal}
      >
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Область дії</label>
            {editing ? (
              <div className="text-sm bg-gray-50 border border-gray-100 rounded px-3 py-2 w-full">
                {editing.is_global ? 'Глобальний (усі постачальники)' : (editing.supplier_name + '')}
              </div>
            ) : (
              <>
                <Select value={fScope} onChange={(e) => setFScope(e.target.value)} className="w-full">
                  <option value="">Глобальний — застосовується до всіх постачальників</option>
                  {suppliers.map((sp) => (
                    <option key={sp.code} value={sp.code}>{sp.name} — тільки цей постачальник</option>
                  ))}
                </Select>
                <p className="text-xs text-gray-400 mt-1">
                  За замовчуванням маппінг створюється глобальним. Постачальник обирається
                  лише для точкового перевизначення.
                </p>
              </>
            )}
          </div>

          <div>
            <label className="block text-xs text-gray-500 mb-1">
              {COLUMN_LABELS[kind].supplierItem} *
            </label>
            <Input value={fItemName} disabled={!!editing} className="w-full"
              onChange={(e) => setFItemName(e.target.value)}
              placeholder={
                kind === 'values'
                  ? 'Значення з фіду, напр. Black'
                  : kind === 'attributes'
                    ? 'Назва атрибута з фіду'
                    : 'Назва категорії з фіду'
              } />
          </div>

          {!editing && kind === 'values' && (
            <div>
              <label className="block text-xs text-gray-500 mb-1">
                Атрибут, до якого належить значення *
              </label>
              <Input value={fParentName} className="w-full"
                onChange={(e) => setFParentName(e.target.value)}
                placeholder="Напр., Колір" />
            </div>
          )}

          <div>
            <label className="block text-xs text-gray-500 mb-1">Статус *</label>
            <Select value={fActive ? 'map' : 'exclude'} className="w-full"
              onChange={(e) => {
                const active = e.target.value === 'map';
                setFActive(active);
                if (!active) { setFCatalogId(''); setFInternalAttrId(''); setValOpts([]); }
              }}>
              <option value="map">Маппінг</option>
              <option value="exclude">Не імпортувати</option>
            </Select>
          </div>

          {fActive && kind !== 'values' && (
            <div>
              <label className="block text-xs text-gray-500 mb-1">
                {COLUMN_LABELS[kind].catalog} *
              </label>
              <Select value={fCatalogId} className="w-full"
                onChange={(e) => setFCatalogId(e.target.value)}>
                <option value="">Оберіть…</option>
                {(kind === 'categories' ? cats : attrs).map((o) => (
                  <option key={o.id} value={o.id}>{o.name}</option>
                ))}
              </Select>
            </div>
          )}

          {fActive && kind === 'values' && (
            <>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Внутрішній атрибут</label>
                <Select value={fInternalAttrId} className="w-full"
                  onChange={(e) => loadValuesForAttr(e.target.value)}>
                  <option value="">Оберіть атрибут…</option>
                  {attrs.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
                </Select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Внутрішнє значення *</label>
                <Select value={fCatalogId} className="w-full" disabled={!fInternalAttrId}
                  onChange={(e) => setFCatalogId(e.target.value)}>
                  <option value="">
                    {fInternalAttrId ? 'Оберіть…' : 'Спочатку оберіть атрибут'}
                  </option>
                  {valOpts.map((v) => (
                    <option key={v.id} value={v.id}>{v.value}</option>
                  ))}
                </Select>
              </div>
            </>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={closeMappingModal}>Скасувати</Button>
            <Button loading={saving} onClick={save}>
              {editing ? 'Зберегти зміни' : 'Створити'}
            </Button>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        title="Видалити маппінг?"
        message={deleting
          ? `Ви впевнені, що хочете видалити цей маппінг? «${deleting.supplier_item_name}» буде відв’язано. Внутрішні атрибути/категорії каталогу не видаляються.`
          : ''}
        confirmLabel="Видалити"
        danger
        onConfirm={doDelete}
        onCancel={() => setDeleting(null)}
      />
    </div>
  );
}




