import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as api from '@/api'
import { nonEmpty } from '@/services/text'

export const useSettingsStore = defineStore('settings', () => {
  // What everyone may see; saving as admin answers with these too (and more).
  const settings = ref<Omit<api.PublicSettings, 'allow_registration'> | null>(null)

  const appName = computed(() => nonEmpty(settings.value?.app_name) ?? 'Meanwhile')
  // None uploaded comes as an empty string.
  const logoUrl = computed(() => nonEmpty(settings.value?.logo_url) ?? null)
  const faviconUrl = computed(() => nonEmpty(settings.value?.favicon_url) ?? null)
  // Kept apart: saving the settings as admin answers without it. Off until known, so the login page
  // doesn't offer to sign up where nobody may.
  const allowRegistration = ref(false)

  async function load() {
    try {
      const loaded = await api.getAppSettings()
      settings.value = loaded
      allowRegistration.value = loaded.allow_registration
    } catch (error) {
      console.error(error)
    }
  }

  async function update(data: api.AppSettingsUpdate) {
    settings.value = await api.updateAppSettings(data)
    return settings.value
  }

  return { settings, appName, logoUrl, faviconUrl, allowRegistration, load, update }
})
