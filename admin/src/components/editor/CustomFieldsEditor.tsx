'use client';

export interface CustomField {
  name: string;
  value: string;
}

/** Dynamic key/value custom fields editor (controlled). */
export default function CustomFieldsEditor({
  fields,
  onChange,
}: {
  fields: CustomField[];
  onChange: (next: CustomField[]) => void;
}) {
  const update = (i: number, patch: Partial<CustomField>) =>
    onChange(fields.map((f, idx) => (idx === i ? { ...f, ...patch } : f)));

  return (
    <div className="space-y-2">
      {fields.length === 0 && (
        <p className="text-sm text-gray-500">Користувацьких полів немає.</p>
      )}
      {fields.map((f, i) => (
        <div key={i} className="flex items-center gap-2">
          <input
            value={f.name}
            onChange={(e) => update(i, { name: e.target.value })}
            placeholder="Назва поля (напр. EAN)"
            className="w-56 rounded border border-gray-300 bg-white px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          />
          <input
            value={f.value}
            onChange={(e) => update(i, { value: e.target.value })}
            placeholder="Значення"
            className="flex-1 rounded border border-gray-300 bg-white px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          />
          <button
            type="button"
            onClick={() => onChange(fields.filter((_, idx) => idx !== i))}
            className="rounded px-2 py-1 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-950"
            title="Видалити поле"
          >
            ✕
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={() => onChange([...fields, { name: '', value: '' }])}
        className="rounded border border-dashed border-gray-400 px-3 py-1.5 text-sm text-gray-600 hover:border-blue-500 hover:text-blue-600 dark:border-zinc-600 dark:text-zinc-300"
      >
        + Додати користувацьке поле
      </button>
    </div>
  );
}
