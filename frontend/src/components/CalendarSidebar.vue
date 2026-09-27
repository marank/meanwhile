<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import type Sortable from 'sortablejs'
import FolderTreeItem from './FolderTreeItem.vue'
import ContextMenu, { type MenuItem } from './ContextMenu.vue'
import { useCalendarStore } from '@/stores/calendars'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore } from '@/stores/auth'
import { confirm, prompt } from '@/services/dialog'
import * as api from '@/api'
import type { CalendarListItem, Folder } from '@/api'

const SIDEBAR_WIDTH_KEY = 'calendar_sidebar_width'
const MIN_WIDTH = 180
const MAX_WIDTH = 500
const DEFAULT_WIDTH = 256

const store = useCalendarStore()
const themeStore = useThemeStore()
const auth = useAuthStore()
const router = useRouter()
const { t } = useI18n()

const sidebarWidth = ref(DEFAULT_WIDTH)
const isResizing = ref(false)
const rootList = ref<HTMLElement | null>(null)
let rootSortable: Sortable | null = null

onMounted(async () => {
  await store.load()
  await nextTick()
  initRootSortable()
  const saved = localStorage.getItem(SIDEBAR_WIDTH_KEY)
  if (saved) {
    const parsed = Number.parseInt(saved, 10)
    if (!Number.isNaN(parsed)) {
      sidebarWidth.value = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, parsed))
    }
  }
})

onUnmounted(() => {
  rootSortable?.destroy()
  rootSortable = null
})

function initRootSortable() {
  if (!rootList.value || rootSortable) return
  import('sortablejs').then((module) => {
    const Sortable = module.default
    rootSortable = Sortable.create(rootList.value!, {
      group: 'sidebar',
      animation: 150,
      draggable: '.sidebar-item',
      filter: '.sidebar-no-drag',
      preventOnFilter: false,
      onEnd: handleSortEnd,
    })
  })
}

function isRootList(element: HTMLElement) {
  return element === rootList.value
}

function targetFolderIdOf(element: HTMLElement): string | null {
  if (isRootList(element)) return null
  const folderId = element.dataset.folderId
  if (folderId) return folderId
  const parent = element.closest('[data-folder-id]') as HTMLElement | null
  return parent?.dataset.folderId ?? null
}

function descendantsOf(folderId: string): string[] {
  const result: string[] = []
  const direct = store.folders.filter((f) => f.parent_id === folderId)
  for (const child of direct) {
    result.push(child.id)
    result.push(...descendantsOf(child.id))
  }
  return result
}

function applyLocalReordering(
  updates: { type: 'folder' | 'calendar'; id: string; parent_id: string | null; position: number }[],
) {
  for (const update of updates) {
    if (update.type === 'folder') {
      const folder = store.folders.find((f) => f.id === update.id)
      if (folder) {
        folder.parent_id = update.parent_id
        folder.position = update.position
      }
    } else {
      const item = store.items.find((i) => i.calendar.id === update.id)
      if (item) {
        item.membership.folder_id = update.parent_id
        item.membership.position = update.position
      }
    }
  }

  store.folders = store.folders
    .slice()
    .sort((a, b) => a.position - b.position || a.name.localeCompare(b.name))

  store.items = store.items
    .slice()
    .sort(
      (a, b) =>
        a.membership.position - b.membership.position ||
        a.calendar.name.localeCompare(b.calendar.name),
    )
}

async function handleSortEnd(evt: Sortable.SortableEvent) {
  if (!auth.token) return

  const to = evt.to as HTMLElement
  const from = evt.from as HTMLElement
  const toTarget = targetFolderIdOf(to)
  const fromTarget = targetFolderIdOf(from)

  const item = evt.item
  const itemType = item.dataset.type
  const itemId = item.dataset.id
  if (
    itemType === 'folder' &&
    (toTarget === itemId || descendantsOf(itemId!).includes(toTarget ?? ''))
  ) {
    await store.load()
    return
  }

  const sidebarUpdates: { type: 'folder' | 'calendar'; id: string; parent_id: string | null; position: number }[] = []

  function collectFromContainer(container: HTMLElement, targetFolderId: string | null) {
    const children = container.querySelectorAll(':scope > .sidebar-item:not(.sidebar-no-drag)')
    children.forEach((el, index) => {
      const type = (el as HTMLElement).dataset.type as 'folder' | 'calendar' | undefined
      const id = (el as HTMLElement).dataset.id
      if (!type || !id) return
      sidebarUpdates.push({ type, id, parent_id: targetFolderId, position: index })
    })
  }

  collectFromContainer(to, toTarget)
  if (to !== from) {
    collectFromContainer(from, fromTarget)
  }

  applyLocalReordering(sidebarUpdates)

  try {
    await api.reorderSidebar(auth.token, sidebarUpdates)
  } catch (e) {
    console.error(e)
    await store.load()
  }
}

const topFolders = computed(() => store.folders.filter((f) => !f.parent_id))
const ungrouped = computed(() => store.items.filter((i) => !i.membership.folder_id))

function calendarColor(calendar: CalendarListItem['calendar']) {
  return themeStore.resolved === 'dark' ? calendar.dark_color : calendar.color
}

async function createCalendar() {
  const name = await prompt(
    t('app.calendarNamePrompt'),
    '',
    t('app.newCalendar'),
  )
  if (!name) return
  await store.create(name)
}

async function createFolder(parentId?: string | null) {
  const name = await prompt(
    t('app.folderNamePrompt'),
    '',
    t('app.createFolder'),
  )
  if (!name || !auth.token) return
  await api.createFolder(auth.token, name, parentId || undefined)
  await store.load()
}

function selectCalendar(id: string) {
  store.select(id)
  router.push('/calendar')
}

function selectFolder(id: string) {
  store.select(id)
  router.push('/calendar')
}

function gotoSettings(item: CalendarListItem) {
  router.push(`/settings/${item.calendar.id}`)
}

async function deleteFolder(id: string) {
  const ok = await confirm(t('app.deleteFolderText'), t('app.deleteFolderTitle'))
  if (!ok || !auth.token) return
  await api.deleteFolder(auth.token, id)
  await store.load()
}

const contextMenu = ref<{ visible: boolean; x: number; y: number; items: MenuItem[] }>({
  visible: false,
  x: 0,
  y: 0,
  items: [],
})

function openMenu(event: MouseEvent, items: MenuItem[]) {
  event.preventDefault()
  if (items.length === 0) return
  contextMenu.value = { visible: true, x: event.clientX, y: event.clientY, items }
}

function closeMenu() {
  contextMenu.value.visible = false
}

function folderMenuItems(folder: Folder): MenuItem[] {
  return [
    { label: t('app.createFolder'), action: () => createFolder(folder.id) },
    { label: t('app.rename'), action: () => renameFolder(folder) },
    { label: t('app.delete'), action: () => deleteFolder(folder.id) },
  ]
}

function rootMenuItems(): MenuItem[] {
  return [
    { label: t('app.createFolder'), action: () => createFolder() },
  ]
}

function calendarMenuItems(item: CalendarListItem): MenuItem[] {
  if (item.membership.role !== 'owner') {
    return []
  }
  return [
    { label: t('app.rename'), action: () => renameCalendar(item) },
    { label: t('app.delete'), action: () => deleteCalendarWithConfirm(item) },
    { label: t('app.settings'), action: () => gotoSettings(item) },
  ]
}

async function renameFolder(folder: Folder) {
  const name = await prompt(t('app.folderNamePrompt'), folder.name, t('app.rename'))
  if (!name || !auth.token) return
  await api.updateFolder(auth.token, folder.id, { name })
  await store.load()
}

async function renameCalendar(item: CalendarListItem) {
  const name = await prompt(t('app.calendarNamePrompt'), item.calendar.name, t('app.rename'))
  if (!name || !auth.token) return
  await api.updateCalendar(auth.token, item.calendar.id, { name })
  await store.load()
}

async function deleteCalendarWithConfirm(item: CalendarListItem) {
  const ok = await confirm(t('app.deleteCalendarText'), t('app.deleteCalendarTitle'))
  if (!ok || !auth.token) return
  await api.deleteCalendar(auth.token, item.calendar.id)
  await store.load()
}

function startResize(event: MouseEvent) {
  event.preventDefault()
  isResizing.value = true
  document.body.style.userSelect = 'none'
  const startX = event.clientX
  const startWidth = sidebarWidth.value

  function onMouseMove(e: MouseEvent) {
    const delta = e.clientX - startX
    sidebarWidth.value = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, startWidth + delta))
  }

  function onMouseUp() {
    isResizing.value = false
    document.body.style.userSelect = ''
    localStorage.setItem(SIDEBAR_WIDTH_KEY, String(sidebarWidth.value))
    window.removeEventListener('mousemove', onMouseMove)
    window.removeEventListener('mouseup', onMouseUp)
  }

  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
}
</script>

<template>
  <aside
    class="relative bg-white border-r border-gray-200 flex flex-col"
    :style="{ width: `${sidebarWidth}px` }"
  >
    <div
      ref="rootList"
      class="sidebar-list flex-1 overflow-y-auto p-2 space-y-1"
      @contextmenu.prevent="openMenu($event, rootMenuItems())"
    >
      <div
        @click="selectCalendar('all')"
        class="sidebar-item sidebar-no-drag flex items-center h-8 gap-2 px-2 py-1 rounded cursor-pointer"
        :class="{ 'bg-blue-100 dark:bg-blue-900': store.allSelected }"
      >
        <svg class="w-4 h-4 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
          <path d="M6 2a1 1 0 00-1 1v1H4a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2h-1V3a1 1 0 10-2 0v1H7V3a1 1 0 00-1-1zm0 5a1 1 0 000 2h8a1 1 0 100-2H6z" />
        </svg>
        <span class="text-sm font-medium text-gray-700">{{ $t('app.allCalendars') }}</span>
      </div>

      <FolderTreeItem
        v-for="folder in topFolders"
        :key="folder.id"
        :folder="folder"
        :selectedId="store.selectedId"
        :on-sort-end="handleSortEnd"
        @select-calendar="selectCalendar"
        @select-folder="selectFolder"
        @delete-folder="deleteFolder"
        @goto-settings="gotoSettings"
        @context-menu-folder="(e: MouseEvent, f: Folder) => openMenu(e, folderMenuItems(f))"
        @context-menu-calendar="(e: MouseEvent, i: CalendarListItem) => openMenu(e, calendarMenuItems(i))"
      />

      <div
        v-for="item in ungrouped"
        :key="item.calendar.id"
        class="sidebar-item flex items-center h-8 gap-2 px-2 py-1 ml-4 rounded cursor-pointer group"
        :class="{ 'bg-blue-100 dark:bg-blue-900': store.selectedId === item.calendar.id }"
        data-type="calendar"
        :data-id="item.calendar.id"
        @click="selectCalendar(item.calendar.id)"
        @contextmenu.stop.prevent="selectCalendar(item.calendar.id); openMenu($event, calendarMenuItems(item))"
      >
        <span
          class="w-3 h-3 rounded-full border border-white shadow-sm"
          :style="{ backgroundColor: calendarColor(item.calendar) }"
        ></span>
        <span class="text-sm text-gray-700 truncate flex-1">{{ item.calendar.name }}</span>
      </div>
    </div>

    <ContextMenu
      v-if="contextMenu.visible"
      :x="contextMenu.x"
      :y="contextMenu.y"
      :items="contextMenu.items"
      @close="closeMenu"
    />

    <div class="p-3 border-t border-gray-100">
      <button
        @click="createCalendar"
        class="w-full py-2 px-3 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition"
      >
        {{ $t('app.newCalendar') }}
      </button>
    </div>

    <div
      class="absolute right-0 top-0 bottom-0 w-2 cursor-col-resize hover:bg-blue-200/50 active:bg-blue-300/50 transition-colors"
      :class="{ 'bg-blue-200/50': isResizing }"
      @mousedown="startResize"
      aria-hidden="true"
    ></div>
  </aside>
</template>
