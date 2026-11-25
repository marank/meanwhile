<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { CalendarX, Clock, MapPin, Plus, Repeat, Search, X } from '@lucide/vue'
import type { Occurrence } from '@/api'
import { groupByDay, isPast, matchesSearch, type AgendaDay, type AgendaEntry } from '@/services/agenda'
import { dayKey } from '@/services/days'
import { formatTime, monthName, newEventStart } from '@/services/datetime'
import { resourceIcon } from '@/services/resourceIcons'

const props = defineProps<{
  occurrences: Occurrence[]
  /** The month shown: its first day, and the first day of the month after it. */
  rangeStart: Date
  rangeEnd: Date
  /** The color an event is shown in (its calendar's, or the overview's). */
  colorOf: (occurrence: Occurrence) => string
  /** The calendar's name, for lists that show several calendars; null when only one is shown. */
  calendarNameOf: ((occurrence: Occurrence) => string) | null
  canCreate: boolean
  /** The hour the user's day starts, where a new event on a picked day begins (User.day_start). */
  dayStart?: number
}>()

const emit = defineEmits<{
  open: [occurrence: Occurrence]
  create: [date: Date]
}>()

const { locale, t } = useI18n()

const query = ref('')
const upcomingOnly = ref(false)

// The clock moves on while the list is open: past events fade and the "now" line follows.
const now = ref(new Date())
const clock = setInterval(() => (now.value = new Date()), 60 * 1000)
onBeforeUnmount(() => clearInterval(clock))

const todayKey = computed(() => dayKey(now.value))
const showsToday = computed(() => now.value >= props.rangeStart && now.value < props.rangeEnd)
const period = computed(() => monthName(props.rangeStart.getMonth() + 1))

const visible = computed(() =>
  props.occurrences.filter((occ) => matchesSearch(occ, query.value) && !(upcomingOnly.value && isPast(occ, now.value))),
)
const days = computed(() => groupByDay(visible.value, props.rangeStart, props.rangeEnd))
const count = computed(() => new Set(days.value.flatMap((day) => day.entries.map((entry) => entry.occurrence))).size)

const emptyText = computed(() => {
  if (query.value.trim()) return t('agenda.noMatches', { query: query.value.trim() })
  if (upcomingOnly.value && props.occurrences.length) return t('agenda.noUpcoming', { period: period.value })
  return t('agenda.empty', { period: period.value })
})

function weekday(date: Date): string {
  return date.toLocaleDateString(locale.value, { weekday: 'short' })
}

function title(occ: Occurrence): string {
  return occ.recurrence_count === null ? occ.title : `${occ.title} (${occ.recurrence_count})`
}

/** The times of an entry: when it starts and ends that day, or that it takes the whole day. */
function times(entry: AgendaEntry): { main: string; sub?: string } {
  const occ = entry.occurrence
  if (occ.all_day || entry.span === 'middle') return { main: t('event.allDay') }
  if (entry.span === 'first') return { main: t('agenda.from', { time: formatTime(occ.start) }) }
  if (entry.span === 'last') return { main: t('agenda.until', { time: formatTime(occ.end) }) }
  const start = formatTime(occ.start)
  const end = formatTime(occ.end)
  return start === end ? { main: start } : { main: start, sub: end }
}

/** A new event starts today when the month shown has it, else on the month's first day. */
function newEventDate(): Date {
  return newEventStart(showsToday.value ? now.value : props.rangeStart, props.dayStart, now.value)
}

function isDeclined(occ: Occurrence): boolean {
  return occ.status === 'rejected' || occ.status === 'cancelled'
}

/** Where the "now" line goes in today's list: before the first event that is still to come. */
function nowIndex(day: AgendaDay): number {
  if (day.key !== todayKey.value) return -1
  const index = day.entries.findIndex(
    (entry) =>
      !entry.occurrence.all_day &&
      (entry.span === 'single' || entry.span === 'first') &&
      new Date(entry.occurrence.start) > now.value,
  )
  return index === -1 ? day.entries.length : index
}

function entryStyle(occ: Occurrence) {
  return { '--agenda-event-color': props.colorOf(occ) }
}

// Opening the list, a month with today in it, or "Today" scrolls to today (or the next day with events).
const scroller = ref<HTMLElement | null>(null)
let scrollPending = true

function scrollToToday(smooth = false) {
  const target = days.value.find((day) => day.date.getTime() >= new Date(now.value).setHours(0, 0, 0, 0))
  const element = target && scroller.value?.querySelector<HTMLElement>(`[data-day="${target.key}"]`)
  if (!scroller.value) return
  if (!element) {
    scroller.value.scrollTo({ top: showsToday.value ? scroller.value.scrollHeight : 0 })
    return
  }
  const top =
    element.getBoundingClientRect().top - scroller.value.getBoundingClientRect().top + scroller.value.scrollTop
  scroller.value.scrollTo({ top, behavior: smooth ? 'smooth' : 'auto' })
}

watch(
  () => props.rangeStart.getTime(),
  () => {
    scrollPending = true
    scroller.value?.scrollTo({ top: 0 })
  },
)

watch(
  days,
  async (list) => {
    if (!scrollPending || !list.length) return
    scrollPending = false
    await nextTick()
    if (showsToday.value) scrollToToday()
  },
  { flush: 'post', immediate: true },
)

defineExpose({ scrollToToday: () => nextTick(() => scrollToToday(true)) })

const searchInput = ref<HTMLInputElement | null>(null)

// "/" jumps to the search, as in many lists.
function onKeydown(event: KeyboardEvent) {
  const target = event.target as HTMLElement | null
  if (event.key !== '/' || event.ctrlKey || event.metaKey || event.altKey) return
  if (target?.closest('input, textarea, select, [contenteditable="true"], [role="dialog"]')) return
  event.preventDefault()
  searchInput.value?.focus()
}
window.addEventListener('keydown', onKeydown)
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="calendar-agenda flex h-full flex-col gap-2">
    <div class="flex flex-wrap items-center gap-2">
      <label class="agenda-search">
        <Search :size="16" class="shrink-0 text-[var(--app-text-muted)]" aria-hidden="true" />
        <input
          ref="searchInput"
          v-model="query"
          type="search"
          class="min-w-0 flex-1 bg-transparent! outline-none"
          :placeholder="$t('agenda.search')"
          :aria-label="$t('agenda.search')"
          @keydown.esc="query = ''"
        />
        <kbd v-if="!query" class="agenda-kbd" aria-hidden="true">/</kbd>
        <button
          v-else
          type="button"
          class="agenda-clear"
          :aria-label="$t('agenda.clearSearch')"
          @click="((query = ''), searchInput?.focus())"
        >
          <X :size="14" />
        </button>
      </label>
      <button
        type="button"
        class="agenda-toggle"
        :class="{ 'agenda-toggle-on': upcomingOnly }"
        :aria-pressed="upcomingOnly"
        @click="upcomingOnly = !upcomingOnly"
      >
        <Clock :size="15" aria-hidden="true" />
        {{ $t('agenda.upcomingOnly') }}
      </button>
      <button v-if="canCreate" type="button" class="agenda-toggle" @click="emit('create', newEventDate())">
        <Plus :size="15" aria-hidden="true" />
        {{ $t('agenda.newEvent') }}
      </button>
      <span class="ml-auto text-sm text-[var(--app-text-muted)] tabular-nums" aria-live="polite">
        {{ $t('agenda.count', count) }}
      </span>
    </div>

    <div ref="scroller" class="agenda-list min-h-0 flex-1 overflow-y-auto">
      <div v-if="!days.length" class="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
        <CalendarX :size="36" class="text-[var(--app-text-muted)] opacity-60" aria-hidden="true" />
        <p class="text-sm text-[var(--app-text-muted)]">{{ emptyText }}</p>
        <button
          v-if="query.trim() || upcomingOnly"
          type="button"
          class="agenda-toggle"
          @click="((query = ''), (upcomingOnly = false))"
        >
          {{ $t('agenda.showAll') }}
        </button>
      </div>

      <section
        v-for="day in days"
        :key="day.key"
        :data-day="day.key"
        class="agenda-day"
        :class="{ 'agenda-day-today': day.key === todayKey, 'agenda-day-past': day.key < todayKey }"
      >
        <div class="agenda-date">
          <div class="agenda-date-inner">
            <span class="agenda-weekday">{{ weekday(day.date) }}</span>
            <span class="agenda-daynumber">{{ day.date.getDate() }}</span>
          </div>
        </div>

        <ul class="agenda-entries">
          <template
            v-for="(entry, index) in day.entries"
            :key="`${entry.occurrence.event_id}-${entry.occurrence.start}`"
          >
            <li v-if="index === nowIndex(day)" class="agenda-now" aria-hidden="true">
              <span>{{ $t('agenda.now') }}</span>
            </li>
            <li>
              <button
                type="button"
                class="agenda-entry"
                :class="{
                  'agenda-entry-past': isPast(entry.occurrence, now),
                  'agenda-entry-pending': entry.occurrence.status === 'pending',
                  'agenda-entry-declined': isDeclined(entry.occurrence),
                }"
                :style="entryStyle(entry.occurrence)"
                @click="emit('open', entry.occurrence)"
              >
                <span class="agenda-time">
                  <span>{{ times(entry).main }}</span>
                  <span v-if="times(entry).sub" class="agenda-time-sub">{{ times(entry).sub }}</span>
                  <span v-if="entry.dayCount > 1" class="agenda-time-sub">
                    {{ $t('agenda.dayOf', { index: entry.dayIndex, count: entry.dayCount }) }}
                  </span>
                </span>
                <span class="agenda-bar" aria-hidden="true"></span>
                <span class="agenda-body">
                  <span class="agenda-title-row">
                    <span
                      v-if="entry.occurrence.category_color"
                      class="agenda-category-marker"
                      :style="{ backgroundColor: entry.occurrence.category_color }"
                      aria-hidden="true"
                    ></span>
                    <span class="agenda-title">{{ title(entry.occurrence) }}</span>
                    <Repeat
                      v-if="entry.occurrence.is_recurring"
                      :size="13"
                      class="shrink-0 text-[var(--app-text-muted)]"
                      :aria-label="$t('agenda.recurring')"
                    />
                    <span v-if="entry.occurrence.status === 'pending'" class="agenda-badge agenda-badge-pending">
                      {{ $t('event.pending') }}
                    </span>
                    <span v-else-if="isDeclined(entry.occurrence)" class="agenda-badge">
                      {{ $t('event.declined') }}
                    </span>
                  </span>
                  <span
                    v-if="
                      entry.occurrence.location ||
                      entry.occurrence.resource_name ||
                      entry.occurrence.category_name ||
                      calendarNameOf
                    "
                    class="agenda-meta"
                  >
                    <span v-if="entry.occurrence.location" class="agenda-meta-item">
                      <component
                        :is="
                          (entry.occurrence.location_resource_id &&
                            resourceIcon(entry.occurrence.location_resource_icon)) ||
                          MapPin
                        "
                        :size="13"
                        aria-hidden="true"
                      />
                      {{ entry.occurrence.location }}
                    </span>
                    <span v-if="entry.occurrence.resource_name" class="agenda-meta-item">
                      <component
                        :is="resourceIcon(entry.occurrence.resource_icon)"
                        v-if="resourceIcon(entry.occurrence.resource_icon)"
                        :size="13"
                        aria-hidden="true"
                      />
                      {{ entry.occurrence.resource_name }}
                    </span>
                    <span v-if="entry.occurrence.category_name" class="agenda-meta-item">
                      {{ entry.occurrence.category_name }}
                    </span>
                    <span v-if="calendarNameOf" class="agenda-meta-item agenda-calendar">
                      <span class="agenda-calendar-dot" aria-hidden="true"></span>
                      {{ calendarNameOf(entry.occurrence) }}
                    </span>
                  </span>
                </span>
              </button>
            </li>
          </template>
          <!-- Everything today is over: the line goes after the last event. -->
          <li v-if="nowIndex(day) === day.entries.length" class="agenda-now" aria-hidden="true">
            <span>{{ $t('agenda.now') }}</span>
          </li>
        </ul>
      </section>
    </div>
  </div>
</template>

<style scoped>
/* Controls in the look of the calendar toolbar (CalendarToolbar), colored by the --calendar-* variables. */
.agenda-search,
.agenda-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  border: 1px solid var(--calendar-control-border);
  border-radius: 0.625rem;
  background-color: var(--calendar-control-bg);
  box-shadow: 0 1px 3px rgb(0 0 0 / 0.12);
  font-size: 0.875rem;
  line-height: 1.25rem;
  color: var(--app-text);
}

.agenda-search {
  flex: 1 1 16rem;
  max-width: 26rem;
  padding: calc(0.3rem + 3px) 0.75rem;
  cursor: text;
}

.agenda-search:focus-within {
  outline: 2px solid var(--calendar-accent-color);
  outline-offset: 1px;
}

/* The frame shows the focus, not the field inside it (see the app's field focus style). */
.agenda-search input:focus {
  box-shadow: none;
}

/* The browser's own clear button; ours keeps the look. */
.agenda-search input::-webkit-search-cancel-button {
  display: none;
}

.agenda-kbd {
  border: 1px solid var(--calendar-control-border);
  border-radius: 0.3rem;
  padding: 0 0.35rem;
  font-size: 0.75rem;
  line-height: 1.1rem;
  color: var(--app-text-muted);
}

.agenda-clear {
  display: inline-flex;
  border-radius: 9999px;
  padding: 0.15rem;
  color: var(--app-text-muted);
}

.agenda-clear:hover {
  background-color: var(--calendar-control-hover);
  color: var(--app-text);
}

.agenda-toggle {
  padding: calc(0.3rem + 3px) 0.8rem;
  font-weight: 500;
  white-space: nowrap;
  transition:
    background-color 120ms ease,
    color 120ms ease;
}

.agenda-toggle:hover:not(.agenda-toggle-on) {
  background-color: var(--calendar-control-hover);
}

.agenda-toggle:focus-visible,
.agenda-entry:focus-visible {
  outline: 2px solid var(--calendar-accent-color);
  outline-offset: 1px;
}

.agenda-toggle-on {
  border-color: transparent;
  background-color: var(--calendar-accent-color);
  color: var(--calendar-accent-text-color);
}

/* The list sits in a frame like the month and week views. */
.agenda-list {
  border: 1px solid var(--calendar-outer-border-color);
  border-radius: 0.5rem;
  background-color: var(--app-surface);
}

.agenda-day {
  display: grid;
  grid-template-columns: 4.5rem 1fr;
  border-top: 1px solid var(--calendar-border-color);
}

.agenda-day:first-of-type {
  border-top: none;
}

.agenda-date {
  border-right: 1px solid var(--calendar-border-color);
  background-color: color-mix(in srgb, var(--calendar-default-color) 60%, var(--app-surface));
}

.agenda-day-today .agenda-date {
  background-color: color-mix(in srgb, var(--calendar-today-color) 75%, var(--app-surface));
}

/* The date stays in view while the day's events scroll past. */
.agenda-date-inner {
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.1rem;
  padding: 0.6rem 0.25rem;
}

.agenda-weekday {
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--app-text-muted);
}

.agenda-daynumber {
  display: grid;
  place-items: center;
  width: 2.1rem;
  height: 2.1rem;
  border-radius: 9999px;
  font-size: 1.15rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: var(--app-text);
}

.agenda-day-today .agenda-daynumber {
  background-color: var(--calendar-accent-color);
  color: var(--calendar-accent-text-color);
}

.agenda-day-today .agenda-weekday {
  color: var(--app-text);
}

.agenda-day-past .agenda-daynumber,
.agenda-day-past .agenda-weekday {
  opacity: 0.6;
}

.agenda-entries {
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: 0.35rem;
  min-width: 0;
}

.agenda-entry {
  display: grid;
  grid-template-columns: 5.5rem 3px 1fr;
  align-items: stretch;
  column-gap: 0.75rem;
  width: 100%;
  border-radius: 0.5rem;
  padding: 0.45rem 0.6rem;
  text-align: left;
  color: var(--app-text);
  transition: background-color 120ms ease;
}

/* A hint of the event's color on hover; the color itself only shows in the bar. */
.agenda-entry:hover {
  background-color: color-mix(in srgb, var(--agenda-event-color) 12%, transparent);
}

.agenda-time {
  display: flex;
  flex-direction: column;
  font-size: 0.85rem;
  font-weight: 600;
  line-height: 1.25rem;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.agenda-time-sub {
  font-weight: 400;
  color: var(--app-text-muted);
}

.agenda-bar {
  border-radius: 9999px;
  background-color: var(--agenda-event-color);
}

.agenda-entry-pending .agenda-bar {
  background: repeating-linear-gradient(to bottom, var(--agenda-event-color) 0 4px, transparent 4px 7px);
}

.agenda-body {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  min-width: 0;
}

.agenda-title-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  min-width: 0;
  line-height: 1.25rem;
}

.agenda-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
}

.agenda-category-marker {
  flex: 0 0 auto;
  width: 0.625rem;
  height: 0.625rem;
  border-radius: 0.125rem;
}

.agenda-badge {
  flex: 0 0 auto;
  border: 1px solid var(--app-border);
  border-radius: 9999px;
  padding: 0 0.45rem;
  font-size: 0.7rem;
  line-height: 1.1rem;
  color: var(--app-text-muted);
}

.agenda-badge-pending {
  border-style: dashed;
  border-color: var(--agenda-event-color);
}

.agenda-meta {
  display: flex;
  flex-wrap: wrap;
  column-gap: 0.9rem;
  row-gap: 0.1rem;
  font-size: 0.8rem;
  line-height: 1.1rem;
  color: var(--app-text-muted);
}

.agenda-meta-item {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  min-width: 0;
}

.agenda-calendar-dot {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 9999px;
  background-color: var(--agenda-event-color);
}

.agenda-entry-past {
  opacity: 0.55;
}

.agenda-entry-past:hover {
  opacity: 0.85;
}

.agenda-entry-declined .agenda-title {
  text-decoration: line-through;
  color: var(--app-text-muted);
}

/* Where today's past events end and its coming ones begin. */
.agenda-now {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.1rem 0.6rem;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--calendar-accent-color);
}

.agenda-now::after {
  content: '';
  flex: 1;
  height: 2px;
  border-radius: 9999px;
  background-color: var(--calendar-accent-color);
}

@media (max-width: 40rem) {
  .agenda-day {
    grid-template-columns: 3.5rem 1fr;
  }

  .agenda-entry {
    grid-template-columns: 4.25rem 3px 1fr;
    column-gap: 0.55rem;
  }
}
</style>
