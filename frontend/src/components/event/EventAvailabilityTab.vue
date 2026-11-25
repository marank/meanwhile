<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ChevronLeft, ChevronRight } from '@lucide/vue'
import * as api from '@/api'
import IconButton from '@/components/IconButton.vue'
import { errorMessage } from '@/services/errors'
import { formatDate } from '@/services/datetime'
import { loadAvailability, type AvailabilityCache } from '@/services/availability'
import { DAY_MS, startOfDay } from '@/services/days'

const props = defineProps<{
  /** The event being planned; it doesn't count as taking anyone's time. */
  eventId?: string | null
  /** The event's time as currently entered. */
  start: Date
  end: Date
  people: { id: string; name: string }[]
  /** The booked place and resource. */
  resourceIds: string[]
  /** Availability already loaded while the dialog is open. */
  cache: AvailabilityCache
}>()

const HOURS = [0, 3, 6, 9, 12, 15, 18, 21]

const { t } = useI18n()
const freeBusy = ref<api.Availability | null>(null)
const error = ref('')

/** The day shown; follows the event's start until one browses to other days. */
const day = ref(startOfDay(props.start))
watch(
  () => props.start.getTime(),
  () => (day.value = startOfDay(props.start)),
)

function moveDay(by: number) {
  const next = new Date(day.value)
  next.setDate(next.getDate() + by)
  day.value = next
}

const dayEnd = computed(() => {
  const next = new Date(day.value)
  next.setDate(next.getDate() + 1)
  return next
})

const userIds = computed(() => props.people.map((p) => p.id))

let request = 0

// Cached days show at once; otherwise the previous day stays visible until the new one is there.
watch(
  () => [day.value.getTime(), userIds.value.join(','), props.resourceIds.join(',')] as const,
  async () => {
    error.value = ''
    if (!userIds.value.length && !props.resourceIds.length) {
      freeBusy.value = { users: [], resources: [] }
      return
    }
    const current = ++request
    const entry = loadAvailability(props.cache, day.value, userIds.value, props.resourceIds, props.eventId)
    if (entry.value) {
      freeBusy.value = entry.value
      return
    }
    try {
      const value = await entry.promise
      if (current === request) freeBusy.value = value
    } catch (e) {
      if (current === request) error.value = errorMessage(e, t('app.loadFailed'))
    }
  },
  { immediate: true },
)

/** One row per person (in the given order) and the resource. */
const rows = computed(() => {
  const byId = new Map((freeBusy.value?.users ?? []).map((u) => [u.id, u]))
  const people = props.people
    .map((p) => ({ name: p.name, busy: byId.get(p.id)?.busy }))
    .filter((row): row is { name: string; busy: api.BusyPeriod[] } => !!row.busy)
  return [...people, ...(freeBusy.value?.resources ?? []).map((r) => ({ name: r.name, busy: r.busy }))]
})

/** Left offset and width in % of the shown day, or null if outside it. */
function placement(start: Date, end: Date) {
  const from = Math.max(start.getTime(), day.value.getTime())
  const to = Math.min(end.getTime(), dayEnd.value.getTime())
  if (to <= from) return null
  const length = dayEnd.value.getTime() - day.value.getTime()
  return {
    left: `${((from - day.value.getTime()) / length) * 100}%`,
    width: `${Math.max(((to - from) / length) * 100, 0.4)}%`,
  }
}

const slot = computed(() => placement(props.start, props.end))

const conflicts = computed(() =>
  rows.value
    .filter((row) =>
      row.busy.some((p) => !p.tentative && new Date(p.start) < props.end && new Date(p.end) > props.start),
    )
    .map((row) => row.name),
)

const dayLength = DAY_MS

type PeriodKind = 'busy' | 'tentative' | 'outOfOffice'
const periodClasses: Record<PeriodKind, string> = {
  busy: 'bg-red-500/70',
  tentative: 'availability-tentative',
  outOfOffice: 'bg-purple-600/70',
}
function periodKind(period: api.BusyPeriod): PeriodKind {
  if (period.out_of_office) return 'outOfOffice'
  return period.tentative ? 'tentative' : 'busy'
}
function periodClass(period: api.BusyPeriod): string {
  return periodClasses[periodKind(period)]
}
</script>

<template>
  <div class="space-y-3">
    <div class="flex items-center justify-between gap-2">
      <IconButton :label="$t('availability.previousDay')" @click="moveDay(-1)">
        <ChevronLeft :size="18" />
      </IconButton>
      <p class="text-sm font-medium text-gray-700">{{ formatDate(day) }}</p>
      <IconButton :label="$t('availability.nextDay')" @click="moveDay(1)">
        <ChevronRight :size="18" />
      </IconButton>
    </div>

    <p v-if="error" class="text-sm text-red-600" role="alert">{{ error }}</p>
    <p v-else-if="!rows.length && freeBusy" class="text-sm text-gray-500">{{ $t('availability.noOne') }}</p>

    <div v-if="rows.length" class="grid grid-cols-[minmax(5rem,9rem)_1fr] items-center gap-x-3 gap-y-1.5">
      <span></span>
      <div class="relative h-4 text-[10px] text-gray-500" aria-hidden="true">
        <span
          v-for="hour in HOURS"
          :key="hour"
          class="absolute -translate-x-1/2 first:translate-x-0"
          :style="{ left: `${(hour * 3600000 * 100) / dayLength}%` }"
          >{{ String(hour).padStart(2, '0') }}</span
        >
      </div>
      <template v-for="row in rows" :key="row.name">
        <span class="truncate text-sm text-gray-700" :title="row.name">{{ row.name }}</span>
        <div
          class="relative h-6 overflow-hidden rounded border border-line bg-surface-muted"
          role="img"
          :aria-label="`${row.name}: ${row.busy.length ? row.busy.map((p) => `${new Date(p.start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}–${new Date(p.end).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`).join(', ') : '—'}`"
        >
          <div
            v-if="slot"
            class="absolute inset-y-0 border-x-2 border-blue-600 bg-blue-500/15"
            :style="slot"
            :title="$t('availability.thisEvent')"
          ></div>
          <template v-for="(period, index) in row.busy" :key="index">
            <div
              v-if="placement(new Date(period.start), new Date(period.end))"
              class="absolute inset-y-1 rounded-sm"
              :class="periodClass(period)"
              :data-kind="periodKind(period)"
              :style="placement(new Date(period.start), new Date(period.end))!"
              :title="$t(`availability.${periodKind(period)}`)"
            ></div>
          </template>
        </div>
      </template>
    </div>

    <p v-if="rows.length && conflicts.length" class="text-sm text-red-600" role="status">
      {{ $t('availability.conflicts', { names: conflicts.join(', ') }) }}
    </p>
    <p v-else-if="rows.length" class="text-sm text-green-700 dark:text-green-400" role="status">
      {{ $t('availability.allFree') }}
    </p>

    <div class="flex flex-wrap gap-4 text-xs text-gray-500">
      <span class="inline-flex items-center gap-1.5"
        ><span class="h-3 w-3 rounded-sm bg-red-500/70"></span>{{ $t('availability.busy') }}</span
      >
      <span class="inline-flex items-center gap-1.5"
        ><span class="availability-tentative h-3 w-3 rounded-sm"></span>{{ $t('availability.tentative') }}</span
      >
      <span class="inline-flex items-center gap-1.5"
        ><span :class="periodClasses.outOfOffice" class="h-3 w-3 rounded-sm"></span
        >{{ $t('availability.outOfOffice') }}</span
      >
      <span class="inline-flex items-center gap-1.5"
        ><span class="h-3 w-3 border-x-2 border-blue-600 bg-blue-500/15"></span>{{ $t('availability.thisEvent') }}</span
      >
    </div>
    <p class="text-xs text-gray-500">{{ $t('availability.hint') }}</p>
  </div>
</template>

<style scoped>
.availability-tentative {
  background-image: repeating-linear-gradient(135deg, rgb(245 158 11 / 0.75) 0 4px, rgb(245 158 11 / 0.3) 4px 8px);
}
</style>
