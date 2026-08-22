'use client';
import React from 'react';

interface AdminPageProps {
  title: string;
  section: string;
  children?: React.ReactNode;
}

export default function AdminPage({ title, section, children }: AdminPageProps) {
  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">{title}</h1>
        <div className="flex gap-2">{/* Action buttons */}</div>
      </div>
      <div className="bg-white rounded-lg shadow p-6">
        {children || (
          <p className="text-gray-500 italic">
            {title} management — implementation in progress.
          </p>
        )}
      </div>
    </div>
  );
}
