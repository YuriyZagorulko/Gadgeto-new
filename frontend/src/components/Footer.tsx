import { useTranslations } from 'next-intl';
import { Link } from '@/i18n/navigation';

const buyersLinks = [
  { href: '/dostavka-i-oplata', label: 'Доставка та оплата' },
  { href: '/return-instruction', label: 'Умови повернення товару' },
  { href: '/dogovir-oferty', label: 'Договір публічної оферти' },
];

const infoLinks = [
  { href: '/about-us', label: 'Про нас' },
  { href: '/privacy_policy', label: 'Політика конфіденційності' },
  { href: '/guarantee', label: 'Гарантія' },
  { href: '/questions-faq', label: 'Питання FAQ' },
];

export default function Footer() {
  const t = useTranslations('footer');

  const columns = [
    { title: t('buyers'), links: buyersLinks },
    { title: t('information'), links: infoLinks },
    {
      title: t('contacts'),
      links: [{ href: '/contacts', label: t('contacts') }],
    },
  ];

  return (
    <footer className="bg-gray-800 text-gray-300 mt-auto">
      <div className="max-w-7xl mx-auto px-4 py-12">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-10">
          {columns.map((column) => (
            <div key={column.title}>
              <h3 className="text-white font-semibold mb-4">{column.title}</h3>
              <ul className="text-sm space-y-2.5">
                {column.links.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className="hover:text-white transition"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </footer>
  );
}
