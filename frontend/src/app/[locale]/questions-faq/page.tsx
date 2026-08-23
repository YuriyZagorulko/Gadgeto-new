import type {Metadata} from 'next';
import {hasLocale} from 'next-intl';
import {notFound} from 'next/navigation';
import {setRequestLocale} from 'next-intl/server';
import {routing} from '@/i18n/routing';

export async function generateMetadata({
  params,
}: {
  params: Promise<{locale: string}>;
}): Promise<Metadata> {
  const {locale} = await params;
  if (!hasLocale(routing.locales, locale)) return {};

  return {
    title: 'Питання FAQ',
    description:
      'Поширені питання та відповіді про інтернет-магазин Gadgeto: як оформити замовлення, способи оплати, терміни доставки, відстеження замовлення, повернення товару та гарантія.',
    alternates: {
      canonical: '/questions-faq',
      languages: {uk: '/questions-faq', 'x-default': '/questions-faq'},
    },
  };
}

const faqItems = [
  {
    question: 'Як оформити замовлення?',
    answer:
      'Щоб оформити замовлення, оберіть товар або послугу, додайте до кошика та заповніть форму оформлення. Після підтвердження з вами зв’яжеться менеджер (за потреби).',
  },
  {
    question: 'Як з нами можна зв’язатися?',
    answer:
      'Ви можете скористатися контактами, зазначеними на сторінці «Контакти».',
  },
  {
    question: 'Чи потрібно реєструватися на сайті?',
    answer:
      'Ні, ви можете оформити замовлення без реєстрації (якщо це дозволено налаштуваннями сайту).',
  },
  {
    question: 'Які способи оплати доступні?',
    answer:
      'Ми приймаємо: Онлайн-оплату карткою, Безготівковий переказ, Післяплату (за наявності).',
  },
  {
    question: 'Чи безпечна онлайн-оплата?',
    answer:
      'Так, усі платежі обробляються через захищені платіжні системи. Ваші дані не зберігаються на сайті.',
  },
  {
    question: 'Які терміни доставки?',
    answer:
      'Термін доставки зазвичай становить 1–3 робочі дні (залежить від регіону).',
  },
  {
    question: 'Чи можна відстежити замовлення?',
    answer:
      'Так, після відправлення ви отримаєте номер накладної для відстеження.',
  },
  {
    question: 'Чи можна повернути товар?',
    answer:
      'Так, відповідно до законодавства України ви можете повернути товар протягом 14 днів (за умови збереження товарного вигляду).',
  },
  {
    question: 'Що робити, якщо товар прийшов пошкоджений?',
    answer:
      'Зв’яжіться з нами протягом 24 годин після отримання та надішліть фото пошкодження.',
  },
];

const faqStructuredData = {
  '@context': 'https://schema.org',
  '@type': 'FAQPage',
  mainEntity: faqItems.map((item) => ({
    '@type': 'Question',
    name: item.question,
    acceptedAnswer: {
      '@type': 'Answer',
      text: item.answer,
    },
  })),
};

export default async function FaqPage({
  params,
}: {
  params: Promise<{locale: string}>;
}) {
  const {locale} = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);

  const sections = [
    {
      title: '1. Загальні питання',
      items: faqItems.slice(0, 3),
    },
    {
      title: '2. Оплата',
      items: faqItems.slice(3, 5),
    },
    {
      title: '3. Доставка',
      items: faqItems.slice(5, 7),
    },
    {
      title: '4. Повернення та гарантія',
      items: faqItems.slice(7, 9),
    },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 sm:py-12">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{__html: JSON.stringify(faqStructuredData)}}
      />
      <article className="max-w-3xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-8">Питання FAQ</h1>

        {sections.map((section) => (
          <section key={section.title} className="mb-10">
            <h2 className="text-xl font-bold text-gray-900 mb-4">
              {section.title}
            </h2>
            <div className="space-y-3">
              {section.items.map((item) => (
                <details key={item.question} className="faq-item">
                  <summary>{item.question}</summary>
                  <div className="faq-answer">{item.answer}</div>
                </details>
              ))}
            </div>
          </section>
        ))}
      </article>
    </div>
  );
}