import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { readStorage, writeStorage } from '@/services/storage'

export type ThemePreference = 'light' | 'dark' | 'system'

const STORAGE_KEY = 'theme'

export const useThemeStore = defineStore('theme', () => {
  const media = window.matchMedia('(prefers-color-scheme: dark)')
  const stored = readStorage(STORAGE_KEY)
  const preference = ref<ThemePreference>(
    stored === 'light' || stored === 'dark' || stored === 'system' ? stored : 'system',
  )
  const systemDark = ref(media.matches)
  const resolved = computed<'light' | 'dark'>(() =>
    preference.value === 'system' ? (systemDark.value ? 'dark' : 'light') : preference.value,
  )
  const isDark = computed(() => resolved.value === 'dark')
  let initialized = false

  function applyTheme() {
    document.documentElement.style.colorScheme = resolved.value
    document.documentElement.classList.toggle('dark', isDark.value)
  }

  function setPreference(value: ThemePreference) {
    preference.value = value
    writeStorage(STORAGE_KEY, value)
  }

  function toggle() {
    setPreference(isDark.value ? 'light' : 'dark')
  }

  function init() {
    if (initialized) return
    initialized = true
    media.addEventListener('change', (event) => {
      systemDark.value = event.matches
    })
    watch(resolved, applyTheme, { immediate: true })
  }

  return { preference, resolved, isDark, setPreference, toggle, init }
})
