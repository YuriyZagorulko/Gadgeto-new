import { useTranslations } from 'next-intl';
import { Link } from '@/i18n/navigation';

export default function NotFound() {
  // Sync access: the request locale is set by [locale]/layout.tsx.
  const t = useTranslations('errors');

  return (
    <div className="max-w-lg mx-auto px-4 py-24 text-center">
      <div className="text-6xl mb-4">🔍</div>
      <h1 className="text-2xl font-bold mb-2">{t('notFoundTitle')}</h1>
      <p className="text-gray-500 mb-8">{t('notFoundDescription')}</p>
      <Link href="/" className="btn-primary inline-block">{t('backToHome')}</Link>
    </div>
  );
}
