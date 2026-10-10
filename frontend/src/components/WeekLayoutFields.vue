<script setup lang="ts">
import { computed } from 'vue'
import AppSelect from '@/components/AppSelect.vue'
import SettingsToggle from '@/components/SettingsToggle.vue'
import { weekdays, weekdaysFrom } from '@/services/weekdays'

withDefaults(defineProps<{ disabled?: boolean }>(), { disabled: false })

const firstWeekday = defineModel<number>('firstWeekday', { required: true })
const weekendDays = defineModel<number[]>('weekendDays', { required: true })
const showWeekends = defineModel<boolean>('showWeekends', { required: true })
const showWeekNumbers = defineModel<boolean>('showWeekNumbers', { required: true })

const orderedWeekdays = computed(() => weekdaysFrom(firstWeekday.value))

function toggleWeekendDay(day: number) {
  weekendDays.value = weekendDays.value.includes(day)
    ? weekendDays.value.filter((value) => value !== day)
    : [...weekendDays.value, day].sort((a, b) => a - b)
}
</script>

<template>
  <div class="space-y-4">
    <div class="grid gap-3 sm:grid-cols-2">
      <label class="block">
        <span class="mb-1 block text-sm font-medium text-gray-800">{{ $t('app.firstWeekday') }}</span>
        <AppSelect
          v-model="firstWeekday"
          :options="weekdays.map((day) => ({ value: day.value, label: $t(`event.${day.key}`) }))"
          :disabled="disabled"
        />
      </label>
    </div>
    <div>
      <span class="mb-2 block text-sm font-medium text-gray-800">{{ $t('app.weekendDays') }}</span>
      <div class="flex flex-wrap gap-2">
        <button
          v-for="day in orderedWeekdays"
          :key="day.value"
          type="button"
          :disabled="disabled"
          class="rounded-full border px-3 py-1.5 text-sm transition-colors disabled:opacity-60"
          :class="
            weekendDays.includes(day.value)
              ? 'border-blue-600 bg-blue-600 text-white'
              : 'border-line text-gray-600 hover:bg-hover'
          "
          @click="toggleWeekendDay(day.value)"
        >
          {{ $t(`event.${day.key}`) }}
        </button>
      </div>
      <p class="mt-1 text-xs text-gray-500">{{ $t('app.weekendDaysHelp') }}</p>
    </div>
    <div class="grid gap-3 sm:grid-cols-2">
      <SettingsToggle
        v-model="showWeekends"
        :disabled="disabled"
        :title="$t('app.showWeekends')"
        :description="$t('app.showWeekendsHelp')"
      />
      <SettingsToggle
        v-model="showWeekNumbers"
        :disabled="disabled"
        :title="$t('app.showWeekNumbers')"
        :description="$t('app.showWeekNumbersHelp')"
      />
    </div>
  </div>
</template>
