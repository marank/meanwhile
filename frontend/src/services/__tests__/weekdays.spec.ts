import { describe, expect, it } from 'vitest'
import { weekdaysFrom } from '../weekdays'

describe('weekdaysFrom', () => {
  it('starts the week on the given day', () => {
    expect(weekdaysFrom(1).map((day) => day.code)).toEqual(['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU'])
    expect(weekdaysFrom(0).map((day) => day.value)).toEqual([0, 1, 2, 3, 4, 5, 6])
  })
})
