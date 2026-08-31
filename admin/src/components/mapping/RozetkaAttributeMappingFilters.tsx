'use client';

import { useState } from 'react';
import { Select, Button } from '@/components/ui';
import EntityMultiSelect from '@/components/mapping/EntityMultiSelect';

export interface RozetkaAttributeMappingFilters {
  internalAttrIds: string;       // comma-separated internal attribute IDs
  externalAttrIds: string;       // comma-separated external (Rozetka) attribute IDs
  externalCategoryIds: string;   // comma-separated external category IDs
  statusFilter: string;
  scopeFilter: string;
}

interface Props {
  onApply: (filters: RozetkaAttributeMappingFilters) => void;
}

export default function RozetkaAttributeMappingFilterPanel({ onApply }: Props) {
  const [internalAttrIds, setInternalAttrIds] = useState<(string | number)[]>([]);
  const [externalAttrIds, setExternalAttrIds] = useState<(string | number)[]>([]);
  const [externalCategoryIds, setExternalCategoryIds] = useState<(string | number)[]>([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [scopeFilter, setScopeFilter] = useState('');

  const hasFilters = !!(internalAttrIds.length || externalAttrIds.length ||
    externalCategoryIds.length || statusFilter || scopeFilter);

  const apply = () => {
    onApply({
      internalAttrIds: internalAttrIds.join(','),
      externalAttrIds: externalAttrIds.join(','),
      externalCategoryIds: externalCategoryIds.join(','),
      statusFilter,
      scopeFilter,
    });
  };

  const reset = () => {
    setInternalAttrIds([]);
    setExternalAttrIds([]);
    setExternalCategoryIds([]);
    setStatusFilter('');
    setScopeFilter('');
    onApply({
      internalAttrIds: '',
      externalAttrIds: '',
      externalCategoryIds: '',
      statusFilter: '',
      scopeFilter: '',
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
        <label className="block text-xs text-gray-500 mb-1">Scope</label>
        <Select value={scopeFilter} onChange={(e) => setScopeFilter(e.target.value)}>
          <option value="">Усі</option>
          <option value="global">Глобальні</option>
          <option value="category">Категорійні</option>
        </Select>
      </div>
      <Button onClick={apply}>Застосувати</Button>
      {hasFilters && (
        <Button variant="ghost" onClick={reset}>Скинути</Button>
      )}
    </div>
  );
}