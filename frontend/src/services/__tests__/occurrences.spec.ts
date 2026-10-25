import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { i18n } from '@/i18n'
import { dialog, submitDialog } from '../dialog'
import { at, occurrence } from '@/components/calendar/__tests__/calendarFixtures'
import { chooseScope, seriesOccurrence } from '../occurrences'

beforeEach(() => {
  i18n.global.locale.value = 'en'
})

afterEach(() => {
  if (dialog.open) submitDialog(null)
})

describe('chooseScope', () => {
  it('asks which events of a series a change applies to', async () => {
    const answer = chooseScope('edit')
    expect(dialog.title).toBe('Change recurring event')
    expect(dialog.message).toBe('Which events of the series should the change apply to?')
    expect(dialog.choices).toEqual([
      { value: 'this', label: 'This event only' },
      { value: 'following', label: 'This and all following events' },
      { value: 'all', label: 'All events of the series' },
    ])
    submitDialog('following')
    await expect(answer).resolves.toBe('following')
  })

  it('offers only whole parts of the series when a single event is not allowed', async () => {
    const answer = chooseScope('delete', false)
    expect(dialog.title).toBe('Delete recurring event')
    expect(dialog.choices.map((choice) => choice.value)).toEqual(['following', 'all'])
    submitDialog(null)
    await expect(answer).resolves.toBeNull()
  })
})

describe('seriesOccurrence', () => {
  it('refers to an occurrence of a series, not to a changed one or a single event', () => {
    const series = occurrence({ event_id: 's1', series_id: 's1', recurrence_id: at(2026, 10, 14, 10) })
    expect(seriesOccurrence(series)).toEqual({
      recurrenceId: series.recurrence_id,
      start: series.start,
      end: series.end,
    })
    expect(seriesOccurrence({ ...series, event_id: 'x1' })).toBeNull()
    expect(seriesOccurrence(occurrence())).toBeNull()
  })
})
