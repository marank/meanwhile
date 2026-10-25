import { computed } from 'vue'
import type { Occurrence } from '@/api'
import { overviewPalette, paletteColors, themeColors } from '@/services/calendarColors'
import { contrastColor } from '@/services/color'
import { useCalendarStore } from '@/stores/calendars'
import { useOverviewStore } from '@/stores/overview'
import { useSettingsStore } from '@/stores/settings'
import { useThemeStore } from '@/stores/theme'

/** Height of an hour's half in the week view, in pixels. */
export const SLOT_HEIGHT = 48

/** How the calendar shown looks: its layout settings, its colors and those of its events. */
export function useCalendarDisplay() {
  const calendarStore = useCalendarStore()
  const overviewStore = useOverviewStore()
  const settingsStore = useSettingsStore()
  const themeStore = useThemeStore()

  // A single calendar brings its own layout and colors; the overview uses the user's overview settings,
  // and until they're loaded the app defaults with the app color preset.
  const displaySettings = computed(() => {
    if (calendarStore.selectedCalendar) return calendarStore.selectedCalendar
    if (overviewStore.settings) return overviewStore.settings
    const appSettings = settingsStore.settings
    return {
      first_weekday: appSettings?.default_first_weekday ?? 0,
      show_weekends: appSettings?.default_show_weekends ?? true,
      weekend_days: appSettings?.default_weekend_days ?? [0, 6],
      show_week_numbers: appSettings?.default_show_week_numbers ?? false,
      ...paletteColors(overviewPalette),
    }
  })

  const hiddenDays = computed(() => (displaySettings.value.show_weekends ? [] : displaySettings.value.weekend_days))

  // Events take their calendar's current event color, so palette changes show up without reloading them.
  // The overview ("All calendars", folders) can instead show all events in its own event color.
  function eventColor(occurrence: Occurrence): string {
    const overview = overviewStore.settings
    const useOverviewColor = !calendarStore.selectedCalendar && overview && !overview.use_calendar_colors
    const source =
      (useOverviewColor ? overview : calendarStore.calendarsById.get(occurrence.calendar_id)) ?? displaySettings.value
    return themeStore.isDark ? source.dark_event_color : source.event_color
  }

  // The list names each event's calendar when it shows several.
  const calendarNameOf = computed(() =>
    !calendarStore.selectedCalendar && calendarStore.selectedCalendarIds.length > 1
      ? (occurrence: Occurrence) => calendarStore.calendarsById.get(occurrence.calendar_id)?.name ?? ''
      : null,
  )

  // Only text colors are computed; everything else is stored per calendar.
  const colorStyle = computed(() => {
    const colors = themeColors(displaySettings.value, themeStore.isDark)
    return {
      '--calendar-default-color': colors.base,
      '--calendar-default-text-color': contrastColor(colors.base),
      '--calendar-header-color': colors.event,
      '--calendar-header-text-color': contrastColor(colors.event),
      '--calendar-border-color': colors.border,
      '--calendar-slot-height': `${SLOT_HEIGHT}px`,
      '--calendar-outer-border-color': colors.outerBorder,
      '--calendar-accent-color': colors.event,
      '--calendar-accent-text-color': contrastColor(colors.event),
      '--fc-classic-border': colors.border,
      '--fc-classic-strong-border': colors.outerBorder,
      '--fc-classic-foreground': contrastColor(colors.base),
      '--calendar-today-color': colors.today,
      '--calendar-today-text-color': contrastColor(colors.today),
      '--calendar-weekend-color': colors.weekend,
      '--calendar-weekend-text-color': contrastColor(colors.weekend),
    }
  })

  return { displaySettings, hiddenDays, eventColor, calendarNameOf, colorStyle }
}
