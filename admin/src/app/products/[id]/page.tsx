'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import { PageHeader, Button, Table, Th, Td, ErrorState, useToast } from '@/components/ui';
import { useProductForm, ProductFormFields } from '@/components/ProductForm';

type AttrRow = { id: number; name: string; slug: string; attr_val: string | null; val_id: number | null };
type ImgRow = { id?: number; url?: string; image_url?: string };

export default function EditProductPage() {
  const { id } = useParams<{ id: string }>();
  const pid = Number(id);
  const router = useRouter();
  const toast = useToast();
  const form = useProductForm(pid);
  const [attrs, setAttrs] = useState<AttrRow[]>([]);
  const [images, setImages] = useState<ImgRow[]>([]);
  const [meta, setMeta] = useState<{ updated_at?: string; created_at?: string } | null>(null);
  const [loadError, setLoadError] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!pid || Number.isNaN(pid)) { setLoadError('Невірний ідентифікатор товару'); return; }
    let cancelled = false;
    api.get<Record<string, unknown>>(`/products/${pid}`)
      .then((d) => {
        if (cancelled) return;
        const arr = (x: unknown) => (Array.isArray(x) ? (x as never[]) : []);
        setAttrs(arr(d.attributes ?? d.attrs) as AttrRow[]);
        setImages(arr(d.images ?? d.product_images) as ImgRow[]);
        const prod = ((d.product ?? d) as Record<string, unknown>);
        setMeta({ updated_at: prod.updated_at as string, created_at: prod.created_at as string });
      })
      .catch((e) => !cancelled && setLoadError(e.message));
    return () => { cancelled = true; };
  }, [pid]);

  const save = async () => {
    if (!form.values.name.trim()) { setError('Вкажіть назву товару'); return; }
    setSaving(true); setError('');
    try {
      await api.put(`/products/${pid}`, form.payload());
      toast.push('success', 'Зміни збережено');
      router.refresh();
    } catch (e: unknown) {
      setError((e as Error).message);
      toast.push('error', 'Не вдалося зберегти зміни');
    } finally { setSaving(false); }
  };

  if (loadError) return <ErrorState message={loadError} />;
  if (form.error) return <ErrorState message={form.error} />;

  return (
    <div>
      <PageHeader
        title={form.values.name ? `Товар: ${form.values.name}` : 'Редагування товару'}
        actions={
          <div className="flex gap-2 items-center">
            <Link href="/products"><Button variant="secondary">До списку</Button></Link>
            <Button onClick={save} loading={saving}>Зберегти</Button>
          </div>
        }
      />
      {meta?.updated_at && (
        <p className="text-xs text-gray-400 mb-3">Останнє оновлення: {formatDateTime(meta.updated_at)}</p>
      )}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-md p-3 mb-4" role="alert">{error}</div>
      )}
      <ProductFormFields {...form} />

      {/* Attributes (DB content — read-only in admin until a dedicated API exists) */}
      <div className="mt-6">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">Характеристики товару</h3>
        {attrs.length === 0 ? (
          <p className="text-sm text-gray-400">Характеристики не задано</p>
        ) : (
          <Table head={<tr><Th>Атрибут</Th><Th>Значення</Th></tr>}>
            {attrs.map((a) => (
              <tr key={a.id}>
                <Td className="font-medium">{a.name}</Td>
                <Td>{a.attr_val || '—'}</Td>
              </tr>
            ))}
          </Table>
        )}
      </div>

      {/* Images (existing backend storage — read-only list here) */}
      <div className="mt-6">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">Зображення</h3>
        {images.length === 0 ? (
          <p className="text-sm text-gray-400">Зображень немає</p>
        ) : (
          <div className="flex gap-2 flex-wrap">
            {images.map((img, i) => {
              const url = img.url || img.image_url || '';
              return (
                // eslint-disable-next-line @next/next/no-img-element
                <img key={img.id ?? i} src={url} alt="" loading="lazy"
                  className="w-20 h-20 object-cover rounded border border-gray-200 bg-gray-50" />
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
