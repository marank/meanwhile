import { defineStore } from 'pinia'
import { computed, onScopeDispose, ref, watch } from 'vue'
import * as api from '@/api'
import { i18n, isLocale, setLocale } from '@/i18n'
import { browserTimeZone, DEFAULT_DAY_START } from '@/services/datetime'
import { realtime } from '@/services/realtime'
import { useCalendarStore } from './calendars'
import { useEventStore } from './events'
import { useNotificationsStore } from './notifications'
import { useOverviewStore } from './overview'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<api.User | null>(null)
  let initPromise: Promise<void> | null = null
  let csrfPromise: Promise<unknown> | null = null

  const isLoggedIn = computed(() => !!user.value)
  const isAdmin = computed(() => !!user.value?.is_admin)
  /** The hour the user's day starts, where new events on a picked day begin. */
  const dayStart = computed(() => user.value?.day_start ?? DEFAULT_DAY_START)

  // Live updates while signed in; signing out (or the session ending) closes the connection.
  watch(
    () => user.value?.id ?? null,
    (id) => (id ? realtime.start() : realtime.stop()),
  )

  // The live connection was refused for want of a session, and it doesn't retry by itself. Ask the API whether
  // the session is really gone: if it is, the request fails with 401 and the unauthorized handler signs out;
  // otherwise connect again, though not more than once a minute should the socket keep refusing.
  let lastRestart = 0
  async function recheckSession() {
    if (!user.value) return
    try {
      const current = await api.me()
      // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition -- may have signed out during the await
      if (user.value?.id === current.id) user.value = current
    } catch (error) {
      if (error instanceof api.ApiError && error.status === 401) return
      // e.g. offline: connecting again keeps retrying until the network is back
    }
    const wait = Math.max(0, lastRestart + 60_000 - Date.now())
    setTimeout(() => {
      if (!user.value) return
      lastRestart = Date.now()
      realtime.start()
    }, wait)
  }
  const stopListening = realtime.on('unauthenticated', () => void recheckSession())
  onScopeDispose(stopListening)

  // The server reads times that calendar apps send without a zone in the user's zone, so it learns
  // the browser's whenever they differ. The language is the account's, chosen in its settings: the
  // browser takes it on, as another person may have used it before. Only an account without one yet
  // (new, or from before the setting) takes the browser's, which emails are then written in.
  watch(user, (current) => {
    if (!current) return
    const changes: api.ProfileUpdate = {}
    const zone = browserTimeZone()
    if (zone && current.timezone !== zone) changes.timezone = zone
    if (isLocale(current.language)) {
      if (current.language !== i18n.global.locale.value) setLocale(current.language)
    } else {
      changes.language = i18n.global.locale.value
    }
    if (Object.keys(changes).length) {
      api.updateProfile(changes).then(
        (updated) => {
          if (user.value?.id === updated.id) user.value = updated
        },
        () => {
          // tried again on the next load
        },
      )
    }
  })

  /** The CSRF cookie, which forms that post need, also without a session. Fetched once per session. */
  function prepareCsrf(): Promise<unknown> {
    csrfPromise ??= api.getCsrf().catch((error: unknown) => {
      csrfPromise = null
      throw error
    })
    return csrfPromise
  }

  /** Restores the session once; later calls wait for the same request. */
  function init(): Promise<void> {
    initPromise ??= (async () => {
      try {
        await prepareCsrf()
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
    csrfPromise = null
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

  return {
    user,
    isLoggedIn,
    isAdmin,
    dayStart,
    init,
    prepareCsrf,
    login,
    register,
    logout,
    clearSession,
    updateProfile,
  }
})
