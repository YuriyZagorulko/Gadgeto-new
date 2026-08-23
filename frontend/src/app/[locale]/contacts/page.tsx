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
    title: 'Контакти',
    description:
      'Контактна інформація інтернет-магазину Gadgeto: електронна пошта, номер телефону та юридична адреса для зв’язку з нами.',
    alternates: {
      canonical: '/contacts',
      languages: {uk: '/contacts', 'x-default': '/contacts'},
    },
  };
}

export default async function ContactsPage({
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
        <h1>Контакти</h1>
        <ul>
          <li>
            <a href="mailto:gadgeto602@gmail.com">gadgeto602@gmail.com</a>
          </li>
          <li>
            <a href="tel:+380935091447">+380935091447</a>
          </li>
          <li>Україна, м. Дніпро, вул. Лубедина, буд. 63</li>
        </ul>
      </article>
    </div>
  );
}