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
    title: 'Умови повернення товару',
    description:
      'Умови повернення та обміну товару в інтернет-магазині Gadgeto: повернення товару належної та неналежної якості протягом 14 днів, товари, що не підлягають поверненню, витрати на доставку та порядок оформлення повернення.',
    alternates: {
      canonical: '/return-instruction',
      languages: {uk: '/return-instruction', 'x-default': '/return-instruction'},
    },
  };
}

export default async function ReturnInstructionPage({
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
        <h1>Умови повернення товару</h1>
        <p>
          Відповідно до Закону України «Про захист прав споживачів», покупець має
          право на повернення або обмін товару належної якості протягом 14 днів з
          моменту отримання, якщо товар не був у використанні та збережено його
          товарний вигляд, упаковку, пломби та розрахункові документи.
        </p>

        <section>
          <h2>Товари, що не підлягають поверненню</h2>
          <p>
            Згідно з Постановою Кабінету Міністрів України №172, деякі категорії
            товарів не підлягають поверненню та обміну, зокрема:
          </p>
          <ul>
            <li>кабельно-провідникова продукція, що відрізається під індивідуальне замовлення</li>
            <li>товари, виготовлені або привезені під індивідуальне замовлення покупця</li>
            <li>товари зі слідами встановлення або використання</li>
            <li>електротехнічні товари після підключення до мережі</li>
            <li>товари з пошкодженою упаковкою або без повної комплектації</li>
          </ul>
          <p>
            <strong>Такі товари поверненню та обміну не підлягають.</strong>
          </p>
        </section>

        <section>
          <h2>Повернення товару належної якості</h2>
          <p>Повернення товару можливе за умов:</p>
          <ul>
            <li>товар не був у використанні</li>
            <li>збережено товарний вигляд</li>
            <li>збережена упаковка та комплектація</li>
            <li>є чек або інший документ про оплату</li>
          </ul>
        </section>

        <section>
          <h2>Повернення товару неналежної якості</h2>
          <p>У разі отримання товару з дефектом покупець має право:</p>
          <ul>
            <li>на обмін товару</li>
            <li>на повернення коштів</li>
            <li>на гарантійний ремонт (якщо передбачено)</li>
          </ul>
        </section>

        <section>
          <h2>Витрати на доставку</h2>
          <p>
            Витрати на пересилку товару при поверненні <strong>оплачує покупець</strong>,
            за винятком випадків отримання товару неналежної якості або помилки з
            боку продавця.
          </p>
        </section>

        <section>
          <h2>Як оформити повернення</h2>
          <p>Для оформлення повернення необхідно:</p>
          <ul>
            <li>Написати на email або в месенджер магазину</li>
            <li>Вказати номер замовлення</li>
            <li>Причину повернення</li>
            <li>Відправити товар після погодження</li>
          </ul>
          <p>
            Після отримання та перевірки товару кошти повертаються протягом 3-7
            робочих днів.
          </p>
        </section>
      </article>
    </div>
  );
}