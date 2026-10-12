<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { OverviewSettings } from '@/api'
import CalendarColorSettings from '@/components/calendar-settings/CalendarColorSettings.vue'
import SettingsPanel from '@/components/SettingsPanel.vue'
import SettingsToggle from '@/components/SettingsToggle.vue'
import WeekLayoutFields from '@/components/WeekLayoutFields.vue'
import { useAction } from '@/composables/useAction'
import { useLoader } from '@/composables/useLoader'
import { changedValues } from '@/services/changes'
import { pickColorFields, type CalendarColorFields } from '@/services/calendarColors'
import { useOverviewStore } from '@/stores/overview'

const { t } = useI18n()
const overview = useOverviewStore()
const { busy, run } = useAction()

const colorForm = ref<CalendarColorFields | null>(null)
const form = ref<Pick<
  OverviewSettings,
  'first_weekday' | 'show_weekends' | 'weekend_days' | 'show_week_numbers' | 'use_calendar_colors'
> | null>(null)

const { loading } = useLoader(async () => {
  await overview.load()
  const settings = overview.settings!
  colorForm.value = pickColorFields(settings)
  form.value = {
    first_weekday: settings.first_weekday,
    show_weekends: settings.show_weekends,
    weekend_days: [...settings.weekend_days],
    show_week_numbers: settings.show_week_numbers,
    use_calendar_colors: settings.use_calendar_colors,
  }
})

function save() {
  if (!colorForm.value || !form.value) return
  const data = changedValues<OverviewSettings>({ ...colorForm.value, ...form.value }, overview.settings!)
  return run(() => (Object.keys(data).length ? overview.update(data) : Promise.resolve()), {
    success: t('app.overviewSettingsSaved'),
    failure: t('app.saveFailed'),
  })
}
</script>

<template>
  <SettingsPanel :title="$t('app.overview')" :description="$t('app.overviewSettingsDescription')" :loading="loading">
    <div v-if="form && colorForm" class="space-y-6">
      <section class="space-y-3">
        <h3 class="text-sm font-semibold text-gray-800">{{ $t('app.calendarAppearance') }}</h3>
        <CalendarColorSettings v-model="colorForm" />
        <SettingsToggle
          v-model="form.use_calendar_colors"
          :title="$t('app.useCalendarColors')"
          :description="$t('app.useCalendarColorsHelp')"
        />
      </section>

      <section class="space-y-4 border-t border-line pt-6">
        <h3 class="text-sm font-semibold text-gray-800">{{ $t('app.calendarDisplay') }}</h3>
        <WeekLayoutFields
          v-model:first-weekday="form.first_weekday"
          v-model:weekend-days="form.weekend_days"
          v-model:show-weekends="form.show_weekends"
          v-model:show-week-numbers="form.show_week_numbers"
        />
      </section>
    </div>
    <template #footer>
      <button
        type="button"
        :disabled="busy || !form"
        class="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
        @click="save"
      >
        {{ $t('app.save') }}
      </button>
    </template>
  </SettingsPanel>
</template>
