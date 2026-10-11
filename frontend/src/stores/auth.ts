import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import * as api from '@/api'
import { browserTimeZone } from '@/services/datetime'
import { realtime } from '@/services/realtime'
import { useCalendarStore } from './calendars'
import { useEventStore } from './events'
import { useNotificationsStore } from './notifications'
import { useOverviewStore } from './overview'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<api.User | null>(null)
  let initPromise: Promise<void> | null = null

  const isLoggedIn = computed(() => !!user.value)
  const isAdmin = computed(() => !!user.value?.is_admin)

  // Live updates while signed in; signing out (or the session ending) closes the connection.
  watch(
    () => user.value?.id ?? null,
    (id) => (id ? realtime.start() : realtime.stop()),
  )

  // The server reads times that calendar apps send without a zone in the user's zone,
  // so it learns the browser's zone whenever it differs.
  watch(user, (current) => {
    const zone = browserTimeZone()
    if (current && zone && current.timezone !== zone) {
      api.updateProfile({ timezone: zone }).then(
        (updated) => {
          if (user.value?.id === updated.id) user.value = updated
        },
        () => {
          // tried again on the next load
        },
      )
    }
  })

  /** Restores the session once; later calls wait for the same request. */
  function init(): Promise<void> {
    initPromise ??= (async () => {
      try {
        await api.getCsrf()
        user.value = await api.me()
      } catch {
        user.value = null
      }
    })()
    return initPromise
  }

  async function login(email: string, password: string) {
    user.value = await api.login({ email, password })
  }

  async function register(email: string, displayName: string, password: string) {
    user.value = await api.register({ email, display_name: displayName, password })
  }

  /** Forgets the user and everything loaded for them, so a following login starts clean. */
  function clearSession() {
    user.value = null
    // The next navigation fetches a fresh CSRF token for the new anonymous session.
    initPromise = null
    useCalendarStore().reset()
    useEventStore().reset()
    useNotificationsStore().reset()
    useOverviewStore().reset()
  }

  async function logout() {
    try {
      await api.logout()
    } catch {
      // the local session is cleared either way
    }
    clearSession()
  }

  async function updateProfile(data: api.ProfileUpdate) {
    user.value = await api.updateProfile(data)
  }

  return { user, isLoggedIn, isAdmin, init, login, register, logout, clearSession, updateProfile }
})
