'use client';

import { PageHeader } from '@/components/ui';

export default function ExportSettingsPage() {
  return (
    <div>
      <PageHeader title="Налаштування експорту" />
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold mb-2">Загальний експорт каталогу</h2>
        <p className="text-gray-600 text-sm">
          Тут буде реалізовано загальний експорт каталогу в CSV та XML у наступних фазах проєкту.
        </p>
        <div className="mt-4 p-4 bg-gray-50 rounded border border-gray-200">
          <p className="text-gray-500 italic">
            Цей розділ незалежний від маппінгу Rozetka або інших каналів.
            Експорт відбуватиметься безпосередньо з головного каталогу (Master Catalog).
          </p>
        </div>
        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 border border-gray-200 rounded-lg bg-white">
            <h3 className="font-medium text-gray-800">CSV</h3>
            <p className="text-sm text-gray-500 mt-1">Буде реалізовано у Phase 8</p>
          </div>
          <div className="p-4 border border-gray-200 rounded-lg bg-white">
            <h3 className="font-medium text-gray-800">XML</h3>
            <p className="text-sm text-gray-500 mt-1">Буде реалізовано у Phase 8</p>
          </div>
        </div>
      </div>
    </div>
  );
}