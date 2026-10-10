<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import FullCalendar from '@fullcalendar/vue3'
import dayGridPlugin from '@fullcalendar/vue3/daygrid'
import timeGridPlugin from '@fullcalendar/vue3/timegrid'
import interactionPlugin from '@fullcalendar/vue3/interaction'
import classicThemePlugin from '@fullcalendar/vue3/themes/classic'
import deLocale from '@fullcalendar/vue3/locales/de'
import type {
  DateClickInfo,
  DateSelectInfo,
  EventClickInfo,
  EventDisplayInfo,
  DatesSetInfo,
  EventDropInfo,
  EventResizeDoneInfo,
} from '@fullcalendar/vue3'
import '@fullcalendar/vue3/skeleton.css'
import '@fullcalendar/vue3/themes/classic/theme.css'
import '@fullcalendar/vue3/themes/classic/palette.css'
import CalendarToolbar, { type CalendarViewType } from '@/components/calendar/CalendarToolbar.vue'
import EventModal from '@/components/event/EventModal.vue'
import { ALL_CALENDARS, useCalendarStore } from '@/stores/calendars'
import { useEventStore } from '@/stores/events'
import { useOverviewStore } from '@/stores/overview'
import { useSettingsStore } from '@/stores/settings'
import { useThemeStore } from '@/stores/theme'
import { overviewPalette, paletteColors, themeColors } from '@/services/calendarColors'
import { contrastColor } from '@/services/color'
import { alert } from '@/services/dialog'
import { browserTimeZone, hour12, toDateInputValue } from '@/services/datetime'
import { bookingErrorMessage } from '@/services/errors'
import { useLoader } from '@/composables/useLoader'
import * as api from '@/api'
import type { Occurrence } from '@/api'

const DAY_MS = 24 * 60 * 60 * 1000
const HOUR_MS = 60 * 60 * 1000

const props = defineProps<{
  calendarId?: string
  folderId?: string
}>()

const router = useRouter()
const calendarStore = useCalendarStore()
const eventStore = useEventStore()
const settingsStore = useSettingsStore()
const overviewStore = useOverviewStore()
const themeStore = useThemeStore()
const { locale, t } = useI18n()

// The URL decides what is shown: /calendar, /calendar/<id> or /calendar/folder/<id>.
const selection = computed(() => props.folderId ?? props.calendarId ?? ALL_CALENDARS)
watch(selection, (id) => calendarStore.select(id), { immediate: true })

// A deleted or no longer shared calendar or folder in the URL falls back to all calendars.
watch(
  () => [selection.value, calendarStore.loaded, calendarStore.selectedCalendar, calendarStore.selectedFolder] as const,
  ([id, loaded, calendar, folder]) => {
    if (loaded && id !== ALL_CALENDARS && !calendar && !folder) router.replace('/calendar')
  },
  { immediate: true },
)

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

function renderEventContent(info: EventDisplayInfo) {
  const content = document.createElement('span')
  const duration = info.event.start && info.event.end ? info.event.end.getTime() - info.event.start.getTime() : 0
  const classes = [duration > DAY_MS ? 'fc-event-label fc-event-label-multiday' : 'fc-event-label']
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

// Events take their calendar's current event color, so palette changes show up without reloading them.
// The overview ("All calendars", folders) can instead show all events in its own event color.
function eventColor(occurrence: Occurrence): string {
  const overview = overviewStore.settings
  const useOverviewColor = !calendarStore.selectedCalendar && overview && !overview.use_calendar_colors
  const source =
    (useOverviewColor ? overview : calendarStore.calendarsById.get(occurrence.calendar_id)) ?? displaySettings.value
  return themeStore.isDark ? source.dark_event_color : source.event_color
}

const fcEvents = computed(() =>
  eventStore.occurrences.map((occ) => {
    const color = eventColor(occ)
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

const toolbar = ref({
  title: '',
  view: 'dayGridMonth' as CalendarViewType,
  date: new Date(),
  todayInRange: true,
})

function handleDatesSet(info: DatesSetInfo) {
  eventStore.load(info.start, info.end)
  const { view } = info
  const now = new Date()
  toolbar.value = {
    title: view.title,
    view: view.type as CalendarViewType,
    date: view.currentStart,
    todayInRange: now >= view.currentStart && now < view.currentEnd,
  }
}

function calendarApi() {
  return calendarRef.value?.getApi()
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
  // New events need one target calendar; "all" and folder selections are ambiguous.
  if (!calendarStore.selectedCalendar) return
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

watch(
  () => calendarStore.selectedCalendar,
  (selected) => {
    if (!selected && showModal.value && !modalEventId.value) closeModal()
  },
)

watch(
  () => calendarStore.selectedCalendarIds.join(','),
  () => reloadVisibleRange(),
  { flush: 'post' },
)

useLoader(overviewStore.load, { immediate: !overviewStore.settings })

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

const SLOT_HEIGHT = 48

// Only text colors are computed; everything else is stored per calendar.
const calendarStyle = computed(() => {
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

async function handleEventChange(info: EventDropInfo | EventResizeDoneInfo) {
  const event = info.event
  if (!event.start) {
    info.revert()
    return
  }
  let start: string
  let end: string
  if (event.allDay) {
    // All-day events are stored as UTC midnights; FullCalendar's end is exclusive, the API's inclusive.
    start = `${toDateInputValue(event.start)}T00:00:00.000Z`
    end = event.end ? `${toDateInputValue(new Date(event.end.getTime() - DAY_MS))}T00:00:00.000Z` : start
  } else {
    start = event.start.toISOString()
    end = (event.end ?? new Date(event.start.getTime() + HOUR_MS)).toISOString()
  }
  try {
    await api.updateEvent(event.extendedProps.eventId as string, {
      start,
      end,
      all_day: event.allDay,
      timezone: browserTimeZone(),
    })
    reloadVisibleRange(true)
  } catch (error) {
    info.revert()
    await alert(bookingErrorMessage(error))
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
  // The toolbar is our own (CalendarToolbar), so it can hold month and year fields.
  headerToolbar: false as const,
  height: '100%',
  locale: locale.value === 'de' ? deLocale : 'en',
  firstDay: displaySettings.value.first_weekday,
  viewClass: 'calendar-view',
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
    // The week title names its days; the toolbar's month and year fields cover the rest.
    timeGridWeek: { titleFormat: { day: 'numeric', month: 'short', year: 'numeric' } as const },
  },
  weekends: true,
  hiddenDays: displaySettings.value.show_weekends ? [] : displaySettings.value.weekend_days,
  weekNumbers: displaySettings.value.show_week_numbers,
  weekNumberCalculation: displaySettings.value.first_weekday === 1 ? ('ISO' as const) : ('local' as const),
  editable: true,
  eventDrop: handleEventChange,
  eventResize: handleEventChange,
  eventTimeFormat: { hour: 'numeric', minute: '2-digit', hour12: hour12() } as Intl.DateTimeFormatOptions,
  slotHeaderFormat: { hour: 'numeric', minute: '2-digit', hour12: hour12() } as Intl.DateTimeFormatOptions,
  dayCellClass,
  dayLaneClass: (info: { dow: number; isToday: boolean }) => `${dayCellClass(info)} calendar-day-lane`,
  datesSet: handleDatesSet,
  dateClick: (info: DateClickInfo) => openCreateModal(info.date),
  selectable: !!calendarStore.selectedCalendar,
  selectMirror: !!calendarStore.selectedCalendar,
  select: (info: DateSelectInfo) => {
    const end = info.allDay ? new Date(info.end.getTime() - DAY_MS) : info.end
    openCreateModal(info.start, end, info.allDay)
  },
  eventClick: (info: EventClickInfo) => openEditModal(info.event.extendedProps.eventId as string),
  eventContent: renderEventContent,
  events: fcEvents.value,
  dayMaxEvents: true,
}))
</script>

<template>
  <div class="calendar-root h-full flex flex-col" :style="calendarStyle">
    <div class="flex flex-1 flex-col overflow-hidden p-2">
      <CalendarToolbar
        v-bind="toolbar"
        @prev="calendarApi()?.prev()"
        @next="calendarApi()?.next()"
        @today="calendarApi()?.today()"
        @goto="calendarApi()?.gotoDate($event)"
        @change-view="calendarApi()?.changeView($event)"
      />
      <div class="min-h-0 flex-1">
        <FullCalendar ref="calendarRef" :options="calendarOptions" />
      </div>
    </div>

    <EventModal
      v-if="showModal"
      :calendar-id="calendarStore.selectedCalendar?.id"
      :event-id="modalEventId"
      :default-start="modalDate"
      :default-end="modalEndDate"
      :default-all-day="modalAllDay"
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

html.dark .calendar-root {
  --calendar-control-bg: transparent;
  --calendar-control-hover: color-mix(in srgb, var(--app-surface-muted) 70%, var(--app-text) 30%);
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
  background-image: repeating-linear-gradient(135deg, transparent 0 6px, rgb(255 255 255 / 0.3) 6px 12px);
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
    color-mix(in srgb, var(--calendar-border-color) 55%, transparent) var(--calendar-slot-height)
      calc(var(--calendar-slot-height) + 1px),
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
