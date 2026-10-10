import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as api from '@/api'
import { useAuthStore } from './auth'

export const useCalendarStore = defineStore('calendars', () => {
  const auth = useAuthStore()

  const items = ref<api.CalendarListItem[]>([])
  const folders = ref<api.Folder[]>([])
  const selectedId = ref<string>('all')
  const loading = ref(false)

  const allSelected = computed(() => selectedId.value === 'all')

  const selectedCalendar = computed<api.Calendar | null>(() => {
    if (allSelected.value) return null
    const found = items.value.find((i) => i.calendar.id === selectedId.value)
    return found?.calendar || null
  })

  function select(id: string) {
    selectedId.value = id
  }

  async function load() {
    if (!auth.isLoggedIn) return
    loading.value = true
    try {
      const [calData, folderData] = await Promise.all([
        api.listCalendars(),
        api.listFolders(),
      ])
      items.value = calData
      folders.value = folderData
    } finally {
      loading.value = false
    }
  }

  async function create(name: string, description?: string, color?: string) {
    if (!auth.isLoggedIn) return
    const cal = await api.createCalendar(name, description, color)
    await load()
    selectedId.value = cal.id
  }

  function groupedItems() {
    const folderMap = new Map<string | null, api.CalendarListItem[]>()
    for (const item of items.value) {
      const folderId = item.membership.folder_id || null
      if (!folderMap.has(folderId)) folderMap.set(folderId, [])
      folderMap.get(folderId)!.push(item)
    }
    return folderMap
  }

  return {
    items,
    folders,
    selectedId,
    loading,
    allSelected,
    selectedCalendar,
    select,
    load,
    create,
    groupedItems,
  }
})
