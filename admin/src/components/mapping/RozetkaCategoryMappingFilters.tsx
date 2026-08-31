'use client';

import { useState, useEffect } from 'react';
import { Input, Select, Button } from '@/components/ui';
import EntityMultiSelect, {
  useInternalCategories,
  InternalParentCategorySelect,
  type CatOpt,
} from '@/components/mapping/EntityMultiSelect';

export interface RozetkaCategoryMappingFilters {
  internalCategoryName: string;       // free-text filter by internal category name
  internalParentCategoryIds: string; // comma-separated parent category IDs
  externalCategoryIds: string;       // comma-separated external (Rozetka) category IDs
  statusFilter: string;
}

interface Props {
  onApply: (filters: RozetkaCategoryMappingFilters) => void;
}

export default function RozetkaCategoryMappingFilterPanel({ onApply }: Props) {
  const [internalCategoryName, setInternalCategoryName] = useState('');
  const [internalParentCategoryIds, setInternalParentCategoryIds] = useState<(string | number)[]>([]);
  const [externalCategoryIds, setExternalCategoryIds] = useState<(string | number)[]>([]);
  const [statusFilter, setStatusFilter] = useState('');
  const { cats, loading } = useInternalCategories();

  const hasFilters = !!(internalCategoryName || internalParentCategoryIds.length || externalCategoryIds.length || statusFilter);

  const apply = () => {
    onApply({
      internalCategoryName,
      internalParentCategoryIds: internalParentCategoryIds.join(','),
      externalCategoryIds: externalCategoryIds.join(','),
      statusFilter,
    });
  };

  const reset = () => {
    setInternalCategoryName('');
    setInternalParentCategoryIds([]);
    setExternalCategoryIds([]);
    setStatusFilter('');
    onApply({
      internalCategoryName: '',
      internalParentCategoryIds: '',
      externalCategoryIds: '',
      statusFilter: '',
    });
  };

  return (
    <div className="flex flex-wrap items-end gap-3 mb-4">
      <div>
        <label className="block text-xs text-gray-500 mb-1">Назва категорії</label>
        <Input value={internalCategoryName} onChange={(e) => setInternalCategoryName(e.target.value)}
          placeholder="Пошук за назвою категорії..." className="w-48"
          onKeyDown={(e) => { if (e.key === 'Enter') apply(); }} />
      </div>
      <div className="w-64">
        <InternalParentCategorySelect
          label="Батьківська внутрішня категорія"
          selected={internalParentCategoryIds}
          onChange={setInternalParentCategoryIds}
          cats={cats}
          loading={loading}
        />
      </div>
      <div className="w-64">
        <EntityMultiSelect
          endpoint="/export/channels/rozetka/pickers/external-categories"
          label="Категорія Rozetka"
          selected={externalCategoryIds}
          onChange={setExternalCategoryIds}
          idKey="external_id"
          nameKey="name"
          placeholder="Введіть для пошуку категорій Rozetka..."
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
      <Button onClick={apply}>Застосувати</Button>
      {hasFilters && (
        <Button variant="ghost" onClick={reset}>Скинути</Button>
      )}
    </div>
  );
}