<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import * as api from '@/api'
import type { AppSettings } from '@/api'
import SettingsPanel from '@/components/SettingsPanel.vue'
import WeekLayoutFields from '@/components/WeekLayoutFields.vue'
import ImageUploadField from './ImageUploadField.vue'
import { useAction } from '@/composables/useAction'
import { useLoader } from '@/composables/useLoader'
import { useSettingsStore } from '@/stores/settings'

const { t } = useI18n()
const settingsStore = useSettingsStore()
const { busy, run } = useAction()
// Everything but the id, all of it sent back on saving.
const form = ref<Omit<AppSettings, 'id'> | null>(null)

const { loading } = useLoader(async () => {
  const settings = await api.getAdminSettings()
  form.value = {
    app_name: settings.app_name,
    logo_url: settings.logo_url,
    favicon_url: settings.favicon_url,
    default_first_weekday: settings.default_first_weekday,
    default_show_weekends: settings.default_show_weekends,
    default_weekend_days: [...settings.default_weekend_days],
    default_show_week_numbers: settings.default_show_week_numbers,
  }
})

function save() {
  const value = form.value
  if (!value) return
  return run(() => settingsStore.update(value), { success: t('app.settingsSaved'), failure: t('app.saveFailed') })
}
</script>

<template>
  <SettingsPanel :title="$t('app.generalSettings')" :description="$t('app.adminGeneralDescription')" :loading="loading">
    <div v-if="form" class="space-y-6">
      <label class="block">
        <span class="mb-1 block text-sm font-medium text-gray-800">{{ $t('app.appName') }}</span>
        <input v-model="form.app_name" class="w-full rounded-lg border px-3 py-2" />
      </label>

      <ImageUploadField
        v-model="form.logo_url"
        :label="$t('app.logo')"
        default-image="/logo.svg"
        :default-label="$t('app.defaultLogo')"
        :remove-label="$t('app.removeLogo')"
      />
      <ImageUploadField
        v-model="form.favicon_url"
        size="sm"
        :label="$t('app.favicon')"
        default-image="/favicon.svg"
        :default-label="$t('app.defaultFavicon')"
        :remove-label="$t('app.removeFavicon')"
      />

      <section class="space-y-4 border-t border-line pt-4">
        <div>
          <h3 class="text-sm font-semibold text-gray-700">{{ $t('app.calendarDisplay') }}</h3>
          <p class="text-xs text-gray-500">{{ $t('app.defaultCalendarSettingsHelp') }}</p>
        </div>
        <WeekLayoutFields
          v-model:first-weekday="form.default_first_weekday"
          v-model:weekend-days="form.default_weekend_days"
          v-model:show-weekends="form.default_show_weekends"
          v-model:show-week-numbers="form.default_show_week_numbers"
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
