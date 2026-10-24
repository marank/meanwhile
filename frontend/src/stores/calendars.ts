import { defineStore } from 'pinia'
import { computed, onScopeDispose, ref } from 'vue'
import * as api from '@/api'
import { realtime } from '@/services/realtime'
import { compareSiblings } from '@/services/sidebarDrag'
import { hasRole } from '@/services/roles'

/** Selection of the calendar view: a calendar id, a folder id, or 'all'. It follows the URL. */
export const ALL_CALENDARS = 'all'

export const useCalendarStore = defineStore('calendars', () => {
  const items = ref<api.CalendarListItem[]>([])
  const folders = ref<api.Folder[]>([])
  const selectedId = ref<string>(ALL_CALENDARS)
  /** Whether calendars and folders have been loaded at least once. */
  const loaded = ref(false)
  let loadVersion = 0
  let refreshTimer: ReturnType<typeof setTimeout> | undefined

  const allSelected = computed(() => selectedId.value === ALL_CALENDARS)

  const calendarsById = computed(() => new Map(items.value.map((i) => [i.calendar.id, i.calendar])))

  const selectedCalendar = computed<api.Calendar | null>(
    () => items.value.find((i) => i.calendar.id === selectedId.value)?.calendar ?? null,
  )

  /** New events need one target calendar and at least the role to add one's own events there. */
  const canCreateInSelected = computed(() => {
    return hasRole(items.value.find((i) => i.calendar.id === selectedId.value)?.membership.role, 'own')
  })

  const selectedFolder = computed<api.Folder | null>(() => folders.value.find((f) => f.id === selectedId.value) ?? null)

  function groupBy<T>(list: T[], key: (item: T) => string | null): Map<string | null, T[]> {
    const groups = new Map<string | null, T[]>()
    for (const item of list) {
      const group = key(item)
      const members = groups.get(group)
      if (members) members.push(item)
      else groups.set(group, [item])
    }
    return groups
  }

  // Indexed once per change, so rendering the tree doesn't filter the full lists for every folder.
  const foldersByParent = computed(() => groupBy(folders.value, (f) => f.parent_id ?? null))
  const calendarsByFolder = computed(() => groupBy(items.value, (i) => i.membership.folder_id ?? null))

  /** What is shown directly under a folder (or the root): its folders and calendars in one list. */
  type TreeChild =
    { type: 'folder'; id: string; folder: api.Folder } | { type: 'calendar'; id: string; item: api.CalendarListItem }

  const childrenByParent = computed(() => {
    const result = new Map<string | null, TreeChild[]>()
    const add = (parentId: string | null, child: TreeChild) => {
      const list = result.get(parentId)
      if (list) list.push(child)
      else result.set(parentId, [child])
    }
    for (const folder of folders.value) add(folder.parent_id ?? null, { type: 'folder', id: folder.id, folder })
    for (const item of items.value)
      add(item.membership.folder_id ?? null, { type: 'calendar', id: item.calendar.id, item })
    const position = (child: TreeChild) =>
      child.type === 'folder'
        ? { type: child.type, position: child.folder.position, name: child.folder.name }
        : { type: child.type, position: child.item.membership.position, name: child.item.calendar.name }
    for (const list of result.values()) list.sort((a, b) => compareSiblings(position(a), position(b)))
    return result
  })

  function childrenOf(parentId: string | null): TreeChild[] {
    return childrenByParent.value.get(parentId) ?? []
  }

  function childFolders(parentId: string | null): api.Folder[] {
    return foldersByParent.value.get(parentId) ?? []
  }

  function calendarsIn(folderId: string | null): api.CalendarListItem[] {
    return calendarsByFolder.value.get(folderId) ?? []
  }

  /** All folders below `folderId`; the visited set guards against cycles in inconsistent data. */
  function descendantFolderIds(folderId: string): string[] {
    const found = new Set<string>()
    const pending = [folderId]
    while (pending.length) {
      for (const child of childFolders(pending.pop()!)) {
        if (found.has(child.id) || child.id === folderId) continue
        found.add(child.id)
        pending.push(child.id)
      }
    }
    return [...found]
  }

  /** Calendars whose events are shown for the current selection. */
  const selectedCalendarIds = computed<string[]>(() => {
    if (allSelected.value) return items.value.map((i) => i.calendar.id)
    if (selectedFolder.value) {
      const folderIds = [selectedFolder.value.id, ...descendantFolderIds(selectedFolder.value.id)]
      return folderIds.flatMap((id) => calendarsIn(id).map((i) => i.calendar.id))
    }
    return selectedCalendar.value ? [selectedCalendar.value.id] : []
  })

  /** Only the calendar view calls this, from its URL; everyone else navigates to `selectionPath(id)`. */
  function select(idOrPath: string) {
    selectedId.value =
      items.value.find((item) => item.calendar.id === idOrPath || item.calendar.url_path === idOrPath)?.calendar.id ??
      idOrPath
  }

  /** The URL that shows a calendar, a folder, or all calendars. */
  function selectionPath(id: string): string {
    if (id === ALL_CALENDARS) return '/calendar'
    if (folders.value.some((f) => f.id === id)) return `/calendar/folder/${id}`
    const calendar = calendarsById.value.get(id)
    return `/calendar/${calendar?.url_path || id}`
  }

  /** Loads calendars and folders; when loads overlap, only the latest one is applied. */
  async function load() {
    const version = ++loadVersion
    const layout = await api.getLayout()
    if (version !== loadVersion) return
    items.value = layout.calendars
    folders.value = layout.folders
    loaded.value = true
  }

  /** Loads again in the background, once for a burst of changes (e.g. removing a user from many calendars). */
  function refresh() {
    clearTimeout(refreshTimer)
    refreshTimer = setTimeout(() => {
      // Nothing to update before the first load or after signing out.
      if (loaded.value) load().catch(() => {})
    }, 300)
  }

  // Live updates: calendars shared with or taken from the user, renamed, recolored, moved into
  // folders or reordered elsewhere (another tab or device) show up without reloading the page.
  const stopListening = [realtime.on('calendars.changed', refresh), realtime.on('reconnected', refresh)]
  onScopeDispose(() => {
    stopListening.forEach((stop) => stop())
    clearTimeout(refreshTimer)
  })

  function reset() {
    loadVersion++
    clearTimeout(refreshTimer)
    items.value = []
    folders.value = []
    loaded.value = false
    selectedId.value = ALL_CALENDARS
  }

  async function createCalendar(name: string): Promise<api.Calendar> {
    const calendar = await api.createCalendar({ name })
    await load()
    return calendar
  }

  async function updateCalendar(id: string, data: api.CalendarUpdate): Promise<api.Calendar> {
    const calendar = await api.updateCalendar(id, data)
    const item = items.value.find((i) => i.calendar.id === id)
    if (item) item.calendar = calendar
    return calendar
  }

  async function deleteCalendar(id: string) {
    await api.deleteCalendar(id)
    await load()
  }

  async function createFolder(name: string, parentId: string | null = null) {
    await api.createFolder(name, parentId)
    await load()
  }

  async function renameFolder(id: string, name: string) {
    await api.updateFolder(id, { name })
    await load()
  }

  async function deleteFolder(id: string) {
    await api.deleteFolder(id)
    await load()
  }

  /** Applies a drag-and-drop result right away and persists it; reloads if the server rejects it. */
  async function reorder(updates: api.LayoutItem[]) {
    for (const update of updates) {
      if (update.type === 'folder') {
        const folder = folders.value.find((f) => f.id === update.id)
        if (folder) {
          folder.parent_id = update.parent_id ?? null
          folder.position = update.position
        }
      } else {
        const item = items.value.find((i) => i.calendar.id === update.id)
        if (item) {
          item.membership.folder_id = update.parent_id ?? null
          item.membership.position = update.position
        }
      }
    }
    folders.value = folders.value.slice().sort((a, b) => a.position - b.position || a.name.localeCompare(b.name))
    items.value = items.value
      .slice()
      .sort((a, b) => a.membership.position - b.membership.position || a.calendar.name.localeCompare(b.calendar.name))

    try {
      await api.updateLayoutItems(updates)
    } catch (error) {
      await load()
      throw error
    }
  }

  return {
    items,
    folders,
    selectedId,
    loaded,
    allSelected,
    selectedCalendar,
    canCreateInSelected,
    selectedFolder,
    selectedCalendarIds,
    calendarsById,
    childrenOf,
    childFolders,
    calendarsIn,
    descendantFolderIds,
    select,
    selectionPath,
    load,
    reset,
    createCalendar,
    updateCalendar,
    deleteCalendar,
    createFolder,
    renameFolder,
    deleteFolder,
    reorder,
  }
})
