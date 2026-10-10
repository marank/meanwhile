import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '@/api'
import { i18n } from '@/i18n'
import { errorMessage } from '@/services/errors'
import { toast } from '@/services/toast'
import { useCalendarStore } from './calendars'

export const useEventStore = defineStore('events', () => {
  const calendars = useCalendarStore()

  const occurrences = ref<api.Occurrence[]>([])
  let loadVersion = 0
  let lastLoadKey = ''

  /**
   * Loads the occurrences of the selected calendars. Requests for the range already shown are
   * skipped, and when loads overlap only the latest one is applied.
   */
  async function load(rangeStart: Date, rangeEnd: Date, force = false) {
    const ids = calendars.selectedCalendarIds
    const start = rangeStart.toISOString()
    const end = rangeEnd.toISOString()
    const loadKey = `${ids.join(',')}|${start}|${end}`
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

  function reset() {
    loadVersion++
    lastLoadKey = ''
    occurrences.value = []
  }

  return { occurrences, load, reset }
})
