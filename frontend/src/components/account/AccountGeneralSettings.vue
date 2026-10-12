<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { User } from '@/api'
import AppSelect, { type SelectOption } from '@/components/AppSelect.vue'
import SettingsPanel from '@/components/SettingsPanel.vue'
import { useAction } from '@/composables/useAction'
import { setLocale, type Locale } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore, type ThemePreference } from '@/stores/theme'

const { t, locale } = useI18n()
const auth = useAuthStore()
const theme = useThemeStore()
const { busy, run } = useAction()

const languages: Array<{ value: Locale; label: string }> = [
  { value: 'en', label: 'English' },
  { value: 'de', label: 'Deutsch' },
]
const themeOptions = computed<SelectOption<ThemePreference>[]>(() => [
  { value: 'system', label: t('app.themeSystem') },
  { value: 'light', label: t('app.themeLight') },
  { value: 'dark', label: t('app.themeDark') },
])
const timeFormats = computed<SelectOption<User['time_format']>[]>(() => [
  { value: 'auto', label: t('app.formatAuto') },
  { value: '24h', label: t('app.format24h') },
  { value: '12h', label: t('app.format12h') },
])
const dateFormats = computed<SelectOption<User['date_format']>[]>(() => [
  { value: 'auto', label: t('app.formatAuto') },
  { value: 'dmy', label: '31.12.2026' },
  { value: 'mdy', label: '12/31/2026' },
  { value: 'ymd', label: '2026-12-31' },
])

const form = ref({
  displayName: auth.user?.display_name ?? '',
  language: locale.value as Locale,
  theme: theme.preference,
  timeFormat: auth.user?.time_format ?? ('auto' as User['time_format']),
  dateFormat: auth.user?.date_format ?? ('auto' as User['date_format']),
})

// Name, formats and language belong to the account (emails are written in its language);
// the color scheme is kept in this browser.
function save() {
  const value = form.value
  return run(
    async () => {
      await auth.updateProfile({
        display_name: value.displayName,
        time_format: value.timeFormat,
        date_format: value.dateFormat,
        language: value.language,
      })
      setLocale(value.language)
      theme.setPreference(value.theme)
    },
    // Evaluated after saving, so the message is already in the newly chosen language.
    { success: () => t('app.settingsSaved'), failure: t('app.saveFailed') },
  )
}
</script>

<template>
  <SettingsPanel :title="$t('app.general')" :description="$t('app.accountGeneralDescription')">
    <div class="space-y-6">
      <section class="space-y-3">
        <h3 class="text-sm font-semibold text-gray-800">{{ $t('app.profile') }}</h3>
        <div class="grid gap-5 sm:grid-cols-2">
          <label class="block">
            <span class="mb-1 block text-sm font-medium text-gray-700">{{ $t('auth.displayName') }}</span>
            <input v-model="form.displayName" class="w-full rounded-lg border border-line px-3 py-2" />
          </label>
        </div>
      </section>

      <section class="space-y-3 border-t border-line pt-6">
        <h3 class="text-sm font-semibold text-gray-800">{{ $t('app.appearance') }}</h3>
        <div class="grid gap-5 sm:grid-cols-2">
          <label class="block">
            <span class="mb-1 block text-sm font-medium text-gray-700">{{ $t('app.language') }}</span>
            <AppSelect v-model="form.language" :options="languages" />
          </label>
          <label class="block">
            <span class="mb-1 block text-sm font-medium text-gray-700">{{ $t('app.theme') }}</span>
            <AppSelect v-model="form.theme" :options="themeOptions" />
          </label>
        </div>
      </section>

      <section class="space-y-3 border-t border-line pt-6">
        <h3 class="text-sm font-semibold text-gray-800">{{ $t('app.dateTime') }}</h3>
        <div class="grid gap-5 sm:grid-cols-2">
          <label class="block">
            <span class="mb-1 block text-sm font-medium text-gray-700">{{ $t('app.timeFormat') }}</span>
            <AppSelect v-model="form.timeFormat" :options="timeFormats" />
          </label>
          <label class="block">
            <span class="mb-1 block text-sm font-medium text-gray-700">{{ $t('app.dateFormat') }}</span>
            <AppSelect v-model="form.dateFormat" :options="dateFormats" />
          </label>
        </div>
      </section>
    </div>
    <template #footer>
      <button
        type="button"
        :disabled="busy"
        class="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
        @click="save"
      >
        {{ $t('app.save') }}
      </button>
    </template>
  </SettingsPanel>
</template>
