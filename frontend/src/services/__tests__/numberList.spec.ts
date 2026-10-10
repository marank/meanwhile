import { describe, expect, it } from 'vitest'
import { formatNumberList, LAST, parseNumberList, sortWithLastAtEnd } from '../numberList'

describe('parseNumberList', () => {
  it('reads numbers separated by commas or spaces, sorted and without duplicates', () => {
    expect(parseNumberList(' 15,1  3, 1', 1, 31, false)).toEqual([1, 3, 15])
  })

  it('reads "+" as the last one, sorted to the end', () => {
    expect(parseNumberList('+, 1, 15', 1, 31, true)).toEqual([1, 15, LAST])
  })

  it.each(['', ',', '0', '32', '1.5', 'x', '-1', '+'])('rejects %j', (text) => {
    expect(parseNumberList(text, 1, 31, false)).toBeNull()
  })
})

describe('formatNumberList', () => {
  it('writes the last one as "+"', () => {
    expect(formatNumberList([LAST, 15, 1])).toBe('1, 15, +')
  })
})

describe('sortWithLastAtEnd', () => {
  it('sorts ascending with the last one at the end', () => {
    expect(sortWithLastAtEnd([LAST, 3, 1, 3])).toEqual([1, 3, LAST])
  })
})
