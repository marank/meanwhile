<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import FullCalendar from '@fullcalendar/vue3'
import dayGridPlugin from '@fullcalendar/vue3/daygrid'
import timeGridPlugin from '@fullcalendar/vue3/timegrid'
import interactionPlugin from '@fullcalendar/vue3/interaction'
import classicThemePlugin from '@fullcalendar/vue3/themes/classic'
import deLocale from '@fullcalendar/vue3/locales/de'
import type {
  DateClickInfo,
  DateSelectInfo,
  DatesSetInfo,
  EventClickInfo,
  EventDropInfo,
  EventResizeDoneInfo,
} from '@fullcalendar/vue3'
import '@fullcalendar/vue3/skeleton.css'
import '@fullcalendar/vue3/themes/classic/theme.css'
import '@fullcalendar/vue3/themes/classic/palette.css'
import type { Occurrence } from '@/api'
import type { GridRange, GridViewType } from '@/composables/useCalendarNavigation'
import { SLOT_HEIGHT } from '@/composables/useCalendarDisplay'
import { baseLanguage } from '@/i18n'
import { contrastColor } from '@/services/color'
import { hour12, newEventStart } from '@/services/datetime'
import { eventLabel, eventParts, renderEventContent } from '@/services/eventContent'
import { moveEvent } from '@/services/eventMove'
import { takesNoTime } from '@/services/occurrences'

/** The month and week grid (FullCalendar), with the events in their colors and labels. */
const props = defineProps<{
  occurrences: Occurrence[]
  colorOf: (occurrence: Occurrence) => string
  display: { first_weekday: number; show_week_numbers: boolean; weekend_days: number[] }
  hiddenDays: number[]
  initialView: GridViewType
  initialDate?: Date
  canCreate: boolean
  /** The hour the user's day starts, where a new event on a picked day begins (User.day_start). */
  dayStart?: number
}>()

const emit = defineEmits<{
  rangeShown: [range: GridRange]
  open: [occurrence: Occurrence]
  create: [start: Date, end?: Date, allDay?: boolean]
  /** An event was dragged or resized, and saved. */
  moved: []
}>()

const { locale, t } = useI18n()
const calendarRef = ref<InstanceType<typeof FullCalendar> | null>(null)

function getApi() {
  return calendarRef.value?.getApi()
}

defineExpose({ getApi })

const fcEvents = computed(() =>
  props.occurrences.map((occ) => {
    const color = props.colorOf(occ)
    const parts = eventParts(occ, t)
    return {
      id: `${occ.event_id}-${occ.start}`,
      title: eventLabel(parts),
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
        parts,
        status: occ.status,
        free: takesNoTime(occ),
      },
    }
  }),
)

function handleDatesSet(info: DatesSetInfo) {
  emit('rangeShown', info)
  const { view } = info
  const now = new Date()
  // The week with today opens at the current time, an hour before it at the top; others at the usual 6:00.
  if (view.type === 'timeGridWeek' && now >= view.currentStart && now < view.currentEnd) {
    const hour = String(Math.max(0, now.getHours() - 1)).padStart(2, '0')
    void nextTick(() => getApi()?.scrollToTime(`${hour}:00`))
  }
}

async function handleEventChange(info: EventDropInfo | EventResizeDoneInfo) {
  if (await moveEvent(info)) emit('moved')
}

function nowLabel(date: Date): string {
  return new Intl.DateTimeFormat(locale.value, { hour: 'numeric', minute: '2-digit', hour12: hour12() }).format(date)
}

function dayCellClass(info: { dow: number; isToday: boolean }) {
  const classes = ['calendar-default']
  if (info.isToday) classes.push('calendar-today')
  if (props.display.weekend_days.includes(info.dow)) classes.push('calendar-weekend')
  return classes.join(' ')
}

const calendarOptions = computed(() => ({
  plugins: [dayGridPlugin, timeGridPlugin, interactionPlugin, classicThemePlugin],
  initialView: props.initialView,
  initialDate: props.initialDate,
  // The toolbar is our own (CalendarToolbar), so it can hold month and year fields.
  headerToolbar: false as const,
  height: '100%',
  locale: baseLanguage(locale.value) === 'de' ? deLocale : 'en',
  firstDay: props.display.first_weekday,
  viewClass: 'calendar-view',
  dayHeaderClass: 'calendar-header',
  eventClass: (info: { event: { extendedProps: Record<string, unknown> } }) => {
    const extended = info.event.extendedProps
    return [
      'calendar-event',
      extended.status === 'pending' && 'calendar-event-pending',
      extended.free === true && 'calendar-event-free',
    ]
      .filter(Boolean)
      .join(' ')
  },
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
  hiddenDays: props.hiddenDays,
  weekNumbers: props.display.show_week_numbers,
  weekNumberCalculation: props.display.first_weekday === 1 ? ('ISO' as const) : ('local' as const),
  editable: true,
  eventDrop: handleEventChange,
  eventResize: handleEventChange,
  eventTimeFormat: { hour: 'numeric', minute: '2-digit', hour12: hour12() } as Intl.DateTimeFormatOptions,
  slotHeaderFormat: { hour: 'numeric', minute: '2-digit', hour12: hour12() } as Intl.DateTimeFormatOptions,
  dayCellClass,
  dayLaneClass: (info: { dow: number; isToday: boolean }) => `${dayCellClass(info)} calendar-day-lane`,
  datesSet: handleDatesSet,
  // A day of the month view comes at midnight; a slot of the week view at its time.
  dateClick: (info: DateClickInfo) =>
    emit('create', info.allDay ? newEventStart(info.date, props.dayStart) : info.date),
  selectable: props.canCreate,
  selectMirror: props.canCreate,
  select: (info: DateSelectInfo) => {
    // The day before by the calendar, as in movedTimes.
    const end = new Date(info.end)
    if (info.allDay) end.setDate(end.getDate() - 1)
    emit('create', info.start, end, info.allDay)
  },
  eventClick: (info: EventClickInfo) => emit('open', info.event.extendedProps.occurrence as Occurrence),
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
  <FullCalendar ref="calendarRef" :options="calendarOptions" />
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

/* Events shown as free: the calendar's color only as a tint, as Outlook shows them. */
.calendar-root .calendar-event-free {
  background-color: color-mix(in srgb, var(--fc-event-color) 35%, var(--app-surface)) !important;
  color: var(--app-text) !important;
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
