import { describe, expect, it } from 'vitest'
import { formatSize, isWebAddress } from '../attachments'

describe('formatSize', () => {
  it('counts in the unit that fits, with a decimal for small numbers', () => {
    expect(formatSize(0, 'en')).toBe('0 byte')
    expect(formatSize(820, 'en')).toBe('820 byte')
    expect(formatSize(1536, 'en')).toBe('1.5 kB')
    expect(formatSize(20 * 1024, 'en')).toBe('20 kB')
    expect(formatSize(3.25 * 1024 * 1024, 'en')).toBe('3.3 MB')
    expect(formatSize(5 * 1024 ** 4, 'en')).toBe('5,120 GB')
  })

  it('writes numbers as the reader does', () => {
    expect(formatSize(1536, 'de')).toBe('1,5 kB')
  })
})

describe('isWebAddress', () => {
  it.each(['https://example.org', 'http://example.org/a?b=c', '  https://example.org/x  '])('takes %s', (text) => {
    expect(isWebAddress(text)).toBe(true)
  })

  it.each(['example.org', 'javascript:alert(1)', 'ftp://example.org', 'mailto:a@b.c', 'https://', ''])(
    'refuses %s',
    (text) => {
      expect(isWebAddress(text)).toBe(false)
    },
  )
})
