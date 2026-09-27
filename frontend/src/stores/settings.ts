import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as api from '@/api'
import type { AppSettings, AppSettingsUpdate } from '@/api'

export const useSettingsStore = defineStore('settings', () => {
  const settings = ref<AppSettings | null>(null)
  const loading = ref(false)

  const appName = computed(() => settings.value?.app_name ?? 'Calendar')
  const logoUrl = computed(() => settings.value?.logo_url ?? null)
  const faviconUrl = computed(() => settings.value?.favicon_url ?? null)

  async function load() {
    loading.value = true
    try {
      settings.value = await api.getAppSettings()
    } catch (e) {
      console.error(e)
    } finally {
      loading.value = false
    }
  }

  async function update(token: string, data: AppSettingsUpdate) {
    const updated = await api.updateAppSettings(token, data)
    settings.value = updated
    return updated
  }

  return {
    settings,
    appName,
    logoUrl,
    faviconUrl,
    loading,
    load,
    update,
  }
})
