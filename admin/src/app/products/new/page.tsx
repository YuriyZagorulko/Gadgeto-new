'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { PageHeader, Button, ErrorState } from '@/components/ui';
import { useProductForm, ProductFormFields } from '@/components/ProductForm';

export default function NewProductPage() {
  const router = useRouter();
  const form = useProductForm();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const save = async () => {
    if (!form.values.name.trim()) { setError('Вкажіть назву товару'); return; }
    setSaving(true); setError('');
    try {
      const res = await api.post<{ id: number }>('/products', form.payload());
      router.push(`/products/${res.id}`);
    } catch (e: unknown) {
      setError((e as Error).message);
      setSaving(false);
    }
  };

  if (form.error) return <ErrorState message={form.error} />;

  return (
    <div>
      <PageHeader
        title="Новий товар"
        actions={
          <div className="flex gap-2">
            <Link href="/products"><Button variant="secondary">Скасувати</Button></Link>
            <Button onClick={save} loading={saving}>Створити</Button>
          </div>
        }
      />
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-md p-3 mb-4" role="alert">{error}</div>
      )}
      <ProductFormFields {...form} />
    </div>
  );
}
