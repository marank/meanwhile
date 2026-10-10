import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  calendarColorPalettes,
  colorRoles,
  matchingPalette,
  newCalendarPalette,
  overviewPalette,
  paletteColors,
  themeColors,
  type CalendarColorPalette,
} from '../calendarColors'

describe('calendar palettes', () => {
  it('define every role as a hex color in both themes', () => {
    for (const palette of calendarColorPalettes) {
      for (const theme of [palette.light, palette.dark]) {
        for (const role of colorRoles) expect(theme[role], `${palette.id}.${role}`).toMatch(/^#[0-9a-f]{6}$/)
      }
    }
  })

  it('have unique ids', () => {
    const ids = calendarColorPalettes.map((palette) => palette.id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('round-trip through the calendar fields', () => {
    const fields = paletteColors(newCalendarPalette)
    expect(themeColors(fields, false)).toEqual(newCalendarPalette.light)
    expect(themeColors(fields, true)).toEqual(newCalendarPalette.dark)
  })
})

describe('matchingPalette', () => {
  it('recognizes a preset regardless of letter case', () => {
    const fields = paletteColors(newCalendarPalette)
    expect(matchingPalette({ ...fields, event_color: fields.event_color.toUpperCase() })).toBe(newCalendarPalette)
  })

  it('treats any changed color as custom', () => {
    expect(matchingPalette({ ...paletteColors(newCalendarPalette), dark_border_color: '#000000' })).toBeNull()
  })
})

describe('presets the server knows', () => {
  // The backend creates new calendars and overviews with these presets, so both sides must agree.
  const backend = readFileSync(join(__dirname, '../../../../backend/core/models/calendar_colors.py'), 'utf8')

  function serverColors(name: string): Record<string, string> {
    const block = backend.match(new RegExp(`${name} = \\{([^}]*)\\}`))![1]!
    return Object.fromEntries([...block.matchAll(/"(\w+)": "(#\w+)"/g)].map((match) => [match[1], match[2]]))
  }

  it.each([
    ['DEFAULT_COLORS', newCalendarPalette],
    ['APP_COLORS', overviewPalette],
  ] as [string, CalendarColorPalette][])('%s matches its preset', (name, palette) => {
    expect(serverColors(name)).toEqual(paletteColors(palette))
  })
})
