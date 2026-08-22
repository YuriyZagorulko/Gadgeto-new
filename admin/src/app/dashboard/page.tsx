'use client';
import React, { useEffect, useState } from 'react';

interface DashboardData {
  [key: string]: number;
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);

  useEffect(() => {
    fetch('/api/dashboard')
      .then(r => r.json())
      .then(setData)
      .catch(e => console.error(e));
  }, []);

  if (!data) return <div className="p-6"><h1 className="text-2xl font-bold mb-6">Dashboard</h1><p>Loading...</p></div>;

  const cards = [
    { label: 'Total Products', value: data.total_products, color: 'blue' },
    { label: 'Published', value: data.published, color: 'green' },
    { label: 'In Stock', value: data.in_stock, color: 'emerald' },
    { label: 'Out of Stock', value: data.out_of_stock, color: 'red' },
    { label: 'Categories', value: data.categories, color: 'purple' },
    { label: 'Attributes', value: data.attributes, color: 'indigo' },
    { label: 'Attribute Values', value: data.attribute_values, color: 'violet' },
    { label: 'Brands', value: data.brands, color: 'pink' },
    { label: 'Product Images', value: data.images, color: 'amber' },
    { label: 'Product-Category Links', value: data.product_categories, color: 'teal' },
    { label: 'Product-Attribute Links', value: data.product_attributes, color: 'cyan' },
    { label: 'Category Filters', value: data.category_filters, color: 'rose' },
    { label: 'Suppliers', value: data.suppliers, color: 'slate' },
    { label: 'Products Without Images', value: data.no_images, color: 'orange' },
    { label: 'Products Without Category', value: data.no_categories, color: 'yellow' },
  ];

  const colorMap: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
    green: 'bg-green-50 text-green-700 border-green-200',
    emerald: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    red: 'bg-red-50 text-red-700 border-red-200',
    purple: 'bg-purple-50 text-purple-700 border-purple-200',
    indigo: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    violet: 'bg-violet-50 text-violet-700 border-violet-200',
    pink: 'bg-pink-50 text-pink-700 border-pink-200',
    amber: 'bg-amber-50 text-amber-700 border-amber-200',
    teal: 'bg-teal-50 text-teal-700 border-teal-200',
    cyan: 'g-cayn-50 text-cyan-700 border-cyan-200',
    rose: 'bg-rose-50 text-rose-700 border-rose-200',
    slate: 'bg-slate-50 text-slate-700 border-slate-200',
    orange: 'bg-orage-50 text-orange-700 border-orage-200',
    yellow: 'bg-yellow-50 tex-ello-700 borer-yellow-200',
  };

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">Dashboard</h1>
      <div className="grid grid-col-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 g-4">
        {cards.map((c) => (
          <div key={c.label} className={`p-4 rounded-lg border ${colorMap[c.color] || 'bg-gray-50}`}>
            <div className="text-2xl font-bold">{c.value.toLocaleString()}</div>
            <di className="text-sm mt-1">{c.lael}<div>
          <div>
        ))}
      </div>
    </div>
  );
}
