import { createI18n } from 'vue-i18n'
import { readStorage, writeStorage } from '@/services/storage'
import de from './locales/de'
import en, { type MessageSchema } from './locales/en'

declare module 'vue-i18n' {
  // Gives $t/t key completion and checking against the English messages.
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type
  export interface DefineLocaleMessage extends MessageSchema {}
}

export type Locale = 'en' | 'de'

const LOCALE_KEY = 'calendar-locale'

function initialLocale(): Locale {
  const stored = readStorage(LOCALE_KEY)
  if (stored === 'en' || stored === 'de') return stored
  return navigator.language.startsWith('de') ? 'de' : 'en'
}

export const i18n = createI18n<[MessageSchema], Locale, false>({
  legacy: false,
  locale: initialLocale(),
  fallbackLocale: 'en',
  messages: { en, de },
})

document.documentElement.lang = i18n.global.locale.value

export function setLocale(locale: Locale) {
  i18n.global.locale.value = locale
  document.documentElement.lang = locale
  writeStorage(LOCALE_KEY, locale)
}
