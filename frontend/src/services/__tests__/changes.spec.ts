import { describe, expect, it } from 'vitest'
import { changedValues } from '../changes'

describe('changedValues', () => {
  const saved = { first_weekday: 0, weekend_days: [0, 6], show_weekends: true, base_color: '#ffffff' }

  it('keeps only what differs from the saved values', () => {
    expect(changedValues({ first_weekday: 1, weekend_days: [0, 6], show_weekends: true }, saved)).toEqual({
      first_weekday: 1,
    })
  })

  it('compares lists by their content', () => {
    expect(changedValues({ weekend_days: [0, 6] }, saved)).toEqual({})
    expect(changedValues({ weekend_days: [5, 6] }, saved)).toEqual({ weekend_days: [5, 6] })
  })
})
