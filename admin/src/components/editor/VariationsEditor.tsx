'use client';

import { useState } from 'react';
import { Input, Select, Button } from '@/components/ui';

/**
 * Props-driven variations editor.
 * The parent page owns all state and persistence; this component only
 * renders/edit rows and can expand attribute combinations into rows.
 */

export type VarAttr = { name: string; value: string };

export type VariationRow = {
  key: string; // stable signature of the attribute combination
  attrs: VarAttr[];
  sku: string;
  price: number | '';
  sale_price: number | '';
  stock_qty: number | '';
  stock_status: string;
  image_url: string;
  barcode: string;
};

type AttrDef = { name: string; values: string[] };

const comboKey = (attrs: VarAttr[]) =>
  attrs.map((a) => `${a.name}:${a.value}`).sort().join('|');

function cartesian(attrs: AttrDef[]): VarAttr[][] {
  let acc: VarAttr[][] = [[]];
  for (const def of attrs) {
    const next: VarAttr[][] = [];
    for (const prefix of acc) {
      for (const v of def.values) {
        if (!v.trim()) continue;
        next.push([...prefix, { name: def.name, value: v.trim() }]);
      }
    }
    acc = next;
  }
  return acc;
}

const emptyRow = (attrs: VarAttr[]): VariationRow => ({
  key: comboKey(attrs),
  attrs,
  sku: '',
  price: '',
  sale_price: '',
  stock_qty: '',
  stock_status: 'in_stock',
  image_url: '',
  barcode: '',
});

export default function VariationsEditor({
  attributes,
  rows,
  onChange,
}: {
  attributes: AttrDef[];
  rows: VariationRow[];
  onChange: (rows: VariationRow[]) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  const usable = attributes.filter((a) => a.values.some((v) => v.trim()));

  const generate = () => {
    const combos = cartesian(usable);
    const existing = new Map(rows.map((r) => [r.key, r]));
    const merged = combos.map((c) => existing.get(comboKey(c)) ?? emptyRow(c));
    onChange(merged);
    setExpanded(true);
  };

  const update = (key: string, patch: Partial<VariationRow>) =>
    onChange(rows.map((r) => (r.key === key ? { ...r, ...patch } : r)));

  const remove = (key: string) => onChange(rows.filter((r) => r.key !== key));

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="text-sm text-gray-600">
          {usable.length === 0
            ? 'Позначте характеристики як «для варіацій» у розділі «Характеристики».'
            : `Варіацій: ${rows.length}`}
        </div>
        <Button variant="secondary" onClick={generate} disabled={usable.length === 0}>
          Згенерувати комбінації
        </Button>
      </div>

      {rows.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs text-gray-500 uppercase">
              <tr>
                <th className="px-3 py-2 font-medium">Комбінація</th>
                <th className="px-3 py-2 font-medium w-36">SKU</th>
                <th className="px-3 py-2 font-medium w-28">Ціна</th>
                <th className="px-3 py-2 font-medium w-28">Акція</th>
                <th className="px-3 py-2 font-medium w-24">Залишок</th>
                <th className="px-3 py-2 font-medium w-40">Статус</th>
                <th className="px-3 py-2 font-medium w-48">EAN</th>
                <th className="px-3 py-2 font-medium w-10"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {(expanded ? rows : rows.slice(0, 8)).map((r) => (
                <tr key={r.key} className="hover:bg-gray-50/60">
                  <td className="px-3 py-2 whitespace-nowrap">
                    {r.attrs.map((a) => (
                      <span key={a.name} className="mr-2 inline-block rounded bg-blue-50 px-1.5 py-0.5 text-xs text-blue-700">
                        {a.name}: {a.value}
                      </span>
                    ))}
                  </td>
                  <td className="px-2 py-1.5"><Input value={r.sku} onChange={(e) => update(r.key, { sku: e.target.value })} /></td>
                  <td className="px-2 py-1.5"><Input type="number" min={0} value={r.price} onChange={(e) => update(r.key, { price: e.target.value === '' ? '' : Number(e.target.value) })} /></td>
                  <td className="px-2 py-1.5"><Input type="number" min={0} value={r.sale_price} onChange={(e) => update(r.key, { sale_price: e.target.value === '' ? '' : Number(e.target.value) })} /></td>
                  <td className="px-2 py-1.5"><Input type="number" min={0} value={r.stock_qty} onChange={(e) => update(r.key, { stock_qty: e.target.value === '' ? '' : Number(e.target.value) })} /></td>
                  <td className="px-2 py-1.5">
                    <Select value={r.stock_status} onChange={(e) => update(r.key, { stock_status: e.target.value })}>
                      <option value="in_stock">В наявності</option>
                      <option value="out_of_stock">Немає в наявності</option>
                      <option value="backorder">Під замовлення</option>
                    </Select>
                  </td>
                  <td className="px-2 py-1.5"><Input value={r.barcode} onChange={(e) => update(r.key, { barcode: e.target.value })} /></td>
                  <td className="px-2 py-1.5">
                    <Button variant="danger" onClick={() => remove(r.key)} aria-label="Видалити">×</Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!expanded && rows.length > 8 && (
            <button className="w-full py-2 text-sm text-blue-600 hover:bg-blue-50" onClick={() => setExpanded(true)}>
              Показати всі {rows.length} варіацій…
            </button>
          )}
        </div>
      )}
    </div>
  );
}
