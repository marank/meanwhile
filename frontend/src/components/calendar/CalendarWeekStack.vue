<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { MapPin } from '@lucide/vue'
import type { Occurrence } from '@/api'
import { dayKey, groupByDay, isPast, type AgendaEntry } from '@/services/agenda'
import { formatTime } from '@/services/datetime'
import { resourceIcon } from '@/services/resourceIcons'

/**
 * The week on phones: its days stacked, each a row of event tiles, instead of the hour grid with seven
 * narrow columns. The rows share the height of the view; a row with many events scrolls sideways.
 */
const props = defineProps<{
  occurrences: Occurrence[]
  /** Local midnight of the week's first day. */
  weekStart: Date
  /** Weekdays (0 = Sunday) left out, as weekends can be. */
  hiddenDays: number[]
  /** Weekdays shown in the weekend color. */
  weekendDays: number[]
  colorOf: (occurrence: Occurrence) => string
  canCreate: boolean
}>()

const emit = defineEmits<{
  open: [occurrence: Occurrence]
  create: [date: Date]
}>()

const { t, locale } = useI18n()

// The clock moves on while the week is open: past events fade, today follows midnight.
const now = ref(new Date())
const clock = setInterval(() => (now.value = new Date()), 60 * 1000)
onBeforeUnmount(() => clearInterval(clock))
const todayKey = computed(() => dayKey(now.value))

const weekEnd = computed(
  () => new Date(props.weekStart.getFullYear(), props.weekStart.getMonth(), props.weekStart.getDate() + 7),
)

const days = computed(() => {
  const entries = new Map(
    groupByDay(props.occurrences, props.weekStart, weekEnd.value).map((day) => [day.key, day.entries]),
  )
  return Array.from({ length: 7 }, (_, index) => {
    const start = props.weekStart
    return new Date(start.getFullYear(), start.getMonth(), start.getDate() + index)
  })
    .filter((date) => !props.hiddenDays.includes(date.getDay()))
    .map((date) => ({ date, key: dayKey(date), entries: entries.get(dayKey(date)) ?? [] }))
})

function weekday(date: Date): string {
  return date.toLocaleDateString(locale.value, { weekday: 'short' })
}

function title(occ: Occurrence): string {
  return occ.recurrence_count === null ? occ.title : `${occ.title} (${occ.recurrence_count})`
}

/** When the entry starts that day, or how it relates to the day (all day, from, until). */
function time(entry: AgendaEntry): string {
  const occ = entry.occurrence
  if (occ.all_day || entry.span === 'middle') return t('event.allDay')
  if (entry.span === 'first') return t('agenda.from', { time: formatTime(occ.start) })
  if (entry.span === 'last') return t('agenda.until', { time: formatTime(occ.end) })
  return formatTime(occ.start)
}

/** How long it takes ("30 Min.", "1 Std. 30 Min."), or which of its days this is. */
function duration(entry: AgendaEntry): string {
  if (entry.dayCount > 1) return t('agenda.dayOf', { index: entry.dayIndex, count: entry.dayCount })
  const occ = entry.occurrence
  if (occ.all_day) return ''
  const minutes = Math.round((new Date(occ.end).getTime() - new Date(occ.start).getTime()) / 60000)
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  if (!hours) return t('weekStack.minutes', { n: rest })
  return rest ? t('weekStack.hoursMinutes', { h: hours, m: rest }) : t('weekStack.hours', { n: hours })
}

function isDeclined(occ: Occurrence): boolean {
  return occ.status === 'rejected' || occ.status === 'cancelled'
}

function create(date: Date) {
  if (props.canCreate) emit('create', date)
}
</script>

<template>
  <div class="week-stack">
    <section
      v-for="day in days"
      :key="day.key"
      class="week-stack-day"
      :class="{
        'week-stack-today': day.key === todayKey,
        'week-stack-weekend': weekendDays.includes(day.date.getDay()),
      }"
    >
      <button
        type="button"
        class="week-stack-date"
        :disabled="!canCreate"
        :aria-label="day.date.toLocaleDateString(locale, { weekday: 'long', day: 'numeric', month: 'long' })"
        @click="create(day.date)"
      >
        <span class="week-stack-weekday">{{ weekday(day.date) }}</span>
        <span class="week-stack-daynumber">{{ day.date.getDate() }}</span>
      </button>

      <!-- Tapping the free part of a day adds an event there. -->
      <div class="week-stack-events" @click.self="create(day.date)">
        <button
          v-for="entry in day.entries"
          :key="`${entry.occurrence.event_id}-${entry.occurrence.start}`"
          type="button"
          class="week-stack-event"
          :class="{
            'week-stack-event-past': isPast(entry.occurrence, now),
            'week-stack-event-pending': entry.occurrence.status === 'pending',
            'week-stack-event-declined': isDeclined(entry.occurrence),
          }"
          :style="{ '--week-stack-color': colorOf(entry.occurrence) }"
          @click="emit('open', entry.occurrence)"
        >
          <span class="week-stack-title" :title="entry.occurrence.category_name ?? undefined">
            <span
              v-if="entry.occurrence.category_color"
              class="week-stack-category"
              :style="{ backgroundColor: entry.occurrence.category_color }"
              aria-hidden="true"
            ></span>
            {{ title(entry.occurrence) }}
          </span>
          <span v-if="entry.occurrence.location" class="week-stack-meta">
            <component
              :is="
                (entry.occurrence.location_resource_id && resourceIcon(entry.occurrence.location_resource_icon)) ||
                MapPin
              "
              :size="12"
              class="shrink-0"
              aria-hidden="true"
            />
            <span class="truncate">{{ entry.occurrence.location }}</span>
          </span>
          <span v-if="entry.occurrence.resource_name" class="week-stack-meta">
            <component
              :is="resourceIcon(entry.occurrence.resource_icon)"
              v-if="resourceIcon(entry.occurrence.resource_icon)"
              :size="12"
              class="shrink-0"
              aria-hidden="true"
            />
            <span class="truncate">{{ entry.occurrence.resource_name }}</span>
          </span>
          <span class="week-stack-time">
            {{ time(entry) }}<span v-if="duration(entry)" class="week-stack-duration"> · {{ duration(entry) }}</span>
          </span>
        </button>
      </div>
    </section>
  </div>
</template>

<style scoped>
/* The colors come from the calendar's palette via the --calendar-* variables of the calendar view. */
.week-stack {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow-y: auto;
  border: 1px solid var(--calendar-outer-border-color);
  background-color: var(--calendar-default-color);
  color: var(--calendar-default-text-color);
}

.week-stack-day {
  display: grid;
  flex: 1 1 0;
  /* Room for a tile's title, place, resource and time; below that the week scrolls. */
  min-height: 5.25rem;
  grid-template-columns: 3.25rem minmax(0, 1fr);
}

.week-stack-day + .week-stack-day {
  border-top: 1px solid var(--calendar-border-color);
}

.week-stack-weekend {
  background-color: var(--calendar-weekend-color);
  color: var(--calendar-weekend-text-color);
}

.week-stack-date {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-right: 1px solid var(--calendar-border-color);
  color: inherit;
}

.week-stack-date:disabled {
  cursor: default;
}

.week-stack-weekday {
  font-size: 0.75rem;
  opacity: 0.75;
}

.week-stack-daynumber {
  font-size: 1.25rem;
  font-weight: 600;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}

/* Today: in the accent color, with a bar along its edge. */
.week-stack-today .week-stack-date {
  color: var(--calendar-accent-color);
  box-shadow: inset 3px 0 0 var(--calendar-accent-color);
}

.week-stack-events {
  display: flex;
  gap: 0.25rem;
  padding: 0.25rem;
  overflow-x: auto;
  scrollbar-width: none;
}

.week-stack-events::-webkit-scrollbar {
  display: none;
}

.week-stack-event {
  display: flex;
  flex: 0 0 min(8.5rem, 42%);
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  padding: 0.3rem 0.45rem 0.35rem;
  border-top: 3px solid var(--week-stack-color);
  border-radius: 0.375rem;
  background-color: color-mix(in srgb, var(--week-stack-color) 40%, var(--app-surface));
  color: var(--app-text);
  font-size: 0.75rem;
  line-height: 1.15rem;
  text-align: left;
}

.week-stack-title {
  /* At least its first line; it takes what the place, resource and time leave. */
  flex: 1 1 auto;
  min-height: 1.15rem;
  overflow: hidden;
  font-weight: 600;
  overflow-wrap: anywhere;
}

/* The category's color, as in the other views. */
.week-stack-category {
  display: inline-block;
  width: 0.55rem;
  height: 0.55rem;
  margin-right: 0.25rem;
  border-radius: 0.125rem;
}

.week-stack-meta {
  display: flex;
  flex: none;
  align-items: center;
  gap: 0.25rem;
  min-width: 0;
  color: var(--app-text-muted);
}

.week-stack-time {
  flex: none;
  overflow: hidden;
  font-variant-numeric: tabular-nums;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.week-stack-duration {
  flex: none;
  color: var(--app-text-muted);
}

.week-stack-event-past {
  opacity: 0.55;
}

/* Bookings awaiting approval: dashed, as in the other views. */
.week-stack-event-pending {
  border: 1px dashed var(--week-stack-color);
  border-top: 3px solid var(--week-stack-color);
}

.week-stack-event-declined .week-stack-title {
  text-decoration: line-through;
}
</style>
