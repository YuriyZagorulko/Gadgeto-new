'use client';

import { useState } from 'react';

export interface AttrRow {
  key: string;
  id?: number; // existing product_attributes.id
  attributeId: number | null;
  attributeName?: string;
  valueText: string;
  valueId?: number | null;
}

interface Props {
  rows: AttrRow[];
  allAttributes: { id: number; name: string }[];
  /** Optional known values per attribute id -> datalist suggestions */
  attrValuesByAttribute?: Record<number, { id: number | null; value: string }[]>;
  onChange: (rows: AttrRow[]) => void;
}

/**
 * Editable product-attributes table: pick an attribute, choose or type a value,
 * remove rows, add new ones. Fully controlled by the parent.
 */
export default function AttributesEditor({ rows, allAttributes, attrValuesByAttribute = {}, onChange }: Props) {
  const update = (key: string, patch: Partial<AttrRow>) =>
    onChange(rows.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  const remove = (key: string) => onChange(rows.filter((r) => r.key !== key));
  const addRow = () =>
    onChange([
      ...rows,
      { key: 'new-' + Date.now() + '-' + Math.random().toString(36).slice(2, 7), attributeId: null, valueText: '' },
    ]);

  const valuesFor = (attributeId: number | null) =>
    attributeId != null ? attrValuesByAttribute[attributeId] ?? [] : [];

  return (
    <div className="space-y-3">
            <div className="overflow-x-auto rounded-lg border border-blue-200/50">
        <table className="w-full text-sm">
          <thead className="bg-gray-800/60 text-left text-gray-300">
            <tr>
              <th className="px-3 py-2 font-medium w-64">Характеристика</th>
              <th className="px-3 py-2 font-medium">Значення</th>
              <th className="px-3 py-2 font-medium w-24 text-right">Дії</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={3} className="px-3 py-6 text-center text-gray-500">
                  Характеристики не задані
                </td>
              </tr>
            )}
            {rows.map((r) => (
                            <tr key={r.key} className="border-t border-blue-100/60">
                <td className="px-3 py-2 align-top">
                  <select
                    className="input-field w-full"
                    value={r.attributeId ?? ''}
                    onChange={(e) => {
                      const id = e.target.value ? Number(e.target.value) : null;
                      const name = allAttributes.find((a) => a.id === id)?.name;
                      update(r.key, { attributeId: id, attributeName: name, valueId: null });
                    }}
                  >
                    <option value="">— оберіть —</option>
                    {allAttributes.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-3 py-2 align-top">
                  {valuesFor(r.attributeId).length > 0 ? (
                    <>
                      <input
                        list={`vals-${r.key}`}
                        className="input-field w-full"
                        value={r.valueText}
                        placeholder="Оберіть або введіть значення"
                        onChange={(e) => {
                          const text = e.target.value;
                          // Check if the typed value matches a known suggestion
                          const matched = valuesFor(r.attributeId).find((v: any) => v.value === text);
                          update(r.key, { valueText: text, valueId: matched ? matched.id : null });
                        }}
                      />
                      <datalist id={`vals-${r.key}`}>
                        {valuesFor(r.attributeId).map((v, i) => (
                          <option key={v.id ?? 'v' + i} value={v.value} />
                        ))}
                      </datalist>
                    </>
                  ) : (
                    <input
                      className="input-field w-full"
                      value={r.valueText}
                      placeholder="Напр.: 16 GB"
                      onChange={(e) => update(r.key, { valueText: e.target.value })}
                    />
                  )}
                </td>
                <td className="px-3 py-2 align-top text-right">
                  <button type="button" onClick={() => remove(r.key)} className="text-red-400 hover:text-red-300">
                    Видалити
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button type="button" onClick={addRow} className="btn-outline text-sm">
        + Додати характеристику
      </button>
    </div>
  );
}
