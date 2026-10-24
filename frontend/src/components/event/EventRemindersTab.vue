<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Plus, Trash2 } from 'lucide-vue-next'
import AppSelect from '@/components/AppSelect.vue'
import IconButton from '@/components/IconButton.vue'
import {
  fromAllDayReminder,
  fromTimedReminder,
  isValidReminder,
  MAX_MINUTES_BEFORE,
  MAX_REMINDERS,
  reminderChoices,
  reminderLabel,
  toAllDayReminder,
  toTimedReminder,
  type ReminderUnit,
} from '@/services/reminders'

const props = defineProps<{
  /** All-day events are reminded of at a time of day, timed ones some time before their start. */
  allDay: boolean
}>()

/** The reminders in minutes before the start, as far as they are valid; sorted, without duplicates. */
const minutes = defineModel<number[]>({ required: true })
/** Whether every row holds a valid reminder. */
const valid = defineModel<boolean>('valid', { default: true })

const { t } = useI18n()

interface Row {
  key: number
  amount: number
  unit: ReminderUnit
  days: number
  time: string
}

let nextKey = 0
const rows = ref<Row[]>([])
let lastEmitted = ''

function rowFor(value: number): Row {
  return { key: nextKey++, ...toTimedReminder(value), ...toAllDayReminder(value) }
}

function rowMinutes(row: Row): number {
  return props.allDay
    ? fromAllDayReminder({ days: row.days, time: row.time })
    : fromTimedReminder({ amount: row.amount, unit: row.unit })
}

function rebuild(values: number[]) {
  rows.value = values.map(rowFor)
}

// Values from outside (loaded from the server) replace the rows; the rows' own changes don't come back here.
watch(
  minutes,
  (values) => {
    if (values.join(',') !== lastEmitted) rebuild(values)
  },
  { immediate: true },
)

// Switching between all-day and timed shows the same reminders the other way.
watch(
  () => props.allDay,
  () => rebuild(minutes.value),
)

const rowStates = computed(() => {
  const seen = new Set<number>()
  return rows.value.map((row) => {
    const value = rowMinutes(row)
    const ok = isValidReminder(value)
    const duplicate = ok && seen.has(value)
    if (ok) seen.add(value)
    return { value, ok, duplicate }
  })
})

watch(
  rowStates,
  (states) => {
    const values = [...new Set(states.filter((s) => s.ok).map((s) => s.value))].sort((a, b) => a - b)
    lastEmitted = values.join(',')
    if (values.join(',') !== minutes.value.join(',')) minutes.value = values
    valid.value = states.every((s) => s.ok)
  },
  { deep: true },
)

/** Unit names in the number of the row's amount ("1 Tag", "2 Tage"). */
function unitOptions(amount: number) {
  const count = Number.isFinite(amount) ? amount : 2
  return (['minutes', 'hours', 'days', 'weeks'] as const).map((value) => ({
    value,
    label: t(`reminders.unit.${value}`, count),
  }))
}

/** No more rows than the server keeps reminders. */
const full = computed(() => rows.value.length >= MAX_REMINDERS)

/** Common choices not set yet. */
const quickChoices = computed(() => reminderChoices(props.allDay).filter((m) => !minutes.value.includes(m)))

function add(value?: number) {
  // Without a choice: the first common one that isn't set yet, else a copy of the last row.
  const next = value ?? quickChoices.value[0] ?? minutes.value.at(-1) ?? 15
  rows.value.push(rowFor(next))
}

function remove(index: number) {
  rows.value.splice(index, 1)
}

const maxWeeks = MAX_MINUTES_BEFORE / (7 * 24 * 60)
</script>

<template>
  <div class="space-y-6">
    <p class="text-sm text-gray-600">{{ $t('reminders.hint') }}</p>

    <!-- The add button belongs to the list; the quick choices below are a block of their own. -->
    <div class="space-y-3">
      <ul v-if="rows.length" class="divide-y divide-line rounded-lg border border-line">
        <li v-for="(row, index) in rows" :key="row.key" class="space-y-1 px-3 py-2">
          <!-- One line on phones too: where it gets narrow, only the text wraps. -->
          <div class="flex items-center gap-2 text-sm">
            <template v-if="allDay">
              <input
                v-model.number="row.days"
                type="number"
                min="0"
                :max="maxWeeks * 7"
                :aria-label="$t('reminders.daysLabel')"
                :aria-invalid="!rowStates[index]?.ok"
                class="w-16 rounded-lg border px-2 py-1.5"
              />
              <span class="min-w-0 text-gray-700">{{ $t('reminders.daysBeforeAtInput') }}</span>
              <input
                v-model="row.time"
                type="time"
                :aria-label="$t('event.time')"
                :aria-invalid="!rowStates[index]?.ok"
                class="rounded-lg border px-2 py-1.5"
              />
            </template>
            <template v-else>
              <input
                v-model.number="row.amount"
                type="number"
                min="0"
                :aria-label="$t('reminders.amountLabel')"
                :aria-invalid="!rowStates[index]?.ok"
                class="w-16 rounded-lg border px-2 py-1.5"
              />
              <!-- A fixed width keeps "before" in one column, whichever unit each row has. -->
              <AppSelect
                v-model="row.unit"
                :options="unitOptions(row.amount)"
                :label="$t('reminders.unitLabel')"
                size="sm"
                class="w-32"
              />
              <span class="text-gray-700">{{ $t('reminders.before') }}</span>
            </template>
            <IconButton :label="$t('reminders.remove')" tone="danger" class="ml-auto shrink-0" @click="remove(index)">
              <Trash2 :size="16" />
            </IconButton>
          </div>
          <p v-if="!rowStates[index]?.ok" class="text-xs text-red-600" role="alert">
            {{ $t(allDay ? 'reminders.invalidAllDay' : 'reminders.invalid', { weeks: maxWeeks }) }}
          </p>
          <p v-else-if="rowStates[index]?.duplicate" class="text-xs text-amber-600">{{ $t('reminders.duplicate') }}</p>
          <p v-else-if="allDay" class="text-xs text-gray-500">{{ reminderLabel(rowStates[index]!.value, true) }}</p>
        </li>
      </ul>
      <p v-else class="text-sm text-gray-500">{{ $t('reminders.none') }}</p>

      <button
        type="button"
        :disabled="full"
        class="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-sm hover:bg-hover disabled:opacity-50"
        @click="add()"
      >
        <Plus :size="16" />
        {{ $t('reminders.add') }}
      </button>
    </div>

    <div v-if="quickChoices.length && !full">
      <p class="mb-2 text-xs text-gray-500">{{ $t('reminders.quick') }}</p>
      <div class="flex flex-wrap gap-2">
        <button
          v-for="choice in quickChoices"
          :key="choice"
          type="button"
          class="rounded-full border border-line px-3 py-1 text-xs hover:bg-hover"
          @click="add(choice)"
        >
          {{ reminderLabel(choice, allDay) }}
        </button>
      </div>
    </div>
  </div>
</template>
