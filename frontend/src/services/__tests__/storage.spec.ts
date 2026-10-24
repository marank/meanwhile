import { afterEach, describe, expect, it, vi } from 'vitest'
import { readStorage, writeStorage } from '../storage'

afterEach(() => {
  vi.restoreAllMocks()
  localStorage.clear()
})

describe('storage', () => {
  it('reads back what was written', () => {
    writeStorage('key', 'value')
    expect(readStorage('key')).toBe('value')
  })

  it('reads nothing for a key never written', () => {
    expect(readStorage('missing')).toBeNull()
  })

  it('reads nothing when storage is blocked', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError')
    })
    expect(readStorage('key')).toBeNull()
  })

  it('carries on when storage refuses to write', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('full', 'QuotaExceededError')
    })
    expect(() => writeStorage('key', 'value')).not.toThrow()
  })
})
