import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'

export type ThemePreference = 'light' | 'dark' | 'system'

const STORAGE_KEY = 'calendar-theme'

export const useThemeStore = defineStore('theme', () => {
  const stored = localStorage.getItem(STORAGE_KEY)
  const preference = ref<ThemePreference>(
    stored === 'light' || stored === 'dark' || stored === 'system' ? stored : 'system',
  )
  const systemDark = ref(window.matchMedia('(prefers-color-scheme: dark)').matches)
  const resolved = computed<'light' | 'dark'>(() =>
    preference.value === 'system' ? (systemDark.value ? 'dark' : 'light') : preference.value,
  )
  let initialized = false

  function applyTheme() {
    const dark = resolved.value === 'dark'
    document.documentElement.dataset.colorScheme = resolved.value
    document.documentElement.style.colorScheme = resolved.value
    document.documentElement.classList.toggle('dark', dark)
  }

  function setPreference(value: ThemePreference) {
    preference.value = value
    localStorage.setItem(STORAGE_KEY, value)
  }

  function toggle() {
    setPreference(resolved.value === 'dark' ? 'light' : 'dark')
  }

  function init() {
    if (initialized) return
    initialized = true
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    media.addEventListener('change', (event) => {
      systemDark.value = event.matches
    })
    watch(resolved, applyTheme, { immediate: true })
  }

  return { preference, resolved, setPreference, toggle, init }
})
