<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import FullCalendar from '@fullcalendar/vue3'
import dayGridPlugin from '@fullcalendar/vue3/daygrid'
import timeGridPlugin from '@fullcalendar/vue3/timegrid'
import interactionPlugin from '@fullcalendar/vue3/interaction'
import classicThemePlugin from '@fullcalendar/vue3/themes/classic'
import deLocale from '@fullcalendar/vue3/locales/de'
import type { DateClickInfo, DateSelectInfo, DayCellInfo, EventClickInfo, EventDisplayInfo, DatesSetInfo } from '@fullcalendar/vue3'
import '@fullcalendar/vue3/skeleton.css'
import '@fullcalendar/vue3/themes/classic/theme.css'
import '@fullcalendar/vue3/themes/classic/palette.css'
import EventModal from '@/components/EventModal.vue'
import { useCalendarStore } from '@/stores/calendars'
import { useEventStore } from '@/stores/events'
import { useThemeStore } from '@/stores/theme'
import type { Occurrence } from '@/api'

const calendarStore = useCalendarStore()
const eventStore = useEventStore()
const themeStore = useThemeStore()
const { locale, t } = useI18n()

const calendarRef = ref<InstanceType<typeof FullCalendar> | null>(null)

function eventLabel(occ: Occurrence): string {
  const title = occ.recurrence_count === null ? occ.title : `${occ.title} (${occ.recurrence_count})`
  return occ.resource_name ? `${title} · ${occ.resource_name}` : title
}

function contrastColor(color: string): string {
  const value = color.replace('#', '')
  const red = Number.parseInt(value.slice(0, 2), 16)
  const green = Number.parseInt(value.slice(2, 4), 16)
  const blue = Number.parseInt(value.slice(4, 6), 16)
  return (red * 299 + green * 587 + blue * 114) / 1000 > 150 ? '#111827' : '#ffffff'
}

function renderEventContent(info: EventDisplayInfo) {
  const content = document.createElement('span')
  const duration = info.event.start && info.event.end
    ? info.event.end.getTime() - info.event.start.getTime()
    : 0
  content.className = duration > 24 * 60 * 60 * 1000
    ? 'fc-event-label fc-event-label-multiday'
    : 'fc-event-label'
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
      color,
      contrastColor: contrastColor(color),
      extendedProps: { eventId: occ.event_id, categoryColor: occ.category_color },
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
  () => eventStore.selectedCalendarIds().join(','),
  () => reloadVisibleRange(),
  { flush: 'post' },
)

const displaySettings = computed(() => calendarStore.selectedCalendar || {
  first_weekday: 0,
  show_weekends: true,
  weekend_days: [0, 6],
  today_color: '#eff6ff',
  dark_today_color: '#27272a',
  weekend_color: '#f9fafb',
  dark_weekend_color: '#18181b',
})

const calendarStyle = computed(() => ({
  '--calendar-today-color': themeStore.resolved === 'dark'
    ? displaySettings.value.dark_today_color
    : displaySettings.value.today_color,
  '--calendar-weekend-color': themeStore.resolved === 'dark'
    ? displaySettings.value.dark_weekend_color
    : displaySettings.value.weekend_color,
}))

function dayCellClass(info: DayCellInfo) {
  const classes = []
  if (info.isToday) classes.push('calendar-today')
  if (displaySettings.value.weekend_days.includes(info.date.getDay())) classes.push('calendar-weekend')
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
  weekends: true,
  hiddenDays: displaySettings.value.show_weekends ? [] : displaySettings.value.weekend_days,
  dayCellClass,
  datesSet: handleDatesSet,
  dateClick: (info: DateClickInfo) => openCreateModal(info.date),
  selectable: true,
  selectMirror: true,
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
  buttonText: {
    today: t('app.today'),
    month: t('app.month'),
    week: t('app.week'),
  },
}))
</script>

<template>
  <div class="h-full flex flex-col" :style="calendarStyle">
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
.fc {
  --fc-border-color: #e5e7eb;
  --fc-today-bg-color: #eff6ff;
  --fc-button-bg-color: #ffffff;
  --fc-button-border-color: #d1d5db;
  --fc-button-text-color: #374151;
  --fc-button-hover-bg-color: #f3f4f6;
  --fc-button-active-bg-color: #2563eb;
  --fc-button-active-border-color: #2563eb;
  font-family: inherit;
}

.fc .fc-toolbar-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: #1f2937;
}

.fc .fc-button {
  text-transform: capitalize;
  box-shadow: none !important;
}

.fc-event {
  font-size: 0.9rem;
  padding: 0.15rem 0.35rem;
  cursor: pointer;
  border-radius: 0.375rem;
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

.fc .fc-daygrid-day-frame {
  min-height: 6rem;
}

.fc .fc-timegrid-slot {
  height: 3rem;
}

.calendar-weekend {
  background-color: var(--calendar-weekend-color) !important;
}

.calendar-today {
  background-color: var(--calendar-today-color) !important;
}
</style>
