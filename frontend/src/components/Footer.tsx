import { useTranslations } from 'next-intl';
import { Link } from '@/i18n/navigation';

export default function Footer() {
  const t = useTranslations('footer');

  return (
    <footer className="bg-gray-800 text-gray-300 py-8 mt-auto">
      <div className="max-w-7xl mx-auto px-4 grid grid-cols-1 md:grid-cols-3 gap-8">
        <div>
          <h3 className="text-white font-bold mb-3">Gadgeto</h3>
          <p className="text-sm">{t('tagline')}</p>
        </div>
        <div>
          <h3 className="text-white font-bold mb-3">{t('information')}</h3>
          <ul className="text-sm space-y-1">
            <li><Link href="/catalog" className="hover:text-white">{t('catalog')}</Link></li>
            <li><Link href="/search" className="hover:text-white">{t('search')}</Link></li>
            <li><Link href="/cart" className="hover:text-white">{t('cart')}</Link></li>
          </ul>
        </div>
        <div>
          <h3 className="text-white font-bold mb-3">{t('contact')}</h3>
          <p className="text-sm">{t('address')}</p>
          <p className="text-sm">{t('delivery')}</p>
        </div>
      </div>
      <div className="border-t border-gray-700 mt-6 pt-4 text-center text-sm">
        {t('copyright', { year: new Date().getFullYear() })}
      </div>
    </footer>
  );
}
