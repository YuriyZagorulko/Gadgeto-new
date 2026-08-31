'use client';

import { useState } from 'react';
import { Input, Select, Button } from '@/components/ui';

export interface CategoryMappingFilters {
  internalQ: string;
  externalQ: string;
  statusFilter: string;
}

interface Props {
  onApply: (filters: CategoryMappingFilters) => void;
}

export default function CategoryMappingFilterPanel({ onApply }: Props) {
  const [internalQ, setInternalQ] = useState('');
  const [externalQ, setExternalQ] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  const hasFilters = !!(internalQ || externalQ || statusFilter);

  const apply = () => {
    onApply({ internalQ, externalQ, statusFilter });
  };

  const reset = () => {
    setInternalQ('');
    setExternalQ('');
    setStatusFilter('');
    onApply({ internalQ: '', externalQ: '', statusFilter: '' });
  };

  return (
    <div className="flex flex-wrap items-end gap-3 mb-4">
      <div>
        <label className="block text-xs text-gray-500 mb-1">Внутрішня категорія</label>
        <Input value={internalQ} onChange={(e) => setInternalQ(e.target.value)}
          placeholder="Пошук внутрішньої категорії..." className="w-48"
          onKeyDown={(e) => { if (e.key === 'Enter') apply(); }} />
      </div>
      <div>
        <label className="block text-xs text-gray-500 mb-1">Категорія Rozetka</label>
        <Input value={externalQ} onChange={(e) => setExternalQ(e.target.value)}
          placeholder="Пошук категорії Rozetka..." className="w-48"
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
      <Button onClick={apply}>Застосувати</Button>
      {hasFilters && (
        <Button variant="ghost" onClick={reset}>Скинути</Button>
      )}
    </div>
  );
}