import { describe, expect, it } from 'vitest'
import { nonEmpty } from '../text'

describe('nonEmpty', () => {
  it('keeps text and treats empty, null and undefined as missing', () => {
    expect(nonEmpty('Ada')).toBe('Ada')
    expect(nonEmpty(' ')).toBe(' ')
    expect(nonEmpty('')).toBeUndefined()
    expect(nonEmpty(null)).toBeUndefined()
    expect(nonEmpty(undefined)).toBeUndefined()
  })
})
