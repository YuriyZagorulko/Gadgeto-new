'use client';

import { useState } from 'react';
import { Input, Select, Button } from '@/components/ui';

export interface AttributeValueMappingFilters {
  internalAttrQ: string;
  externalAttrQ: string;
  internalValueQ: string;
  externalValueQ: string;
  extCatFilter: string;
  statusFilter: string;
  attrFilter: string;
  valueMode: 'all' | 'unmapped';
}

interface Props {
  onApply: (filters: AttributeValueMappingFilters) => void;
}

export default function AttributeValueMappingFilterPanel({ onApply }: Props) {
  const [internalAttrQ, setInternalAttrQ] = useState('');
  const [externalAttrQ, setExternalAttrQ] = useState('');
  const [internalValueQ, setInternalValueQ] = useState('');
  const [externalValueQ, setExternalValueQ] = useState('');
  const [extCatFilter, setExtCatFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [attrFilter, setAttrFilter] = useState('');
  const [valueMode, setValueMode] = useState<'all' | 'unmapped'>('all');

  const hasFilters = !!(internalAttrQ || externalAttrQ || internalValueQ || externalValueQ || extCatFilter || statusFilter || attrFilter || valueMode === 'unmapped');

  const apply = () => {
    onApply({ internalAttrQ, externalAttrQ, internalValueQ, externalValueQ, extCatFilter, statusFilter, attrFilter, valueMode });
  };

  const reset = () => {
    setInternalAttrQ(''); setExternalAttrQ(''); setInternalValueQ(''); setExternalValueQ('');
    setExtCatFilter(''); setStatusFilter(''); setAttrFilter(''); setValueMode('all');
    onApply({ internalAttrQ: '', externalAttrQ: '', internalValueQ: '', externalValueQ: '', extCatFilter: '', statusFilter: '', attrFilter: '', valueMode: 'all' });
  };

  return (
    <div className="flex flex-wrap items-end gap-3 mb-4">
      <div>
        <label className="block text-xs text-gray-500 mb-1">Внутрішній атрибут</label>
        <Input value={internalAttrQ} onChange={(e) => setInternalAttrQ(e.target.value)}
          placeholder="Пошук атрибуту..." className="w-48"
          onKeyDown={(e) => { if (e.key === 'Enter') apply(); }} />
      </div>
      <div>
        <label className="block text-xs text-gray-500 mb-1">Атрибут Rozetka</label>
        <Input value={externalAttrQ} onChange={(e) => setExternalAttrQ(e.target.value)}
          placeholder="ID або назва атрибуту..." className="w-48"
          onKeyDown={(e) => { if (e.key === 'Enter') apply(); }} />
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