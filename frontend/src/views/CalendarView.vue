<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import FullCalendar from '@fullcalendar/vue3'
import dayGridPlugin from '@fullcalendar/vue3/daygrid'
import timeGridPlugin from '@fullcalendar/vue3/timegrid'
import interactionPlugin from '@fullcalendar/vue3/interaction'
import classicThemePlugin from '@fullcalendar/vue3/themes/classic'
import deLocale from '@fullcalendar/vue3/locales/de'
import type { DateClickInfo, DateSelectInfo, EventClickInfo, EventDisplayInfo, DatesSetInfo, EventDropInfo, EventResizeDoneInfo } from '@fullcalendar/vue3'
import '@fullcalendar/vue3/skeleton.css'
import '@fullcalendar/vue3/themes/classic/theme.css'
import '@fullcalendar/vue3/themes/classic/palette.css'
import EventModal from '@/components/EventModal.vue'
import { useAuthStore } from '@/stores/auth'
import { useCalendarStore } from '@/stores/calendars'
import { useEventStore } from '@/stores/events'
import { useSettingsStore } from '@/stores/settings'
import { useThemeStore } from '@/stores/theme'
import { alert } from '@/services/dialog'
import { hour12 } from '@/services/datetime'
import * as api from '@/api'
import type { Occurrence } from '@/api'

const auth = useAuthStore()
const calendarStore = useCalendarStore()
const eventStore = useEventStore()
const settingsStore = useSettingsStore()
const themeStore = useThemeStore()
const { locale, t } = useI18n()

const calendarRef = ref<InstanceType<typeof FullCalendar> | null>(null)

function eventLabel(occ: Occurrence): string {
  let title = occ.recurrence_count === null ? occ.title : `${occ.title} (${occ.recurrence_count})`
  if (occ.status === 'rejected' || occ.status === 'cancelled') {
    title = `${title} (${t('event.declined')})`
  } else if (occ.status === 'pending') {
    title = `${title} (${t('event.pending')})`
  }
  return occ.resource_name ? `${title} · ${occ.resource_name}` : title
}

function colorChannels(color: string): [number, number, number] {
  const value = color.replace('#', '')
  return [
    Number.parseInt(value.slice(0, 2), 16),
    Number.parseInt(value.slice(2, 4), 16),
    Number.parseInt(value.slice(4, 6), 16),
  ]
}

function contrastColor(color: string): string {
  const [red, green, blue] = colorChannels(color)
  return (red * 299 + green * 587 + blue * 114) / 1000 > 150 ? '#111827' : '#ffffff'
}

function toHsl(color: string): [number, number, number] {
  const [red, green, blue] = colorChannels(color).map((channel) => channel / 255) as [number, number, number]
  const max = Math.max(red, green, blue)
  const min = Math.min(red, green, blue)
  const lightness = (max + min) / 2
  if (max === min) return [0, 0, lightness]
  const delta = max - min
  const saturation = lightness > 0.5 ? delta / (2 - max - min) : delta / (max + min)
  const hue = max === red
    ? (green - blue) / delta + (green < blue ? 6 : 0)
    : max === green ? (blue - red) / delta + 2 : (red - green) / delta + 4
  return [hue * 60, saturation, lightness]
}

function fromHsl(hue: number, saturation: number, lightness: number): string {
  const amount = saturation * Math.min(lightness, 1 - lightness)
  const channel = (n: number) => {
    const k = (n + hue / 30) % 12
    const value = lightness - amount * Math.max(-1, Math.min(k - 3, 9 - k, 1))
    return Math.round(value * 255).toString(16).padStart(2, '0')
  }
  return `#${channel(0)}${channel(8)}${channel(4)}`
}

// Darkens a color while keeping its hue, adding saturation so pastel palette colors stay vivid.
// Saturation is capped so already saturated hues (indigo, lavender, purple) don't turn garish.
function shadeColor(color: string, lightnessFactor: number, saturationBoost = 0.15, maxSaturation = 0.65): string {
  const [hue, saturation, lightness] = toHsl(color)
  return fromHsl(hue, Math.min(maxSaturation, saturation + saturationBoost), lightness * lightnessFactor)
}

function relativeLuminance(color: string): number {
  const [red, green, blue] = colorChannels(color).map((channel) => {
    const value = channel / 255
    return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
  }) as [number, number, number]
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue
}

// Keeps darkening until white text reaches WCAG AA contrast (4.5:1); green and yellow hues need more.
function darkenForWhiteText(color: string): string {
  let result = color
  for (let step = 0; step < 20 && 1.05 / (relativeLuminance(result) + 0.05) < 4.5; step++) {
    const [hue, saturation, lightness] = toHsl(result)
    result = fromHsl(hue, saturation, lightness * 0.93)
  }
  return result
}

function mixColor(color: string, target: '#000000' | '#ffffff', amount: number): string {
  const source = colorChannels(color)
  const destination = colorChannels(target)
  return `#${source.map((channel, index) =>
    Math.round(channel + (destination[index]! - channel) * amount).toString(16).padStart(2, '0'),
  ).join('')}`
}

function renderEventContent(info: EventDisplayInfo) {
  const content = document.createElement('span')
  const duration = info.event.start && info.event.end
    ? info.event.end.getTime() - info.event.start.getTime()
    : 0
  const classes = [duration > 24 * 60 * 60 * 1000
    ? 'fc-event-label fc-event-label-multiday'
    : 'fc-event-label']
  const status = info.event.extendedProps.status as string | undefined
  if (status === 'rejected' || status === 'cancelled') {
    classes.push('fc-event-declined')
  }
  content.className = classes.join(' ')
  if (info.timeText) {
    const time = document.createElement('span')
    time.className = 'fc-event-time-label'
    time.textContent = info.timeText
    content.append(time)
  }
  const categoryColor = info.event.extendedProps.categoryColor as string | null
  if (categoryColor) {
    const marker = document.createElement('span')
    marker.className = 'fc-event-category-marker'
    marker.style.backgroundColor = categoryColor
    content.append(marker)
  }
  const title = document.createElement('span')
  title.textContent = info.event.title
  content.append(title)
  return { domNodes: [content] }
}

const fcEvents = computed(() =>
  eventStore.occurrences.map((occ) => {
    const color = themeStore.resolved === 'dark' ? occ.dark_color : occ.color
    return {
      id: `${occ.event_id}-${occ.start}`,
      title: eventLabel(occ),
      start: occ.start,
      end: occ.end,
      allDay: occ.all_day,
      startEditable: occ.can_edit && !occ.is_recurring,
      durationEditable: occ.can_edit && !occ.is_recurring,
      color,
      contrastColor: contrastColor(color),
      extendedProps: { eventId: occ.event_id, categoryColor: occ.category_color, status: occ.status },
    }
  }),
)

function syncEvents() {
  const api = calendarRef.value?.getApi()
  if (!api) return
  api.removeAllEventSources()
  if (fcEvents.value.length) api.addEventSource(fcEvents.value)
}

function handleDatesSet(info: DatesSetInfo) {
  eventStore.load(info.start, info.end)
}

function reloadVisibleRange(force = false) {
  const view = calendarRef.value?.getApi().view
  if (view) eventStore.load(view.activeStart, view.activeEnd, force)
}

const showModal = ref(false)
const modalEventId = ref<string | null>(null)
const modalDate = ref<Date>(new Date())
const modalEndDate = ref<Date | undefined>(undefined)
const modalAllDay = ref<boolean | undefined>(undefined)

function openCreateModal(start: Date, end?: Date, allDay?: boolean) {
  if (calendarStore.allSelected) return
  modalEventId.value = null
  modalDate.value = start
  modalEndDate.value = end
  modalAllDay.value = allDay
  showModal.value = true
}

function openEditModal(eventId: string) {
  modalEventId.value = eventId
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  modalEventId.value = null
  modalEndDate.value = undefined
  modalAllDay.value = undefined
}

function saved() {
  closeModal()
  reloadVisibleRange(true)
}

const activeCalendarId = computed(() => {
  if (calendarStore.selectedCalendar) return calendarStore.selectedCalendar.id
  const first = calendarStore.items[0]
  return first?.calendar.id || ''
})

onMounted(() => {
  calendarStore.load()
  syncEvents()
})

watch(fcEvents, syncEvents, { flush: 'post' })

watch(
  () => calendarStore.allSelected,
  (allSelected) => {
    if (allSelected && showModal.value && !modalEventId.value) closeModal()
  },
)

watch(
  () => eventStore.selectedCalendarIds().join(','),
  () => reloadVisibleRange(),
  { flush: 'post' },
)

const displaySettings = computed(() => {
  if (calendarStore.selectedCalendar) return calendarStore.selectedCalendar
  const appSettings = settingsStore.settings
  return {
    first_weekday: appSettings?.default_first_weekday ?? 0,
    show_weekends: appSettings?.default_show_weekends ?? true,
    weekend_days: appSettings?.default_weekend_days ?? [0, 6],
    show_week_numbers: appSettings?.default_show_week_numbers ?? false,
    color: '#3b82f6',
    dark_color: '#60a5fa',
    today_color: '#eff6ff',
    dark_today_color: '#27272a',
    weekend_color: '#f9fafb',
    dark_weekend_color: '#18181b',
  }
})

const SLOT_HEIGHT = 48

const calendarStyle = computed(() => {
  const isDark = themeStore.resolved === 'dark'
  const defaultColor = isDark ? displaySettings.value.dark_color : displaySettings.value.color
  const todayColor = isDark ? displaySettings.value.dark_today_color : displaySettings.value.today_color
  const weekendColor = isDark ? displaySettings.value.dark_weekend_color : displaySettings.value.weekend_color
  const headerColor = darkenForWhiteText(shadeColor(defaultColor, isDark ? 0.55 : 0.42, 0.25))
  const borderColor = mixColor(defaultColor, isDark ? '#ffffff' : '#000000', isDark ? 0.14 : 0.16)
  const outerBorderColor = shadeColor(defaultColor, isDark ? 0.7 : 0.36, isDark ? 0.35 : 0.2)
  // Dark palettes are already near black, so the active toolbar button is lifted instead of darkened.
  const accentColor = isDark ? shadeColor(defaultColor, 2.6, 0.2, 1) : headerColor
  return {
    '--calendar-default-color': defaultColor,
    '--calendar-default-text-color': contrastColor(defaultColor),
    '--calendar-header-color': headerColor,
    '--calendar-header-text-color': contrastColor(headerColor),
    '--calendar-border-color': borderColor,
    '--calendar-slot-height': `${SLOT_HEIGHT}px`,
    '--calendar-outer-border-color': outerBorderColor,
    '--calendar-accent-color': accentColor,
    '--calendar-accent-text-color': contrastColor(accentColor),
    '--fc-classic-border': borderColor,
    '--fc-classic-strong-border': mixColor(borderColor, isDark ? '#ffffff' : '#000000', 0.18),
    '--fc-classic-foreground': contrastColor(defaultColor),
    '--calendar-today-color': todayColor,
    '--calendar-today-text-color': contrastColor(todayColor),
    '--calendar-weekend-color': weekendColor,
    '--calendar-weekend-text-color': contrastColor(weekendColor),
  }
})

function localYMD(d: Date) {
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${month}-${day}`
}

async function handleEventChange(info: EventDropInfo | EventResizeDoneInfo) {
  const event = info.event
  if (!event.start || !auth.isLoggedIn) {
    info.revert()
    return
  }
  let start: string
  let end: string
  if (event.allDay) {
    start = `${localYMD(event.start)}T00:00:00.000Z`
    end = event.end
      ? `${localYMD(new Date(event.end.getTime() - 24 * 60 * 60 * 1000))}T00:00:00.000Z`
      : start
  } else {
    start = event.start.toISOString()
    end = event.end
      ? event.end.toISOString()
      : new Date(event.start.getTime() + 60 * 60 * 1000).toISOString()
  }
  try {
    await api.updateEvent(event.extendedProps.eventId as string, {
      start,
      end,
      all_day: event.allDay,
    })
    reloadVisibleRange(true)
  } catch (e: any) {
    info.revert()
    const detail = e.detail?.detail
    await alert(typeof detail === 'string' ? detail : detail?.message || e.message)
  }
}

function dayCellClass(info: { dow: number; isToday: boolean }) {
  const classes = ['calendar-default']
  if (info.isToday) classes.push('calendar-today')
  if (displaySettings.value.weekend_days.includes(info.dow)) classes.push('calendar-weekend')
  return classes.join(' ')
}

const calendarOptions = computed(() => ({
  plugins: [dayGridPlugin, timeGridPlugin, interactionPlugin, classicThemePlugin],
  initialView: 'dayGridMonth',
  headerToolbar: {
    left: 'prev,next today',
    center: 'title',
    right: 'dayGridMonth,timeGridWeek',
  },
  height: '100%',
  locale: locale.value === 'de' ? deLocale : 'en',
  firstDay: displaySettings.value.first_weekday,
  viewClass: 'calendar-view',
  toolbarTitleClass: 'calendar-toolbar-title',
  buttonGroupClass: 'calendar-button-group',
  buttonClass: (info: { isSelected: boolean; isIconOnly: boolean; buttonGroup: unknown }) => [
    'calendar-button',
    info.isSelected && 'calendar-button-active',
    info.isIconOnly && 'calendar-button-icon',
    !info.buttonGroup && 'calendar-button-solo',
  ].filter(Boolean).join(' '),
  dayHeaderClass: 'calendar-header',
  eventClass: (info: { event: { extendedProps: Record<string, unknown> } }) =>
    info.event.extendedProps.status === 'pending' ? 'calendar-event calendar-event-pending' : 'calendar-event',
  slotMinHeight: SLOT_HEIGHT,
  slotHeaderInnerClass: 'calendar-axis-label',
  allDayHeaderInnerClass: 'calendar-axis-label',
  weekNumberHeaderInnerClass: 'calendar-axis-label',
  inlineWeekNumberClass: 'calendar-inherit-color',
  views: {
    dayGridMonth: { dayRowClass: 'calendar-day-row' },
  },
  weekends: true,
  hiddenDays: displaySettings.value.show_weekends ? [] : displaySettings.value.weekend_days,
  weekNumbers: displaySettings.value.show_week_numbers,
  weekNumberCalculation: displaySettings.value.first_weekday === 1 ? 'ISO' as const : 'local' as const,
  editable: true,
  eventDrop: handleEventChange,
  eventResize: handleEventChange,
  eventTimeFormat: { hour: 'numeric', minute: '2-digit', hour12: hour12() } as Intl.DateTimeFormatOptions,
  slotHeaderFormat: { hour: 'numeric', minute: '2-digit', hour12: hour12() } as Intl.DateTimeFormatOptions,
  dayCellClass,
  dayLaneClass: (info: { dow: number; isToday: boolean }) => `${dayCellClass(info)} calendar-day-lane`,
  datesSet: handleDatesSet,
  dateClick: (info: DateClickInfo) => openCreateModal(info.date),
  selectable: !calendarStore.allSelected,
  selectMirror: !calendarStore.allSelected,
  select: (info: DateSelectInfo) => {
    const end = info.allDay
      ? new Date(info.end.getTime() - 24 * 60 * 60 * 1000)
      : info.end
    openCreateModal(info.start, end, info.allDay)
  },
  eventClick: (info: EventClickInfo) =>
    openEditModal(info.event.extendedProps.eventId as string),
  eventContent: renderEventContent,
  dayMaxEvents: true,
  buttons: {
    today: { text: t('app.today'), display: 'text' as const },
    dayGridMonth: { text: t('app.month'), display: 'text' as const },
    timeGridWeek: { text: t('app.week'), display: 'text' as const },
  },
}))
</script>

<template>
  <div class="calendar-root h-full flex flex-col" :style="calendarStyle">
    <div class="flex-1 overflow-hidden p-2">
      <FullCalendar ref="calendarRef" :options="calendarOptions" />
    </div>

    <EventModal
      v-if="showModal && activeCalendarId"
      :calendarId="activeCalendarId"
      :eventId="modalEventId"
      :defaultStart="modalDate"
      :defaultEnd="modalEndDate"
      :defaultAllDay="modalAllDay"
      @saved="saved"
      @cancel="closeModal"
      @deleted="saved"
    />
  </div>
</template>

<style>
.calendar-root {
  --fc-classic-background: var(--app-surface);
  --fc-classic-today: var(--calendar-today-color);
}

.calendar-root .calendar-toolbar-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--app-text);
}

.calendar-root .calendar-view {
  border-color: var(--calendar-outer-border-color);
}

.calendar-root .calendar-header {
  background-color: var(--calendar-header-color) !important;
  color: var(--calendar-header-text-color) !important;
}

.calendar-root .calendar-header a {
  color: inherit !important;
}

.calendar-root .calendar-inherit-color {
  color: inherit;
}

.calendar-root .calendar-axis-label {
  color: var(--app-text);
}

.calendar-root {
  --calendar-control-bg: var(--app-surface);
  --calendar-control-border: var(--calendar-border-color);
  --calendar-control-hover: color-mix(in srgb, var(--app-surface-muted) 85%, var(--app-text) 15%);
}

[data-color-scheme='dark'] .calendar-root {
  --calendar-control-bg: transparent;
  --calendar-control-hover: color-mix(in srgb, var(--app-surface-muted) 70%, var(--app-text) 30%);
}

.calendar-root .calendar-button-group {
  display: inline-flex;
  gap: 2px;
  padding: 3px;
  border: 1px solid var(--calendar-control-border);
  border-radius: 0.625rem;
  background-color: var(--calendar-control-bg);
  box-shadow: 0 1px 3px rgb(0 0 0 / 0.12);
}

.calendar-root .calendar-button {
  --fc-classic-button: transparent;
  --fc-classic-button-border: transparent;
  --fc-classic-button-strong: var(--calendar-control-hover);
  --fc-classic-button-strong-border: transparent;
  --fc-classic-button-foreground: var(--app-text);
  --fc-classic-button-outline: var(--calendar-accent-color);
  margin: 0 !important;
  border-radius: 0.5rem !important;
  padding: 0.3rem 0.8rem;
  font-size: 0.875rem;
  font-weight: 500;
  text-transform: capitalize;
  box-shadow: none !important;
  transition: background-color 120ms ease, color 120ms ease;
}

.calendar-root .calendar-button-icon {
  padding: 0.3rem 0.45rem;
}

.calendar-root .calendar-button-solo {
  --fc-classic-button: var(--calendar-control-bg);
  --fc-classic-button-border: var(--calendar-control-border);
  --fc-classic-button-strong-border: var(--calendar-control-border);
  --fc-classic-button-foreground: var(--app-text);
  box-shadow: 0 1px 3px rgb(0 0 0 / 0.12) !important;
  /* The theme only draws inline borders on standalone buttons. */
  border: 1px solid var(--calendar-control-border) !important;
  border-radius: 0.625rem !important;
  padding: calc(0.3rem + 3px) 0.9rem;
}

.calendar-root .calendar-button-solo:disabled {
  opacity: 0.5;
}

.calendar-root .calendar-button-active {
  --fc-classic-button: var(--calendar-accent-color);
  --fc-classic-button-strong: var(--calendar-accent-color);
  --fc-classic-button-foreground: var(--calendar-accent-text-color);
  color: var(--calendar-accent-text-color) !important;
  box-shadow: 0 1px 2px rgb(0 0 0 / 0.15) !important;
}

.calendar-root .calendar-event {
  font-size: 0.9rem;
  padding: 0.15rem 0.35rem;
  cursor: pointer;
  border-radius: 0.375rem;
}

/* Bookings awaiting approval: striped and with a dashed outline. */
.calendar-root .calendar-event-pending {
  border-style: dashed !important;
  background-image: repeating-linear-gradient(
    135deg,
    transparent 0 6px,
    rgb(255 255 255 / 0.3) 6px 12px
  );
}

.fc-event-label {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
}

.fc-event-label-multiday {
  padding-inline: 0.3rem;
}

.fc-event-time-label {
  font-weight: 600;
}

.fc-event-category-marker {
  width: 0.625rem;
  height: 0.625rem;
  border-radius: 0.125rem;
  flex: 0 0 auto;
}

.fc-event-declined {
  opacity: 0.6;
  text-decoration: line-through;
}

/* Colored day lanes sit above the slot rows, so the hour and half-hour lines are redrawn on them. */
.calendar-root .calendar-day-lane {
  background-image: repeating-linear-gradient(
    to bottom,
    var(--calendar-border-color) 0 1px,
    transparent 1px var(--calendar-slot-height),
    color-mix(in srgb, var(--calendar-border-color) 55%, transparent) var(--calendar-slot-height) calc(var(--calendar-slot-height) + 1px),
    transparent calc(var(--calendar-slot-height) + 1px) calc(var(--calendar-slot-height) * 2)
  );
}

.calendar-root .calendar-day-row {
  min-height: 6rem;
}

.calendar-default {
  background-color: var(--calendar-default-color);
  color: var(--calendar-default-text-color);
}

.calendar-default a {
  color: inherit;
}

.calendar-weekend {
  background-color: var(--calendar-weekend-color) !important;
  color: var(--calendar-weekend-text-color);
}

.calendar-today {
  background-color: var(--calendar-today-color) !important;
  color: var(--calendar-today-text-color);
}
</style>
