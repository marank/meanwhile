<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Calendar } from '@/api'
import SettingsPanel from '@/components/SettingsPanel.vue'
import SettingsToggle from '@/components/SettingsToggle.vue'
import WeekLayoutFields from '@/components/WeekLayoutFields.vue'
import { useAction } from '@/composables/useAction'
import { changedValues } from '@/services/changes'
import { pickColorFields, type CalendarColorFields } from '@/services/calendarColors'
import CalendarColorSettings from './CalendarColorSettings.vue'
import { useCalendarStore } from '@/stores/calendars'

const props = defineProps<{
  calendar: Calendar
  canManage: boolean
}>()

const emit = defineEmits<{
  updated: [calendar: Calendar]
}>()

const { t } = useI18n()
const calendarStore = useCalendarStore()
const { busy, run } = useAction()

const colorForm = ref<CalendarColorFields>(pickColorFields(props.calendar))
const form = ref({
  force_all_day: props.calendar.force_all_day,
  first_weekday: props.calendar.first_weekday,
  show_weekends: props.calendar.show_weekends,
  weekend_days: [...props.calendar.weekend_days],
  show_week_numbers: props.calendar.show_week_numbers,
})

function save() {
  const data = changedValues<Calendar>({ ...colorForm.value, ...form.value }, props.calendar)
  return run(
    async () => {
      if (Object.keys(data).length) emit('updated', await calendarStore.updateCalendar(props.calendar.id, data))
    },
    { success: t('app.calendarSettingsSaved'), failure: t('app.saveFailed') },
  )
}
</script>

<template>
  <SettingsPanel :title="$t('app.calendarBehavior')" :description="$t('app.calendarGeneralDescription')">
    <div class="space-y-6">
      <section class="space-y-3">
        <h3 class="text-sm font-semibold text-gray-800">{{ $t('app.calendarAppearance') }}</h3>
        <CalendarColorSettings v-model="colorForm" :disabled="!canManage" />
      </section>

      <section class="space-y-4 border-t border-line pt-6">
        <h3 class="text-sm font-semibold text-gray-800">{{ $t('app.calendarDisplay') }}</h3>
        <WeekLayoutFields
          v-model:first-weekday="form.first_weekday"
          v-model:weekend-days="form.weekend_days"
          v-model:show-weekends="form.show_weekends"
          v-model:show-week-numbers="form.show_week_numbers"
          :disabled="!canManage"
        />
      </section>

      <section class="space-y-4 border-t border-line pt-6">
        <h3 class="text-sm font-semibold text-gray-800">{{ $t('app.eventBehavior') }}</h3>
        <SettingsToggle
          v-model="form.force_all_day"
          :disabled="!canManage"
          :title="$t('app.forceAllDay')"
          :description="$t('app.forceAllDayHelp')"
        />
      </section>
    </div>
    <template #footer>
      <button
        type="button"
        :disabled="!canManage || busy"
        class="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
        @click="save"
      >
        {{ $t('app.save') }}
      </button>
    </template>
  </SettingsPanel>
</template>
