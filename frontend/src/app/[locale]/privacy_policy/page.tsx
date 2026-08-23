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
    title: 'Політика конфіденційності',
    description:
      'Політика конфіденційності інтернет-магазину Gadgeto: які персональні дані збираються на сайті, з якою метою, як вони захищаються, використання cookies та права користувача.',
    alternates: {
      canonical: '/privacy_policy',
      languages: {uk: '/privacy_policy', 'x-default': '/privacy_policy'},
    },
  };
}

export default async function PrivacyPolicyPage({
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
        <h1>Політика конфіденційності</h1>

        <section>
          <h2>1. Загальні положення</h2>
          <p>
            Адміністрація сайту з повагою ставиться до прав відвідувачів сайту
            та визнає важливість захисту їхніх персональних даних. Ця Політика
            конфіденційності пояснює, які персональні дані ми збираємо, з якою
            метою та як вони використовуються.
          </p>
        </section>

        <section>
          <h2>2. Які персональні дані ми збираємо</h2>
          <p>Під час використання сайту ми можемо збирати такі дані:</p>
          <ul>
            <li>ім’я та прізвище;</li>
            <li>адреса електронної пошти;</li>
            <li>номер телефону;</li>
            <li>адреса доставки;</li>
            <li>дані облікового запису користувача;</li>
            <li>технічна інформація (IP-адреса, cookies, тип браузера).</li>
          </ul>
        </section>

        <section>
          <h2>3. Мета збору персональних даних</h2>
          <p>Ваші персональні дані використовуються для:</p>
          <ul>
            <li>реєстрації та обслуговування облікового запису;</li>
            <li>обробки замовлень та надання послуг;</li>
            <li>зв’язку з користувачем;</li>
            <li>покращення роботи сайту та сервісів;</li>
            <li>виконання вимог законодавства.</li>
          </ul>
        </section>

        <section>
          <h2>4. Захист персональних даних</h2>
          <p>
            Ми вживаємо необхідних організаційних та технічних заходів для
            захисту персональних даних користувачів від несанкціонованого
            доступу, зміни, розголошення або знищення.
          </p>
        </section>

        <section>
          <h2>5. Передача даних третім особам</h2>
          <p>
            Персональні дані не передаються третім особам, за винятком
            випадків, передбачених законодавством України або необхідних для
            виконання замовлення (служби доставки, платіжні системи).
          </p>
        </section>

        <section>
          <h2>6. Cookies</h2>
          <p>
            Сайт використовує файли cookies для коректної роботи, аналітики та
            покращення користувацького досвіду. Ви можете змінити налаштування
            cookies у своєму браузері.
          </p>
        </section>

        <section>
          <h2>7. Права користувача</h2>
          <p>Користувач має право:</p>
          <ul>
            <li>отримати інформацію про свої персональні дані;</li>
            <li>вимагати зміну або видалення персональних даних;</li>
            <li>відкликати згоду на обробку персональних даних.</li>
          </ul>
        </section>

        <section>
          <h2>8. Зміни до політики конфіденційності</h2>
          <p>
            Адміністрація сайту має право вносити зміни до цієї Політики без
            попереднього повідомлення. Актуальна версія завжди доступна на цій
            сторінці.
          </p>
        </section>
      </article>
    </div>
  );
}