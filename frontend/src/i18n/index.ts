import { createI18n } from 'vue-i18n'
import { readStorage, writeStorage } from '@/services/storage'
import de from './locales/de'
import deInformal from './locales/de-informal'
import en, { type MessageSchema } from './locales/en'

declare module 'vue-i18n' {
  // Gives $t/t key completion and checking against the English messages.
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type -- augmenting vue-i18n needs an interface
  export interface DefineLocaleMessage extends MessageSchema {}
}

// "de-informal" is the German that says "du" (BCP 47 allows the variant; Intl treats it as "de").
const locales = ['en', 'de', 'de-informal'] as const
export type Locale = (typeof locales)[number]

export function isLocale(value: string | null | undefined): value is Locale {
  return locales.some((locale) => locale === value)
}

/** The language of `locale` without its variant ("de-informal" → "de"), for the page and libraries. */
export function baseLanguage(locale: string): string {
  return locale.split('-')[0] ?? locale
}

const LOCALE_KEY = 'locale'

function initialLocale(): Locale {
  const stored = readStorage(LOCALE_KEY)
  if (isLocale(stored)) return stored
  return navigator.language.startsWith('de') ? 'de' : 'en'
}

export const i18n = createI18n<[MessageSchema], Locale, false>({
  legacy: false,
  locale: initialLocale(),
  fallbackLocale: 'en',
  messages: { en, de, 'de-informal': deInformal },
})

document.documentElement.lang = baseLanguage(i18n.global.locale.value)

export function setLocale(locale: Locale) {
  i18n.global.locale.value = locale
  document.documentElement.lang = baseLanguage(locale)
  writeStorage(LOCALE_KEY, locale)
}
