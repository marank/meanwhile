<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
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
import CalendarAgenda from '@/components/calendar/CalendarAgenda.vue'
import CalendarWeekStack from '@/components/calendar/CalendarWeekStack.vue'
import EventModal from '@/components/event/EventModal.vue'
import { ALL_CALENDARS, useCalendarStore } from '@/stores/calendars'
import { useEventStore } from '@/stores/events'
import { useOverviewStore } from '@/stores/overview'
import { useSettingsStore } from '@/stores/settings'
import { useThemeStore } from '@/stores/theme'
import { overviewPalette, paletteColors, themeColors } from '@/services/calendarColors'
import { contrastColor } from '@/services/color'
import { alert } from '@/services/dialog'
import { chooseScope, type OccurrenceRef } from '@/services/occurrences'
import { browserTimeZone, formatTime, hour12, toDateInputValue } from '@/services/datetime'
import { resourceIconSvg } from '@/services/resourceIcons'
import { bookingErrorMessage } from '@/services/errors'
import { parseCalendarQuery, showsTarget, type CalendarViewName } from '@/services/calendarUrl'
import { useLoader } from '@/composables/useLoader'
import { useMediaQuery } from '@/composables/useMediaQuery'
import * as api from '@/api'
import type { Occurrence } from '@/api'

const DAY_MS = 24 * 60 * 60 * 1000
const HOUR_MS = 60 * 60 * 1000

const props = defineProps<{
  calendarId?: string
  folderId?: string
}>()

const router = useRouter()
const route = useRoute()
const calendarStore = useCalendarStore()
const eventStore = useEventStore()
const settingsStore = useSettingsStore()
const overviewStore = useOverviewStore()
const themeStore = useThemeStore()
const { locale, t } = useI18n()

// The URL decides what is shown: /calendar, /calendar/<id-or-readable-path> or /calendar/folder/<id>.
const selection = computed(() => props.folderId ?? props.calendarId ?? ALL_CALENDARS)
watch(
  () => [selection.value, calendarStore.loaded] as const,
  ([id]) => calendarStore.select(id),
  { immediate: true },
)

// A deleted or no longer shared calendar or folder in the URL falls back to all calendars.
watch(
  () => [selection.value, calendarStore.loaded, calendarStore.selectedCalendar, calendarStore.selectedFolder] as const,
  ([id, loaded, calendar, folder]) => {
    if (loaded && id !== ALL_CALENDARS && !calendar && !folder) router.replace('/calendar')
  },
  { immediate: true },
)

const calendarRef = ref<InstanceType<typeof FullCalendar> | null>(null)

interface LabelPart {
  text: string
  /** Name of the icon of the place or resource this part names. */
  icon?: string
}

// What an event says: its title, then where (the place) and with what (the resource), each with its icon.
function eventParts(occ: Occurrence): LabelPart[] {
  let title = occ.recurrence_count === null ? occ.title : `${occ.title} (${occ.recurrence_count})`
  if (occ.status === 'rejected' || occ.status === 'cancelled') {
    title = `${title} (${t('event.declined')})`
  } else if (occ.status === 'pending') {
    title = `${title} (${t('event.pending')})`
  }
  return [
    { text: title },
    { text: occ.location, icon: occ.location_resource_id ? occ.location_resource_icon : undefined },
    { text: occ.resource_name ?? '', icon: occ.resource_icon },
  ].filter((part) => part.text)
}

function eventLabel(occ: Occurrence): string {
  return eventParts(occ)
    .map((part) => part.text)
    .join(' · ')
}

function renderEventContent(info: EventDisplayInfo) {
  const content = document.createElement('span')
  const duration = info.event.start && info.event.end ? info.event.end.getTime() - info.event.start.getTime() : 0
  const classes = [duration > DAY_MS ? 'fc-event-label fc-event-label-multiday' : 'fc-event-label']
  // In the week's narrow columns the time goes above the title, which wraps; short events stay on one line.
  const stacked = info.view.type === 'timeGridWeek' && !info.event.allDay && !info.isShort
  if (stacked) classes.push('fc-event-label-stacked')
  const status = info.event.extendedProps.status as string | undefined
  if (status === 'rejected' || status === 'cancelled') {
    classes.push('fc-event-declined')
  }
  content.className = classes.join(' ')
  if (info.timeText) {
    const time = document.createElement('span')
    time.className = 'fc-event-time-label'
    if (stacked && info.event.start && info.event.end) {
      // Stacked, the start and the end each get a line of their own.
      time.textContent = formatTime(info.event.start)
      const end = document.createElement('span')
      end.className = 'fc-event-time-label fc-event-end-label'
      end.textContent = formatTime(info.event.end)
      content.append(time, end)
    } else {
      time.textContent = info.timeText
      content.append(time)
    }
  }
  const parts = info.event.extendedProps.parts as LabelPart[]
  const text = document.createElement('span')
  const categoryColor = info.event.extendedProps.categoryColor as string | null
  if (categoryColor) {
    const marker = document.createElement('span')
    marker.className = 'fc-event-category-marker'
    marker.style.backgroundColor = categoryColor
    // Stacked, it starts the title's first line rather than taking a line of its own.
    if (stacked) text.append(marker)
    else content.append(marker)
  }
  content.append(text)
  parts.forEach((part, index) => {
    if (index > 0) text.append(' · ')
    const svg = resourceIconSvg(part.icon, 12)
    if (svg) {
      const icon = document.createElement('span')
      icon.className = 'fc-event-resource-icon'
      icon.innerHTML = svg
      text.append(icon)
    }
    text.append(part.text)
  })
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

// The list names each event's calendar when it shows several.
const calendarNameOf = computed(() =>
  !calendarStore.selectedCalendar && calendarStore.selectedCalendarIds.length > 1
    ? (occurrence: Occurrence) => calendarStore.calendarsById.get(occurrence.calendar_id)?.name ?? ''
    : null,
)

const fcEvents = computed(() =>
  eventStore.occurrences.map((occ) => {
    const color = eventColor(occ)
    return {
      id: `${occ.event_id}-${occ.start}`,
      title: eventLabel(occ),
      // All-day occurrences come as UTC midnights; as dates, so FullCalendar doesn't move them
      // to the day before in zones west of UTC.
      start: occ.all_day ? occ.start.slice(0, 10) : occ.start,
      end: occ.all_day ? occ.end.slice(0, 10) : occ.end,
      allDay: occ.all_day,
      startEditable: occ.can_edit,
      durationEditable: occ.can_edit,
      color,
      contrastColor: contrastColor(color),
      extendedProps: {
        occurrence: occ,
        categoryColor: occ.category_color,
        parts: eventParts(occ),
        status: occ.status,
      },
    }
  }),
)

type GridViewType = Exclude<CalendarViewType, 'list'>

const toolbar = ref({
  title: '',
  view: 'dayGridMonth' as CalendarViewType,
  date: new Date(),
  todayInRange: true,
})

// The URL can name the month or week and the view to show: ?date=2026-10, ?month=10&year=2025, ?view=week.
// It is only ever read, never written: a bookmark keeps the parameters it was made with.
const VIEW_TYPES: Record<CalendarViewName, CalendarViewType> = {
  month: 'dayGridMonth',
  week: 'timeGridWeek',
  list: 'list',
}
const initialTarget = parseCalendarQuery(route.query)

function firstOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1)
}

// The list is our own (CalendarAgenda) and shows a month; FullCalendar isn't mounted meanwhile, and
// opens again on the month the list showed.
const listMode = ref(initialTarget.view === 'list')
const listMonth = ref(firstOfMonth(initialTarget.date ?? new Date()))
const listEnd = computed(() => new Date(listMonth.value.getFullYear(), listMonth.value.getMonth() + 1, 1))
const gridStart = ref<{ view: GridViewType; date?: Date }>({
  view: initialTarget.view === 'week' ? 'timeGridWeek' : 'dayGridMonth',
  date: initialTarget.date,
})
const agendaRef = ref<InstanceType<typeof CalendarAgenda> | null>(null)

const listToolbar = computed(() => {
  const now = new Date()
  return {
    title: new Intl.DateTimeFormat(locale.value, { month: 'long', year: 'numeric' }).format(listMonth.value),
    view: 'list' as CalendarViewType,
    date: listMonth.value,
    todayInRange: now >= listMonth.value && now < listEnd.value,
  }
})

watch(
  () => [listMode.value, listMonth.value.getTime()] as const,
  ([list]) => {
    if (list) eventStore.load(listMonth.value, listEnd.value)
  },
  { immediate: true },
)

function shiftListMonth(by: number) {
  listMonth.value = new Date(listMonth.value.getFullYear(), listMonth.value.getMonth() + by, 1)
}

function goPrev() {
  if (listMode.value) shiftListMonth(-1)
  else if (stackMode.value) stackDate.value = addDays(stackStart.value, -7)
  else calendarApi()?.prev()
}

function goNext() {
  if (listMode.value) shiftListMonth(1)
  else if (stackMode.value) stackDate.value = addDays(stackStart.value, 7)
  else calendarApi()?.next()
}

function goToday() {
  if (stackMode.value) {
    stackDate.value = new Date()
    return
  }
  if (!listMode.value) {
    calendarApi()?.today()
    return
  }
  listMonth.value = firstOfMonth(new Date())
  agendaRef.value?.scrollToToday()
}

function gotoDate(date: Date) {
  if (listMode.value) listMonth.value = firstOfMonth(date)
  else if (stackMode.value) stackDate.value = date
  else calendarApi()?.gotoDate(date)
}

/** What the toolbar shows: the list's month, the stacked week, or FullCalendar's view. */
const shownToolbar = computed(() =>
  listMode.value ? listToolbar.value : stackMode.value ? stackToolbar.value : toolbar.value,
)

/** The day to keep in view when switching views: today if it is shown, else the start of what is shown. */
function anchorDate(): Date {
  const shown = shownToolbar.value
  return shown.todayInRange ? new Date() : shown.date
}

function changeView(view: CalendarViewType, date?: Date) {
  if (view === 'list') {
    listMonth.value = firstOfMonth(date ?? anchorDate())
    stackMode.value = false
    listMode.value = true
  } else if (view === 'timeGridWeek' && isPhone.value) {
    stackDate.value = date ?? anchorDate()
    listMode.value = false
    stackMode.value = true
  } else if (listMode.value || stackMode.value) {
    gridStart.value = { view, date: date ?? anchorDate() }
    listMode.value = false
    stackMode.value = false
  } else {
    calendarApi()?.changeView(view, date)
  }
}

function handleDatesSet(info: DatesSetInfo) {
  eventStore.load(info.start, info.end)
  const { view } = info
  const now = new Date()
  const todayInRange = now >= view.currentStart && now < view.currentEnd
  toolbar.value = {
    title: view.title,
    view: view.type as CalendarViewType,
    date: view.currentStart,
    todayInRange,
  }
  // The week with today opens at the current time, an hour before it at the top; others at the usual 6:00.
  if (view.type === 'timeGridWeek' && todayInRange) {
    const hour = String(Math.max(0, now.getHours() - 1)).padStart(2, '0')
    nextTick(() => calendarApi()?.scrollToTime(`${hour}:00`))
  }
}

// A link followed while the calendar is open (another month, the week view) is applied.
watch(
  () => route.query,
  (query) => {
    const target = parseCalendarQuery(query)
    if (stackMode.value) {
      if (target.view && target.view !== 'week') changeView(VIEW_TYPES[target.view], target.date)
      else if (target.date) stackDate.value = target.date
      return
    }
    if (target.view === 'week' && isPhone.value) {
      changeView('timeGridWeek', target.date)
      return
    }
    if (listMode.value) {
      if (target.view && target.view !== 'list') changeView(VIEW_TYPES[target.view], target.date)
      else if (target.date) listMonth.value = firstOfMonth(target.date)
      return
    }
    if (target.view === 'list') {
      changeView('list', target.date)
      return
    }
    const api = calendarApi()
    if (!api) return
    const { currentStart, currentEnd, type } = api.view
    const view: CalendarViewName = type === 'timeGridWeek' ? 'week' : 'month'
    if (showsTarget(target, view, currentStart, currentEnd)) return
    // In one step: the view's own dates-set would otherwise write the URL before the date is reached.
    if (target.view && target.view !== view) api.changeView(VIEW_TYPES[target.view], target.date)
    else if (target.date) api.gotoDate(target.date)
  },
)

function calendarApi() {
  return calendarRef.value?.getApi()
}

function reloadVisibleRange(force = false) {
  if (listMode.value) {
    eventStore.load(listMonth.value, listEnd.value, force)
    return
  }
  if (stackMode.value) {
    eventStore.load(stackStart.value, stackEnd.value, force)
    return
  }
  const view = calendarRef.value?.getApi().view
  if (view) eventStore.load(view.activeStart, view.activeEnd, force)
}

const showModal = ref(false)
const modalEventId = ref<string | null>(null)
const modalOccurrence = ref<OccurrenceRef | null>(null)
const modalDate = ref<Date>(new Date())
const modalEndDate = ref<Date | undefined>(undefined)
const modalAllDay = ref<boolean | undefined>(undefined)

function openCreateModal(start: Date, end?: Date, allDay?: boolean) {
  // New events need one target calendar ("all" and folder selections are ambiguous) where one may add them.
  if (!calendarStore.canCreateInSelected) return
  modalEventId.value = null
  modalDate.value = start
  modalEndDate.value = end
  modalAllDay.value = allDay
  showModal.value = true
}

/** An occurrence of a series (not a changed one, which is an event of its own). */
function seriesOccurrence(occ: Occurrence): OccurrenceRef | null {
  if (!occ.series_id || occ.series_id !== occ.event_id || !occ.recurrence_id) return null
  return { recurrenceId: occ.recurrence_id, start: occ.start, end: occ.end }
}

function openEditModal(occ: Occurrence) {
  modalEventId.value = occ.event_id
  modalOccurrence.value = seriesOccurrence(occ)
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  modalEventId.value = null
  modalOccurrence.value = null
  modalEndDate.value = undefined
  modalAllDay.value = undefined
}

function saved() {
  closeModal()
  reloadVisibleRange(true)
}

watch(
  () => calendarStore.canCreateInSelected,
  (canCreate) => {
    if (!canCreate && showModal.value && !modalEventId.value) closeModal()
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

// On phones the week shows its days stacked (CalendarWeekStack) instead of seven narrow columns of hours;
// like the list, FullCalendar isn't mounted meanwhile. The week is the one with `stackDate` in it.
const isPhone = useMediaQuery('(max-width: 40rem)')
const stackMode = ref(initialTarget.view === 'week' && isPhone.value)
const stackDate = ref(initialTarget.date ?? new Date())
const stackStart = computed(() => {
  const date = stackDate.value
  const back = (date.getDay() - displaySettings.value.first_weekday + 7) % 7
  return new Date(date.getFullYear(), date.getMonth(), date.getDate() - back)
})
const stackEnd = computed(() => addDays(stackStart.value, 7))
const hiddenDays = computed(() => (displaySettings.value.show_weekends ? [] : displaySettings.value.weekend_days))

function addDays(date: Date, days: number): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate() + days)
}

const stackToolbar = computed(() => {
  const now = new Date()
  const format = new Intl.DateTimeFormat(locale.value, { day: 'numeric', month: 'short', year: 'numeric' })
  return {
    title: format.formatRange(stackStart.value, addDays(stackStart.value, 6)),
    view: 'timeGridWeek' as CalendarViewType,
    date: stackStart.value,
    todayInRange: now >= stackStart.value && now < stackEnd.value,
  }
})

watch(
  () => [stackMode.value, stackStart.value.getTime()] as const,
  ([stack]) => {
    if (stack) eventStore.load(stackStart.value, stackEnd.value)
  },
  { immediate: true },
)

// Turning the phone or resizing the window across the breakpoint keeps the week, in the other form.
watch(isPhone, (phone) => {
  if (phone && !listMode.value && !stackMode.value && toolbar.value.view === 'timeGridWeek') {
    changeView('timeGridWeek')
  } else if (!phone && stackMode.value) {
    gridStart.value = { view: 'timeGridWeek', date: anchorDate() }
    stackMode.value = false
  }
})

const SLOT_HEIGHT = 48

// The week view marks the current time with a line across all its days. FullCalendar draws it in today's
// column only; the line is moved left by today's column and widened to all of them (they are equally wide).
const now = ref(new Date())
const clock = setInterval(() => (now.value = new Date()), 60 * 1000)
onBeforeUnmount(() => clearInterval(clock))

const nowColumns = computed(() => {
  if (listMode.value || toolbar.value.view !== 'timeGridWeek') return null
  const hidden = displaySettings.value.show_weekends ? [] : displaySettings.value.weekend_days
  const days = Array.from({ length: 7 }, (_, i) => {
    const start = toolbar.value.date
    return new Date(start.getFullYear(), start.getMonth(), start.getDate() + i)
  }).filter((day) => !hidden.includes(day.getDay()))
  const today = days.findIndex((day) => day.toDateString() === now.value.toDateString())
  return today < 0 ? null : { today, count: days.length }
})

function nowLabel(date: Date): string {
  return new Intl.DateTimeFormat(locale.value, { hour: 'numeric', minute: '2-digit', hour12: hour12() }).format(date)
}

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
    '--calendar-now-column': nowColumns.value?.today ?? 0,
    '--calendar-now-columns': nowColumns.value?.count ?? 1,
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
    // The day before by the calendar, not 24 hours earlier: the night clocks spring forward has 23.
    const lastDay = event.end ? new Date(event.end) : null
    lastDay?.setDate(lastDay.getDate() - 1)
    end = lastDay ? `${toDateInputValue(lastDay)}T00:00:00.000Z` : start
  } else {
    start = event.start.toISOString()
    end = (event.end ?? new Date(event.start.getTime() + HOUR_MS)).toISOString()
  }
  const data = { start, end, all_day: event.allDay, timezone: browserTimeZone() }
  const occ = event.extendedProps.occurrence as Occurrence
  const occurrence = seriesOccurrence(occ)
  try {
    if (occurrence) {
      const scope = await chooseScope('edit')
      if (!scope) {
        info.revert()
        return
      }
      await api.updateOccurrence(occ.event_id, occurrence.recurrenceId, scope, data)
    } else {
      await api.updateEvent(occ.event_id, data)
    }
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
  initialView: gridStart.value.view,
  initialDate: gridStart.value.date,
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
  hiddenDays: hiddenDays.value,
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
  selectable: calendarStore.canCreateInSelected,
  selectMirror: calendarStore.canCreateInSelected,
  select: (info: DateSelectInfo) => {
    const end = info.allDay ? new Date(info.end.getTime() - DAY_MS) : info.end
    openCreateModal(info.start, end, info.allDay)
  },
  eventClick: (info: EventClickInfo) => openEditModal(info.event.extendedProps.occurrence as Occurrence),
  eventContent: renderEventContent,
  events: fcEvents.value,
  dayMaxEvents: true,
  nowIndicator: true,
  nowIndicatorLineClass: 'calendar-now-line',
  nowIndicatorDotClass: 'calendar-now-dot',
  nowIndicatorHeaderClass: 'calendar-now-label',
  nowIndicatorHeaderContent: (info: { date: Date }) => nowLabel(info.date),
}))
</script>

<template>
  <div class="calendar-root h-full flex flex-col" :style="calendarStyle">
    <div class="flex flex-1 flex-col overflow-hidden p-2">
      <CalendarToolbar
        v-bind="shownToolbar"
        @prev="goPrev"
        @next="goNext"
        @today="goToday"
        @goto="gotoDate"
        @change-view="changeView"
      />
      <div class="min-h-0 flex-1">
        <CalendarAgenda
          v-if="listMode"
          ref="agendaRef"
          :occurrences="eventStore.occurrences"
          :range-start="listMonth"
          :range-end="listEnd"
          :color-of="eventColor"
          :calendar-name-of="calendarNameOf"
          :can-create="calendarStore.canCreateInSelected"
          @open="openEditModal"
          @create="openCreateModal"
        />
        <CalendarWeekStack
          v-else-if="stackMode"
          :occurrences="eventStore.occurrences"
          :week-start="stackStart"
          :hidden-days="hiddenDays"
          :weekend-days="displaySettings.weekend_days"
          :color-of="eventColor"
          :can-create="calendarStore.canCreateInSelected"
          @open="openEditModal"
          @create="openCreateModal"
        />
        <FullCalendar v-else ref="calendarRef" :options="calendarOptions" />
      </div>
    </div>

    <EventModal
      v-if="showModal"
      :calendar-id="calendarStore.selectedCalendar?.id"
      :event-id="modalEventId"
      :occurrence="modalOccurrence"
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

/* Phones: seven narrow day columns; smaller event text shows more of each title. */
@media (max-width: 40rem) {
  .calendar-root .calendar-event {
    font-size: 0.75rem;
    padding: 0.05rem 0.2rem;
    border-radius: 0.25rem;
  }

  .calendar-root .fc-event-label {
    gap: 0.15rem;
  }

  .calendar-root .fc-event-category-marker {
    width: 0.5rem;
    height: 0.5rem;
  }
}

/* The current time in the week view: a line across all days (see nowColumns), its time on the axis. */
.calendar-root .calendar-now-line {
  left: calc(var(--calendar-now-column) * -100%);
  right: auto;
  width: calc(var(--calendar-now-columns) * 100%);
  z-index: 5;
  border: none;
  /* The accent, with a thin light edge that sets it off from events of the same color. */
  border-top: 2px solid var(--calendar-accent-color);
  box-shadow: 0 0 0 1px var(--app-surface);
  pointer-events: none;
}

/* On dark backgrounds a dark edge hardly shows on events: there the core is light, edged in the accent. */
html.dark .calendar-root .calendar-now-line {
  border-top-color: var(--calendar-accent-text-color);
  box-shadow: 0 0 0 1px var(--calendar-accent-color);
}

/* Day columns are layers of their own, later ones above earlier ones; today's lifts its line above all. */
.calendar-root .calendar-day-lane:has(.calendar-now-line) {
  z-index: 2;
}

/* Where the line crosses today. */
.calendar-root .calendar-now-dot {
  z-index: 6;
  width: 10px;
  height: 10px;
  margin: -4px 0 0 -5px;
  border: none;
  border-radius: 9999px;
  background-color: var(--calendar-accent-color);
  box-shadow: 0 0 0 2px var(--app-surface);
}

html.dark .calendar-root .calendar-now-dot {
  box-shadow: 0 0 0 2px var(--calendar-accent-text-color);
}

.calendar-root .calendar-now-label {
  z-index: 6;
  left: 2px;
  right: auto;
  width: auto;
  height: auto;
  border: none;
  transform: translateY(-50%);
  padding: 0 0.3rem;
  border-radius: 0.25rem;
  font-size: 0.7rem;
  font-weight: 600;
  line-height: 1.1rem;
  background-color: var(--calendar-accent-color);
  color: var(--calendar-accent-text-color);
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

.fc-event-label-stacked {
  flex-direction: column;
  align-items: flex-start;
  gap: 0;
  /* Stays in view while a long event is scrolled past its start (sticky within the event). */
  position: sticky;
  top: 0;
  max-height: 100%;
  white-space: normal;
  /* Words break only where one doesn't fit a line by itself, then hyphenated. */
  overflow-wrap: break-word;
  hyphens: auto;
}

/* As wide as the event, so a word too long for it breaks instead of running out of it. */
.fc-event-label-stacked > * {
  align-self: stretch;
  min-width: 0;
}

/* Where it gets tight, the end gives way first, then the title down to its first line; the start stays. */
.fc-event-label-stacked .fc-event-end-label {
  flex: 0 1000 auto;
  min-height: 0;
  font-weight: 400;
  opacity: 0.85;
}

/* The title gets what is left of the event's height. */
.fc-event-label-stacked > :last-child {
  flex: 1 1 auto;
  min-height: min(1.2rem, 100%);
  overflow: hidden;
}

.fc-event-label-stacked .fc-event-time-label {
  flex: none;
  line-height: 1rem;
  max-width: 100%;
  overflow: hidden;
  font-size: 0.75rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fc-event-label-stacked .fc-event-category-marker {
  display: inline-block;
  margin-right: 0.25rem;
  vertical-align: 0.05rem;
}

.fc-event-label-multiday {
  padding-inline: 0.3rem;
}

.fc-event-time-label {
  font-weight: 600;
}

.fc-event-resource-icon {
  display: inline-block;
  margin-right: 0.25rem;
  vertical-align: -0.15rem;
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
  /* The weeks share the height of the view, so the month never scrolls; what doesn't fit into a day
     shows as "+ n more". */
  min-height: 0;
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
