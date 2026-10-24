import { afterEach, describe, expect, it } from 'vitest'
import { i18n, setLocale } from '..'

describe('setLocale', () => {
  afterEach(() => setLocale('en'))

  it('switches the language, tells the page and remembers it', () => {
    setLocale('de')
    expect(i18n.global.locale.value).toBe('de')
    expect(document.documentElement.lang).toBe('de')
    expect(localStorage.getItem('locale')).toBe('de')
  })
})
