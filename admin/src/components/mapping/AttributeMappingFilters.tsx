'use client';

import { useState } from 'react';
import { Input, Select, Button } from '@/components/ui';

export interface AttributeMappingFilters {
  internalQ: string;
  externalQ: string;
  internalCategoryQ: string;
  externalCategoryQ: string;
  statusFilter: string;
  scopeFilter: string;
}

interface Props {
  onApply: (filters: AttributeMappingFilters) => void;
}

export default function AttributeMappingFilterPanel({ onApply }: Props) {
  const [internalQ, setInternalQ] = useState('');
  const [externalQ, setExternalQ] = useState('');
  const [internalCategoryQ, setInternalCategoryQ] = useState('');
  const [externalCategoryQ, setExternalCategoryQ] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [scopeFilter, setScopeFilter] = useState('');

  const hasFilters = !!(internalQ || externalQ || internalCategoryQ || externalCategoryQ || statusFilter || scopeFilter);

  const apply = () => {
    onApply({ internalQ, externalQ, internalCategoryQ, externalCategoryQ, statusFilter, scopeFilter });
  };

  const reset = () => {
    setInternalQ(''); setExternalQ(''); setInternalCategoryQ(''); setExternalCategoryQ('');
    setStatusFilter(''); setScopeFilter('');
    onApply({ internalQ: '', externalQ: '', internalCategoryQ: '', externalCategoryQ: '', statusFilter: '', scopeFilter: '' });
  };

  return (
    <div className="flex flex-wrap items-end gap-3 mb-4">
      <div>
        <label className="block text-xs text-gray-500 mb-1">Внутрішній атрибут</label>
        <Input value={internalQ} onChange={(e) => setInternalQ(e.target.value)}
          placeholder="Пошук атрибуту..." className="w-48"
          onKeyDown={(e) => { if (e.key === 'Enter') apply(); }} />
      </div>
      <div>
        <label className="block text-xs text-gray-500 mb-1">Атрибут Rozetka</label>
        <Input value={externalQ} onChange={(e) => setExternalQ(e.target.value)}
          placeholder="ID або назва атрибуту..." className="w-48"
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