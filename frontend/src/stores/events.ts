import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import * as api from '@/api'
import { i18n } from '@/i18n'
import { errorMessage } from '@/services/errors'
import { realtime } from '@/services/realtime'
import { toast } from '@/services/toast'
import { useCalendarStore } from './calendars'

export const useEventStore = defineStore('events', () => {
  const calendars = useCalendarStore()

  const occurrences = ref<api.Occurrence[]>([])
  let loadVersion = 0
  let lastLoadKey = ''
  /** The range shown, to load again when others change its events. */
  let lastRange: [Date, Date] | null = null
  let refreshTimer: ReturnType<typeof setTimeout> | undefined

  /**
   * Loads the occurrences of the selected calendars. Requests for the range already shown are
   * skipped, and when loads overlap only the latest one is applied.
   */
  async function load(rangeStart: Date, rangeEnd: Date, force = false) {
    const ids = calendars.selectedCalendarIds
    const start = rangeStart.toISOString()
    const end = rangeEnd.toISOString()
    const loadKey = `${ids.join(',')}|${start}|${end}`
    lastRange = [rangeStart, rangeEnd]
    if (!force && loadKey === lastLoadKey) return
    lastLoadKey = loadKey
    const version = ++loadVersion
    try {
      const result = ids.length ? await api.listEvents(ids, start, end) : []
      if (version === loadVersion) occurrences.value = result
    } catch (error) {
      if (version !== loadVersion) return
      // Allow the same range to be retried.
      lastLoadKey = ''
      toast.error(errorMessage(error, i18n.global.t('app.loadFailed')))
    }
  }

  /** Loads the range shown again, once for a burst of changes (e.g. a series saved in parts). */
  function refresh() {
    clearTimeout(refreshTimer)
    refreshTimer = setTimeout(() => {
      if (lastRange) void load(lastRange[0], lastRange[1], true)
    }, 300)
  }

  // Live updates: follow the calendars shown, and load again when their events change elsewhere
  // (another user, another tab, a phone via CalDAV) or after updates may have been missed.
  watch(
    () => calendars.selectedCalendarIds,
    (ids) => realtime.setCalendars(ids),
    { immediate: true },
  )
  realtime.on('events.changed', (message) => {
    if (calendars.selectedCalendarIds.includes(String(message.calendar_id))) refresh()
  })
  realtime.on('reconnected', refresh)

  function reset() {
    loadVersion++
    lastLoadKey = ''
    lastRange = null
    clearTimeout(refreshTimer)
    occurrences.value = []
  }

  return { occurrences, load, reset }
})
