import { afterEach, describe, expect, it, vi } from 'vitest'
import { i18n, setLocale } from '..'

describe('setLocale', () => {
  afterEach(() => setLocale('en'))

  it('switches the language, tells the page and remembers it', () => {
    setLocale('de')
    expect(i18n.global.locale.value).toBe('de')
    expect(document.documentElement.lang).toBe('de')
    expect(localStorage.getItem('locale')).toBe('de')
  })

  it('tells the page the language of the German that says du', () => {
    setLocale('de-informal')
    expect(i18n.global.t('rsvp.yourAnswer')).toBe('Deine Antwort')
    expect(i18n.global.t('rsvp.guest')).toBe('Gast')
    expect(document.documentElement.lang).toBe('de')
    expect(localStorage.getItem('locale')).toBe('de-informal')
  })

  it('starts in the language remembered', async () => {
    localStorage.setItem('locale', 'de-informal')
    vi.resetModules()
    const fresh = await import('..')
    expect(fresh.i18n.global.locale.value).toBe('de-informal')
  })
})
