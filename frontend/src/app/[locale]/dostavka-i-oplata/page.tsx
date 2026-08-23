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
    title: 'Доставка і оплата',
    description:
      'Умови доставки та оплати в інтернет-магазині Gadgeto: терміни доставки по Україні та за кордоном, способи доставки (Нова Пошта, Укрпошта), способи оплати (карткою, LiqPay, накладений платіж) та контактна інформація.',
    alternates: {
      canonical: '/dostavka-i-oplata',
      languages: {uk: '/dostavka-i-oplata', 'x-default': '/dostavka-i-oplata'},
    },
  };
}

export default async function DeliveryAndPaymentPage({
  params,
}: {
  params: Promise<{locale: string}>;
}) {
  const {locale} = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 sm:py-12">
      <article className="prose prose-neutral max-w-3xl mx-auto">
        <h1>Доставка і оплата</h1>

        <section>
          <h2>1. Загальні положення</h2>
          <p>
            1.1. Відвідуючи цю сторінку, користувач підтверджує ознайомлення з
            умовами доставки та оплати.
          </p>
          <p>1.2. Власником та розпорядником інформації про замовлення є:</p>
          <ul>
            <li>ФОП Загорулько Юрій Олегович</li>
            <li>ІПН: 3476016835</li>
            <li>Адреса: Україна, м. Дніпро, вул. Лубедина, буд. 63</li>
            <li>Email: gadgeto602@gmail.com</li>
            <li>Телефон: +380935091447</li>
          </ul>
        </section>

        <section>
          <h2>2. Доставка</h2>
          <p>2.1. Терміни доставки:</p>
          <ul>
            <li>По Україні: 1–5 робочих днів</li>
            <li>Міжнародна доставка: 7–21 робочих днів (залежить від країни)</li>
          </ul>
          <p>2.2. Способи доставки:</p>
          <ul>
            <li>Кур’єрські служби: Нова Пошта, Укрпошта</li>
            <li>Самовивіз: [адреса точки самовивозу]</li>
            <li>Доставка службою перевізника за домовленістю</li>
          </ul>
          <p>2.3. Вартість доставки:</p>
          <ul>
            <li>Від 50 грн по Україні (можливо безкоштовно при замовленні від певної суми)</li>
            <li>Міжнародна доставка — розраховується індивідуально</li>
          </ul>
          <p>
            2.4. Ми залишаємо за собою право змінювати терміни та способи доставки
            у разі непередбачуваних обставин.
          </p>
        </section>

        <section>
          <h2>3. Оплата</h2>
          <p>3.1. Способи оплати:</p>
          <ul>
            <li>Онлайн карткою (Visa, Mastercard, Приват24, LiqPay)</li>
            <li>Готівкою при отриманні (накладений платіж)</li>
            <li>Банківський переказ (для юридичних осіб)</li>
          </ul>
          <p>
            3.2. Безпека платежів: Всі платежі проходять через захищені платіжні
            шлюзи з шифруванням SSL.
          </p>
          <p>
            3.3. Підтвердження оплати надсилається на email або телефон користувача
            після успішної транзакції.
          </p>
        </section>

        <section>
          <h2>4. Повернення та обмін</h2>
          <p>4.1. Приймаємо повернення протягом 14 днів після отримання товару.</p>
          <p>
            4.2. Для обміну чи повернення потрібно заповнити форму на сайті або
            звернутися до служби підтримки.
          </p>
          <p>
            4.3. Повернення коштів здійснюється тим же способом, що і оплата
            замовлення, якщо інше не узгоджено.
          </p>
        </section>

        <section>
          <h2>5. Контактна інформація</h2>
          <ul>
            <li>ФОП Загорулько Юрій Олегович</li>
            <li>ІПН: 3476016835</li>
            <li>Адреса: Україна, м. Дніпро, вул. Лубедина, буд. 63</li>
            <li>Email: gadgeto602@gmail.com</li>
            <li>Телефон: +380935091447</li>
          </ul>
        </section>
      </article>
    </div>
  );
}