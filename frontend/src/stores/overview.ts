import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '@/api'

/** The user's settings for "All calendars" and folder views. */
export const useOverviewStore = defineStore('overview', () => {
  const settings = ref<api.OverviewSettings | null>(null)
  let loading: Promise<void> | null = null

  /** Loads the settings once; later calls wait for the same request. */
  function load(): Promise<void> {
    loading ??= api
      .getOverviewSettings()
      .then((value) => {
        settings.value = value
      })
      .catch((error) => {
        loading = null
        throw error
      })
    return loading
  }

  async function update(data: Partial<api.OverviewSettings>) {
    settings.value = await api.updateOverviewSettings(data)
    return settings.value
  }

  function reset() {
    settings.value = null
    loading = null
  }

  return { settings, load, update, reset }
})
