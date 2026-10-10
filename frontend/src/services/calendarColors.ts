import type { Calendar } from '@/api'
import { calendarColorPalettes } from './calendarPalettes'

export { calendarColorPalettes }

/** The colors a calendar uses in one theme. Text colors aren't stored; they follow from these for contrast. */
export interface CalendarThemeColors {
  /** Background of regular days */
  base: string
  weekend: string
  today: string
  /** Events; also the weekday header and the active toolbar button */
  event: string
  /** Grid lines between days and time slots */
  border: string
  /** Frame around the calendar and stronger dividers */
  outerBorder: string
}

/** A preset of calendar colors; its name is the i18n key `palette.<id>`. */
export interface CalendarColorPalette {
  id: string
  light: CalendarThemeColors
  dark: CalendarThemeColors
}

export const colorRoles = ['base', 'weekend', 'today', 'event', 'border', 'outerBorder'] as const

export type CalendarColorFields = Pick<
  Calendar,
  | 'base_color'
  | 'weekend_color'
  | 'today_color'
  | 'event_color'
  | 'border_color'
  | 'outer_border_color'
  | 'dark_base_color'
  | 'dark_weekend_color'
  | 'dark_today_color'
  | 'dark_event_color'
  | 'dark_border_color'
  | 'dark_outer_border_color'
>

type ColorField = keyof CalendarColorFields

/** The calendar fields behind each color role, per theme. */
export const colorFields: Record<(typeof colorRoles)[number], { light: ColorField; dark: ColorField }> = {
  base: { light: 'base_color', dark: 'dark_base_color' },
  weekend: { light: 'weekend_color', dark: 'dark_weekend_color' },
  today: { light: 'today_color', dark: 'dark_today_color' },
  event: { light: 'event_color', dark: 'dark_event_color' },
  border: { light: 'border_color', dark: 'dark_border_color' },
  outerBorder: { light: 'outer_border_color', dark: 'dark_outer_border_color' },
}

/** The calendar fields a palette sets. */
export function paletteColors(palette: CalendarColorPalette): CalendarColorFields {
  const fields = {} as CalendarColorFields
  for (const role of colorRoles) {
    fields[colorFields[role].light] = palette.light[role]
    fields[colorFields[role].dark] = palette.dark[role]
  }
  return fields
}

/** The colors of one theme, read from a calendar's fields. */
export function themeColors(colors: CalendarColorFields, dark: boolean): CalendarThemeColors {
  const result = {} as CalendarThemeColors
  for (const role of colorRoles) result[role] = colors[colorFields[role][dark ? 'dark' : 'light']]
  return result
}

/** The preset whose colors the calendar uses unchanged, if any. */
export function matchingPalette(colors: CalendarColorFields): CalendarColorPalette | null {
  return (
    calendarColorPalettes.find((palette) =>
      Object.entries(paletteColors(palette)).every(
        ([field, color]) => colors[field as ColorField].toLowerCase() === color,
      ),
    ) ?? null
  )
}

/** The colors new calendars start with (set by the server). */
export const newCalendarPalette = calendarColorPalettes.find((palette) => palette.id === 'blue')!

/** Matches the app theme; the overview ("All calendars", folders) starts with it. */
export const overviewPalette = calendarColorPalettes.find((palette) => palette.id === 'app')!

/** Copies the color fields out of anything that has them, e.g. a calendar. */
export function pickColorFields(source: CalendarColorFields): CalendarColorFields {
  const fields = {} as CalendarColorFields
  for (const { light, dark } of Object.values(colorFields)) {
    fields[light] = source[light]
    fields[dark] = source[dark]
  }
  return fields
}
