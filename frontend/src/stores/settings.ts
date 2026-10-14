import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as api from '@/api'

export const useSettingsStore = defineStore('settings', () => {
  const settings = ref<api.AppSettings | null>(null)

  const appName = computed(() => settings.value?.app_name || 'Meanwhile')
  const logoUrl = computed(() => settings.value?.logo_url ?? null)
  const faviconUrl = computed(() => settings.value?.favicon_url ?? null)

  async function load() {
    try {
      settings.value = await api.getAppSettings()
    } catch (error) {
      console.error(error)
    }
  }

  async function update(data: api.AppSettingsUpdate) {
    settings.value = await api.updateAppSettings(data)
    return settings.value
  }

  return { settings, appName, logoUrl, faviconUrl, load, update }
})
