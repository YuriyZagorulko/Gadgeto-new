'use client';

import { useState, useCallback } from 'react';
import { Input, Select, Button } from '@/components/ui';
import EntityMultiSelect from '@/components/mapping/EntityMultiSelect';

export interface ImportAttributeValueMappingFilters {
  /** Text search across supplier attribute + supplier value + internal value + internal attr */
  q: string;
  appliedQ: string;
  /** Comma-separated supplier attribute (holder) IDs */
  supplierAttrIds: string;
  /** Text search on supplier attribute (holder) name */
  supplierAttrQ: string;
  /** Text search on supplier value */
  supplierValueQ: string;
  fStatus: string;
  fMapped: string;
  fScope: string;
}

interface Props {
  onApply: (filters: ImportAttributeValueMappingFilters) => void;
  suppliers: { id: number; code: string; name: string }[];
  initialFilters?: ImportAttributeValueMappingFilters;
}

export default function ImportAttributeValueMappingFilterPanel({
  onApply,
  suppliers,
  initialFilters,
}: Props) {
  const [q, setQ] = useState(initialFilters?.q ?? '');
  const [supplierAttrIds, setSupplierAttrIds] = useState<(string | number)[]>(
    initialFilters?.supplierAttrIds
      ? initialFilters.supplierAttrIds.split(',').filter(Boolean).map(Number)
      : [],
  );
  const [supplierAttrQ, setSupplierAttrQ] = useState(initialFilters?.supplierAttrQ ?? '');
  const [supplierValueQ, setSupplierValueQ] = useState(initialFilters?.supplierValueQ ?? '');
  const [fStatus, setFStatus] = useState(initialFilters?.fStatus ?? '');
  const [fMapped, setFMapped] = useState(initialFilters?.fMapped ?? '');
  const [fScope, setFScope] = useState(initialFilters?.fScope ?? '');

  const hasFilters = !!(
    q || supplierAttrIds.length || supplierAttrQ || supplierValueQ ||
    fStatus || fMapped || fScope
  );

  const apply = useCallback(() => {
    onApply({
      q,
      appliedQ: q,
      supplierAttrIds: supplierAttrIds.join(','),
      supplierAttrQ,
      supplierValueQ,
      fStatus,
      fMapped,
      fScope,
    });
  }, [q, supplierAttrIds, supplierAttrQ, supplierValueQ, fStatus, fMapped, fScope, onApply]);

  const reset = useCallback(() => {
    setQ('');
    setSupplierAttrIds([]);
    setSupplierAttrQ('');
    setSupplierValueQ('');
    setFStatus('');
    setFMapped('');
    setFScope('');
    onApply({
      q: '',
      appliedQ: '',
      supplierAttrIds: '',
      supplierAttrQ: '',
      supplierValueQ: '',
      fStatus: '',
      fMapped: '',
      fScope: '',
    });
  }, [onApply]);

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-3 mb-4 flex flex-wrap gap-3 items-end">
      {/* Пошук — text search across all value-related columns */}
      <div className="w-64">
        <label className="block text-xs text-gray-500 mb-1">Пошук</label>
        <Input value={q} onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') apply(); }}
          placeholder="Атрибут постачальника, значення…" />
      </div>

      {/* Батьківський атрибут — supplier attribute EntityMultiSelect */}
      <div className="w-56">
        <EntityMultiSelect
          endpoint="/mappings/supplier-attributes"
          label="Батьківський атрибут"
          selected={supplierAttrIds}
          onChange={setSupplierAttrIds}
          idKey="id"
          nameKey="supplier_name"
          placeholder="Введіть для пошуку атрибута..."
          perPage={50}
        />
      </div>

      {/* Атрибут постачальника — supplier attribute text search */}
      <div className="w-48">
        <label className="block text-xs text-gray-500 mb-1">Атрибут постачальника</label>
        <Input value={supplierAttrQ} onChange={(e) => setSupplierAttrQ(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') apply(); }}
          placeholder="Назва атрибута..." />
      </div>

      {/* Значення атрибута постачальника — supplier value text search */}
      <div className="w-48">
        <label className="block text-xs text-gray-500 mb-1">Значення атрибута постачальника</label>
        <Input value={supplierValueQ} onChange={(e) => setSupplierValueQ(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') apply(); }}
          placeholder="Значення..." />
      </div>

      {/* Статус */}
      <div className="w-40">
        <label className="block text-xs text-gray-500 mb-1">Статус</label>
        <Select value={fStatus} onChange={(e) => setFStatus(e.target.value)}>
          <option value="">Усі</option>
          <option value="true">Маппінг</option>
          <option value="false">Не імпортувати</option>
        </Select>
      </div>

      {/* Прив'язка */}
      <div className="w-44">
        <label className="block text-xs text-gray-500 mb-1">Прив&apos;язка</label>
        <Select value={fMapped} onChange={(e) => setFMapped(e.target.value)}>
          <option value="">Усі</option>
          <option value="true">Прив&apos;язано</option>
          <option value="false">Без прив&apos;язки</option>
        </Select>
      </div>

      {/* Область */}
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