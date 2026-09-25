import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '@/api'
import { useAuthStore } from './auth'
import { useCalendarStore } from './calendars'
import type { Occurrence } from '@/api'

export const useEventStore = defineStore('events', () => {
  const auth = useAuthStore()
  const calendars = useCalendarStore()

  const occurrences = ref<Occurrence[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  let loadVersion = 0
  let activeLoadKey = ''
  let lastLoadKey = ''

  function selectedCalendarIds(): string[] {
    if (calendars.allSelected) {
      return calendars.items.map((i) => i.calendar.id)
    }
    const sel = calendars.selectedId
    // Check if it is a folder id
    const folder = calendars.folders.find((f) => f.id === sel)
    if (folder) {
      const childFolderIds = new Set<string>([folder.id])
      let changed = true
      while (changed) {
        changed = false
        for (const f of calendars.folders) {
          if (!childFolderIds.has(f.id) && f.parent_id && childFolderIds.has(f.parent_id)) {
            childFolderIds.add(f.id)
            changed = true
          }
        }
      }
      return calendars.items
        .filter((i) => i.membership.folder_id && childFolderIds.has(i.membership.folder_id))
        .map((i) => i.calendar.id)
    }
    if (calendars.selectedCalendar) {
      return [calendars.selectedCalendar.id]
    }
    return []
  }

  async function load(rangeStart: Date, rangeEnd: Date, force = false) {
    if (!auth.token) return
    const ids = selectedCalendarIds()
    const start = rangeStart.toISOString()
    const end = rangeEnd.toISOString()
    const loadKey = `${ids.join(',')}|${start}|${end}`
    if (!force && (loadKey === activeLoadKey || loadKey === lastLoadKey)) return
    const version = ++loadVersion
    activeLoadKey = loadKey
    if (ids.length === 0) {
      occurrences.value = []
      loading.value = false
      lastLoadKey = loadKey
      activeLoadKey = ''
      return
    }
    loading.value = true
    error.value = null
    try {
      const results = await Promise.all(
        ids.map((id) => api.listEvents(auth.token!, id, start, end).catch(() => [] as Occurrence[])),
      )
      if (version === loadVersion) {
        occurrences.value = results.flat().sort((a, b) => a.start.localeCompare(b.start))
        lastLoadKey = loadKey
      }
    } catch (e: any) {
      if (version === loadVersion) error.value = e.message || 'Failed to load events'
    } finally {
      if (version === loadVersion) {
        loading.value = false
        activeLoadKey = ''
      }
    }
  }

  return {
    occurrences,
    loading,
    error,
    selectedCalendarIds,
    load,
  }
})
