'use client';

import { useState } from 'react';
import { Input, Select, Button } from '@/components/ui';
import EntityMultiSelect from '@/components/mapping/EntityMultiSelect';

export interface RozetkaValueMappingFilters {
  internalAttrIds: string;       // comma-separated internal attribute IDs
  externalAttrIds: string;       // comma-separated external (Rozetka) attribute IDs
  externalCategoryIds: string;   // comma-separated external category IDs
  internalValueQ: string;        // text search on internal value
  externalValueQ: string;        // text search on external value
  statusFilter: string;
  valueMode: 'all' | 'unmapped';
}

interface Props {
  onApply: (filters: RozetkaValueMappingFilters) => void;
}

export default function RozetkaValueMappingFilterPanel({ onApply }: Props) {
  const [internalAttrIds, setInternalAttrIds] = useState<(string | number)[]>([]);
  const [externalAttrIds, setExternalAttrIds] = useState<(string | number)[]>([]);
  const [externalCategoryIds, setExternalCategoryIds] = useState<(string | number)[]>([]);
  const [internalValueQ, setInternalValueQ] = useState('');
  const [externalValueQ, setExternalValueQ] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [valueMode, setValueMode] = useState<'all' | 'unmapped'>('all');

  const hasFilters = !!(internalAttrIds.length || externalAttrIds.length ||
    externalCategoryIds.length || internalValueQ || externalValueQ ||
    statusFilter || valueMode === 'unmapped');

  const apply = () => {
    onApply({
      internalAttrIds: internalAttrIds.join(','),
      externalAttrIds: externalAttrIds.join(','),
      externalCategoryIds: externalCategoryIds.join(','),
      internalValueQ,
      externalValueQ,
      statusFilter,
      valueMode,
    });
  };

  const reset = () => {
    setInternalAttrIds([]);
    setExternalAttrIds([]);
    setExternalCategoryIds([]);
    setInternalValueQ('');
    setExternalValueQ('');
    setStatusFilter('');
    setValueMode('all');
    onApply({
      internalAttrIds: '',
      externalAttrIds: '',
      externalCategoryIds: '',
      internalValueQ: '',
      externalValueQ: '',
      statusFilter: '',
      valueMode: 'all',
    });
  };

  return (
    <div className="flex flex-wrap items-end gap-3 mb-4">
      <div className="w-64">
        <EntityMultiSelect
          endpoint="/attributes"
          label="Внутрішній атрибут"
          selected={internalAttrIds}
          onChange={setInternalAttrIds}
          placeholder="Введіть для пошуку атрибутів..."
        />
      </div>
      <div className="w-72">
        <EntityMultiSelect
          endpoint="/export/channels/rozetka/pickers/external-attributes"
          label="Атрибут Rozetka"
          selected={externalAttrIds}
          onChange={setExternalAttrIds}
          idKey="external_id"
          nameKey="name"
          placeholder="Введіть для пошуку атрибутів Rozetka..."
        />
      </div>
      <div className="w-64">
        <EntityMultiSelect
          endpoint="/export/channels/rozetka/pickers/external-categories"
          label="Контекст — категорія Rozetka"
          selected={externalCategoryIds}
          onChange={setExternalCategoryIds}
          idKey="external_id"
          nameKey="name"
          placeholder="Введіть для пошуку категорій..."
        />
      </div>
      <div>
        <label className="block text-xs text-gray-500 mb-1">Внутрішнє значення</label>
        <Input value={internalValueQ} onChange={(e) => setInternalValueQ(e.target.value)}
          placeholder="Пошук значення..." className="w-48"
          onKeyDown={(e) => { if (e.key === 'Enter') apply(); }} />
      </div>
      <div>
        <label className="block text-xs text-gray-500 mb-1">Значення Rozetka</label>
        <Input value={externalValueQ} onChange={(e) => setExternalValueQ(e.target.value)}
          placeholder="Пошук значення Rozetka..." className="w-48"
          onKeyDown={(e) => { if (e.key === 'Enter') apply(); }} />
      </div>
      <div>
        <label className="block text-xs text-gray-500 mb-1">Статус</label>
        <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">Усі</option>
          <option value="accepted">Прийнято</option>
          <option value="proposed">Запропоновано</option>
          <option value="excluded">Виключено</option>
          <option value="unmapped">Не зіставлено</option>
        </Select>
      </div>
      <div>
        <label className="block text-xs text-gray-500 mb-1">Режим</label>
        <div className="flex gap-0">
          <button onClick={() => { setValueMode('all'); apply(); }}
            className={`px-3 py-1.5 text-xs font-medium border rounded-l ${valueMode === 'all' ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'}`}>Усі маппінги</button>
          <button onClick={() => { setValueMode('unmapped'); apply(); }}
            className={`px-3 py-1.5 text-xs font-medium border rounded-r ${valueMode === 'unmapped' ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'}`}>Не зіставлені</button>
        </div>
      </div>
      <Button onClick={apply}>Застосувати</Button>
      {hasFilters && (
        <Button variant="ghost" onClick={reset}>Скинути</Button>
      )}
    </div>
  );
}