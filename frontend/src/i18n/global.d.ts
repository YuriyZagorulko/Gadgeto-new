import type {routing} from './routing';

type Messages = typeof import('../../messages/uk.json');

declare module 'next-intl' {
  interface AppConfig {
    Locale: (typeof routing.locales)[number];
    Messages: Messages;
  }
}
