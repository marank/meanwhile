<script setup lang="ts">
import { computed, ref } from 'vue'
import { Translation as I18nT, useI18n } from 'vue-i18n'
import AppSelect from '@/components/AppSelect.vue'
import NumberListInput from '@/components/NumberListInput.vue'
import SegmentedControl from '@/components/SegmentedControl.vue'
import { formatDayMonth, weekdayName } from '@/services/datetime'
import {
  defaultRecurrenceRule,
  matchingPreset,
  presetRule,
  recurrenceDefaults,
  recurrencePresets,
  type RecurrenceDayMode,
  type RecurrenceEnd,
  type RecurrenceFrequency,
  type RecurrencePreset,
  type RecurrenceRule,
} from '@/services/rrule'

type Choice = 'none' | 'keep' | 'custom' | RecurrencePreset

const props = defineProps<{
  /** Start date of the event (YYYY-MM-DD); the presets are based on it. */
  start: string
}>()

// The parent owns the rule object; the custom editor changes its fields in place.
const rule = defineModel<RecurrenceRule | null>('rule', { required: true })
/** A rule from another client that the editor can't show; kept unless another choice is made. */
const foreign = defineModel<string | null>('foreign', { required: true })
const showCount = defineModel<boolean>('showCount', { required: true })

const { t } = useI18n()

const WEEK = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']
const FREQUENCIES: RecurrenceFrequency[] = ['DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY']
const ORDINAL_KEYS: Record<number, string> = { 1: 'first', 2: 'second', 3: 'third', 4: 'fourth', [-1]: 'last' }

const startDate = computed(() => new Date(`${props.start}T00:00:00`))
const defaults = computed(() => recurrenceDefaults(startDate.value))
// Opened explicitly, the custom editor stays open even while the rule matches a preset.
const customOpen = ref(false)

const choice = computed<Choice>(() => {
  if (foreign.value) return 'keep'
  if (!rule.value) return 'none'
  if (customOpen.value) return 'custom'
  return matchingPreset(rule.value, defaults.value) ?? 'custom'
})

const choices = computed(() => {
  const { weekday, monthDay, ordinal } = defaults.value
  const presetLabels: Record<RecurrencePreset, string> = {
    daily: t('recurrence.daily'),
    weekdays: t('recurrence.weekdays'),
    weekly: t('recurrence.weekly', { weekday: weekdayName(weekday) }),
    biweekly: t('recurrence.biweekly', { weekday: weekdayName(weekday) }),
    monthlyDate: t('recurrence.monthlyDate', { day: monthDay }),
    monthlyWeekday: t('recurrence.monthlyWeekday', {
      ordinal: t(`recurrence.ordinal.${ORDINAL_KEYS[ordinal]}`),
      weekday: weekdayName(weekday),
    }),
    yearly: t('recurrence.yearly', { date: formatDayMonth(startDate.value) }),
  }
  return [
    ...(foreign.value ? [{ value: 'keep' as const, label: t('recurrence.keep') }] : []),
    { value: 'none' as const, label: t('recurrence.none') },
    ...recurrencePresets.map((preset) => ({ value: preset, label: presetLabels[preset] })),
    { value: 'custom' as const, label: t('recurrence.custom') },
  ]
})

function choose(value: Choice) {
  if (value === 'keep') return
  foreign.value = null
  customOpen.value = value === 'custom'
  if (value === 'none') {
    rule.value = null
  } else if (value === 'custom') {
    rule.value ??= defaultRecurrenceRule(defaults.value)
  } else {
    // Switching the pattern keeps how the series ends.
    const { end, until, count } = rule.value ?? defaultRecurrenceRule(defaults.value)
    rule.value = { ...presetRule(value, defaults.value), end, until, count }
  }
}

/** Toggles a value in a list, but never empties it: a rule needs at least one day or month. */
function toggle<T>(list: T[], value: T): T[] {
  if (!list.includes(value)) return [...list, value]
  return list.length > 1 ? list.filter((item) => item !== value) : list
}

function toggleClass(active: boolean): string {
  return active ? 'border-blue-600 bg-blue-600 text-white' : 'border-line text-gray-600 hover:bg-hover'
}

const dayModes = computed(() => [
  { value: 'date' as RecurrenceDayMode, label: t('recurrence.byDate') },
  { value: 'weekday' as RecurrenceDayMode, label: t('recurrence.byWeekday') },
])

const endings = computed(() => [
  { value: 'never' as RecurrenceEnd, label: t('recurrence.never') },
  { value: 'until' as RecurrenceEnd, label: t('recurrence.onDate') },
  { value: 'count' as RecurrenceEnd, label: t('recurrence.afterCount') },
])
</script>

<template>
  <div class="space-y-4">
    <label class="block">
      <span class="mb-1 block text-sm font-medium text-gray-700">{{ $t('recurrence.repeat') }}</span>
      <AppSelect :model-value="choice" :options="choices" @update:model-value="choose" />
    </label>

    <template v-if="rule">
      <div v-if="choice === 'custom'" class="space-y-3 rounded-lg border border-line p-3 text-sm">
        <div class="flex items-center gap-2">
          <span class="text-gray-700">{{ $t('recurrence.every') }}</span>
          <input
            v-model.number="rule.interval"
            type="number"
            min="1"
            :aria-label="$t('recurrence.every')"
            class="w-16 rounded-lg border px-2 py-1.5"
          />
          <AppSelect
            v-model="rule.frequency"
            :options="
              FREQUENCIES.map((frequency) => ({
                value: frequency,
                label: $t(`recurrence.unit.${frequency}`, rule!.interval || 1),
              }))
            "
            size="sm"
            :label="$t('recurrence.repeat')"
            class="flex-1"
          />
        </div>

        <div v-if="rule.frequency === 'WEEKLY'" class="flex items-center gap-2">
          <span class="text-gray-700">{{ $t('recurrence.onWeekdays') }}</span>
          <div role="group" :aria-label="$t('recurrence.weekdaysLabel')" class="flex flex-1 gap-1">
            <button
              v-for="day in WEEK"
              :key="day"
              type="button"
              :aria-pressed="rule.weekdays.includes(day)"
              :title="weekdayName(day)"
              class="h-8 flex-1 rounded-md border text-xs font-semibold transition-colors"
              :class="toggleClass(rule.weekdays.includes(day))"
              @click="rule.weekdays = toggle(rule.weekdays, day)"
            >
              {{ weekdayName(day, 'short') }}
            </button>
          </div>
        </div>

        <template v-if="rule.frequency === 'MONTHLY' || rule.frequency === 'YEARLY'">
          <I18nT
            v-if="rule.frequency === 'YEARLY'"
            keypath="recurrence.inMonths"
            scope="global"
            tag="div"
            class="leading-9 text-gray-700"
          >
            <template #months>
              <NumberListInput
                v-model="rule.months"
                :min="1"
                :max="12"
                placeholder="3, 10"
                :label="$t('recurrence.monthsLabel')"
              />
            </template>
          </I18nT>

          <SegmentedControl v-model="rule.dayMode" :label="$t('recurrence.dayMode')" :options="dayModes" />

          <I18nT
            v-if="rule.dayMode === 'date'"
            keypath="recurrence.onDays"
            scope="global"
            tag="div"
            class="leading-9 text-gray-700"
          >
            <template #days>
              <NumberListInput
                v-model="rule.monthDays"
                :min="1"
                :max="31"
                allow-last
                placeholder="1, 15, +"
                :label="$t('recurrence.monthDaysLabel')"
              />
            </template>
          </I18nT>
          <I18nT v-else keypath="recurrence.onPositions" scope="global" tag="div" class="leading-9 text-gray-700">
            <template #positions>
              <NumberListInput
                v-model="rule.ordinals"
                :min="1"
                :max="5"
                allow-last
                placeholder="1, 3"
                :label="$t('recurrence.ordinalsLabel')"
                class="!w-20"
              />
            </template>
            <template #weekday>
              <AppSelect
                v-model="rule.ordinalWeekday"
                :options="WEEK.map((day) => ({ value: day, label: weekdayName(day) }))"
                size="sm"
                :label="$t('recurrence.weekdaysLabel')"
                class="inline-block align-middle leading-normal"
              />
            </template>
          </I18nT>
          <p class="text-xs text-gray-500">{{ $t('recurrence.listHint') }}</p>
        </template>
      </div>

      <div class="flex flex-wrap items-center gap-2 text-sm">
        <span class="font-medium text-gray-700">{{ $t('recurrence.ends') }}</span>
        <SegmentedControl v-model="rule.end" :label="$t('recurrence.ends')" :options="endings" />
        <input
          v-if="rule.end === 'until'"
          v-model="rule.until"
          type="date"
          :min="start"
          :aria-label="$t('recurrence.onDate')"
          class="rounded-lg border px-3 py-1.5"
        />
        <label v-else-if="rule.end === 'count'" class="flex items-center gap-2">
          <input
            v-model.number="rule.count"
            type="number"
            min="1"
            :aria-label="$t('recurrence.afterCount')"
            class="w-16 rounded-lg border px-2 py-1.5"
          />
          {{ $t('recurrence.occurrences', rule.count || 1) }}
        </label>
      </div>

      <label class="flex cursor-pointer items-center gap-2 text-sm" :title="$t('event.showRecurrenceCountHelp')">
        <input v-model="showCount" type="checkbox" />
        <span class="text-gray-700">{{ $t('event.showRecurrenceCount') }}</span>
      </label>
    </template>
  </div>
</template>
