'use client';

import { useState, useEffect } from 'react';
import { Select, Button } from '@/components/ui';
import EntityMultiSelect, {
  useInternalCategories,
  InternalParentCategorySelect,
  type CatOpt,
} from '@/components/mapping/EntityMultiSelect';

export interface RozetkaCategoryMappingFilters {
  internalParentCategoryIds: string; // comma-separated parent category IDs
  externalCategoryIds: string;       // comma-separated external (Rozetka) category IDs
  statusFilter: string;
}

interface Props {
  onApply: (filters: RozetkaCategoryMappingFilters) => void;
}

export default function RozetkaCategoryMappingFilterPanel({ onApply }: Props) {
  const [internalParentCategoryIds, setInternalParentCategoryIds] = useState<(string | number)[]>([]);
  const [externalCategoryIds, setExternalCategoryIds] = useState<(string | number)[]>([]);
  const [statusFilter, setStatusFilter] = useState('');
  const { cats, loading } = useInternalCategories();

  const hasFilters = !!(internalParentCategoryIds.length || externalCategoryIds.length || statusFilter);

  const apply = () => {
    onApply({
      internalParentCategoryIds: internalParentCategoryIds.join(','),
      externalCategoryIds: externalCategoryIds.join(','),
      statusFilter,
    });
  };

  const reset = () => {
    setInternalParentCategoryIds([]);
    setExternalCategoryIds([]);
    setStatusFilter('');
    onApply({
      internalParentCategoryIds: '',
      externalCategoryIds: '',
      statusFilter: '',
    });
  };

  return (
    <div className="flex flex-wrap items-end gap-3 mb-4">
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
          extraParams={{ parents_only: '1' }}
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