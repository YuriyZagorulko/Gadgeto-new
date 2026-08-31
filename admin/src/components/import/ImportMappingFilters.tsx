'use client';

import { useState } from 'react';
import { Input, Select, Button } from '@/components/ui';

type SupOpt = { id: number; code: string; name: string };

export interface ImportMappingFilters {
  q: string;
  appliedQ: string;
  fStatus: string;
  fMapped: string;
  fScope: string;
}

interface Props {
  onApply: (filters: ImportMappingFilters) => void;
  suppliers: SupOpt[];
  columnLabel: string;
}

export default function ImportMappingFilterPanel({ onApply, suppliers, columnLabel }: Props) {
  const [q, setQ] = useState('');
  const [fStatus, setFStatus] = useState('');
  const [fMapped, setFMapped] = useState('');
  const [fScope, setFScope] = useState('');

  const hasFilters = !!(q || fStatus || fMapped || fScope);

  const apply = () => {
    onApply({ q, appliedQ: q, fStatus, fMapped, fScope });
  };

  const reset = () => {
    setQ('');
    setFStatus('');
    setFMapped('');
    setFScope('');
    onApply({ q: '', appliedQ: '', fStatus: '', fMapped: '', fScope: '' });
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-3 mb-4 flex flex-wrap gap-3 items-end">
      <div className="w-64">
        <label className="block text-xs text-gray-500 mb-1">Пошук</label>
        <Input value={q} onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') apply(); }}
          placeholder={`Постачальник, ${columnLabel.toLowerCase()}…`} />
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
        <label className="block text-xs text-gray-500 mb-1">Прив'язка</label>
        <Select value={fMapped} onChange={(e) => setFMapped(e.target.value)}>
          <option value="">Усі</option>
          <option value="true">Прив'язано</option>
          <option value="false">Без прив'язки</option>
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
      <Button variant="secondary" onClick={apply}>Застосувати</Button>
      {hasFilters && (
        <Button variant="ghost" onClick={reset}>Скинути</Button>
      )}
    </div>
  );
}