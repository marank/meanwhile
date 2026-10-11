<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import type Sortable from 'sortablejs'
import { CalendarDays } from 'lucide-vue-next'
import FolderTreeItem from './FolderTreeItem.vue'
import SidebarCalendarItem from './SidebarCalendarItem.vue'
import ContextMenu, { type MenuItem } from './ContextMenu.vue'
import { ALL_CALENDARS, useCalendarStore } from '@/stores/calendars'
import { useAction } from '@/composables/useAction'
import { useLoader } from '@/composables/useLoader'
import { confirm, prompt } from '@/services/dialog'
import { readStorage, writeStorage } from '@/services/storage'
import { useSidebarSortable } from '@/composables/useSidebarSortable'
import { collapsedFolders } from '@/services/sidebarState'
import type { CalendarListItem, Folder, SidebarReorderItem } from '@/api'

const SIDEBAR_WIDTH_KEY = 'calendar_sidebar_width'
const MIN_WIDTH = 180
const MAX_WIDTH = 500
const DEFAULT_WIDTH = 256

const store = useCalendarStore()
const router = useRouter()
const { t } = useI18n()
const { run } = useAction()

const sidebarWidth = ref(clampWidth(Number.parseInt(readStorage(SIDEBAR_WIDTH_KEY) ?? '', 10)))
const isResizing = ref(false)
const rootList = ref<HTMLElement | null>(null)

useLoader(store.load)
useSidebarSortable(rootList, handleSortEnd)

function clampWidth(width: number): number {
  return Number.isNaN(width) ? DEFAULT_WIDTH : Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, width))
}

function select(id: string) {
  router.push(store.selectionPath(id))
}

// Drag and drop

function targetFolderIdOf(list: HTMLElement): string | null {
  if (list === rootList.value) return null
  return list.closest<HTMLElement>('[data-folder-id]')?.dataset.folderId ?? null
}

function positionsIn(list: HTMLElement, parentId: string | null): SidebarReorderItem[] {
  return Array.from(list.querySelectorAll<HTMLElement>(':scope > .sidebar-item:not(.sidebar-no-drag)')).flatMap(
    (element, position) => {
      const { type, id } = element.dataset
      if ((type !== 'folder' && type !== 'calendar') || !id) return []
      return [{ type, id, parent_id: parentId, position }]
    },
  )
}

/** Puts a dragged item back where Sortable took it from; the lists are rendered from the store. */
function restorePosition(event: Sortable.SortableEvent) {
  const { item, from, oldIndex } = event
  item.remove()
  from.insertBefore(item, from.children[oldIndex ?? 0] ?? null)
}

/** The item was dropped onto a folder: it becomes the last entry of that folder. */
async function moveIntoFolder(event: Sortable.SortableEvent, folderId: string) {
  restorePosition(event)
  const { type, id } = event.item.dataset
  if ((type !== 'folder' && type !== 'calendar') || !id) return

  // A folder can't move into itself or one of its own subfolders.
  if (type === 'folder' && (folderId === id || store.descendantFolderIds(id).includes(folderId))) return

  const currentParent =
    type === 'folder'
      ? (store.folders.find((f) => f.id === id)?.parent_id ?? null)
      : (store.items.find((i) => i.calendar.id === id)?.membership.folder_id ?? null)
  collapsedFolders.delete(folderId)
  if (currentParent === folderId) return

  const positions = [
    ...store.calendarsIn(folderId).map((i) => i.membership.position),
    ...store.childFolders(folderId).map((f) => f.position),
  ]
  const position = positions.length ? Math.max(...positions) + 1 : 0
  await run(() => store.reorder([{ type, id, parent_id: folderId, position }]))
}

async function handleSortEnd(event: Sortable.SortableEvent, dropIntoFolderId: string | null) {
  if (dropIntoFolderId) return moveIntoFolder(event, dropIntoFolderId)
  const to = event.to
  const from = event.from
  const toFolderId = targetFolderIdOf(to)
  const { type, id } = event.item.dataset

  // A folder can't move into itself or one of its own subfolders; restore the stored order.
  if (
    type === 'folder' &&
    id &&
    toFolderId &&
    (toFolderId === id || store.descendantFolderIds(id).includes(toFolderId))
  ) {
    await store.load()
    return
  }

  const updates = positionsIn(to, toFolderId)
  if (to !== from) updates.push(...positionsIn(from, targetFolderIdOf(from)))
  await run(() => store.reorder(updates))
}

// Context menu

const contextMenu = ref<{ x: number; y: number; items: MenuItem[] } | null>(null)

function openMenu(event: MouseEvent, items: MenuItem[]) {
  if (!items.length) return
  // Opened from the keyboard (context menu key, Shift+F10), the event has no pointer position.
  if (event.clientX || event.clientY) {
    contextMenu.value = { x: event.clientX, y: event.clientY, items }
  } else {
    const rect = (event.target as Element).getBoundingClientRect()
    contextMenu.value = { x: rect.left + 16, y: rect.bottom, items }
  }
}

function rootMenuItems(): MenuItem[] {
  return [{ label: t('app.createFolder'), action: () => createFolder(null) }]
}

function folderMenuItems(folder: Folder): MenuItem[] {
  return [
    { label: t('app.createFolder'), action: () => createFolder(folder.id) },
    { label: t('app.rename'), action: () => renameFolder(folder) },
    { label: t('app.delete'), action: () => deleteFolder(folder) },
  ]
}

function calendarMenuItems(item: CalendarListItem): MenuItem[] {
  if (item.membership.role !== 'owner') return []
  return [
    { label: t('app.rename'), action: () => renameCalendar(item) },
    { label: t('app.delete'), action: () => deleteCalendar(item) },
    { label: t('app.settings'), action: () => router.push(`/settings/${item.calendar.id}`) },
  ]
}

// Actions

async function createCalendar() {
  const name = await prompt(t('app.calendarNamePrompt'), '', t('app.newCalendar'))
  if (name) await run(async () => select((await store.createCalendar(name)).id))
}

async function renameCalendar(item: CalendarListItem) {
  const name = await prompt(t('app.calendarNamePrompt'), item.calendar.name, t('app.rename'))
  if (name) await run(() => store.updateCalendar(item.calendar.id, { name }))
}

async function deleteCalendar(item: CalendarListItem) {
  if (await confirm(t('app.deleteCalendarText'), t('app.deleteCalendarTitle'))) {
    await run(() => store.deleteCalendar(item.calendar.id))
  }
}

async function createFolder(parentId: string | null) {
  const name = await prompt(t('app.folderNamePrompt'), '', t('app.createFolder'))
  if (name) await run(() => store.createFolder(name, parentId))
}

async function renameFolder(folder: Folder) {
  const name = await prompt(t('app.folderNamePrompt'), folder.name, t('app.rename'))
  if (name) await run(() => store.renameFolder(folder.id, name))
}

async function deleteFolder(folder: Folder) {
  if (await confirm(t('app.deleteFolderText'), t('app.deleteFolderTitle'))) {
    await run(() => store.deleteFolder(folder.id))
  }
}

// Resizing

function startResize(event: MouseEvent) {
  event.preventDefault()
  isResizing.value = true
  document.body.style.userSelect = 'none'
  const startX = event.clientX
  const startWidth = sidebarWidth.value

  function onMouseMove(moveEvent: MouseEvent) {
    sidebarWidth.value = clampWidth(startWidth + moveEvent.clientX - startX)
  }

  function onMouseUp() {
    isResizing.value = false
    document.body.style.userSelect = ''
    writeStorage(SIDEBAR_WIDTH_KEY, String(sidebarWidth.value))
    window.removeEventListener('mousemove', onMouseMove)
    window.removeEventListener('mouseup', onMouseUp)
  }

  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
}
</script>

<template>
  <aside class="relative flex flex-col border-r border-line bg-surface" :style="{ width: `${sidebarWidth}px` }">
    <div class="flex-1 space-y-1 overflow-y-auto p-2" @contextmenu.prevent="openMenu($event, rootMenuItems())">
      <!-- Outside the sortable list: nothing can be dragged above it. -->
      <div
        class="flex h-8 cursor-pointer items-center gap-2 rounded px-2 py-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        :class="{ 'bg-blue-100 dark:bg-blue-900': store.allSelected }"
        role="button"
        tabindex="0"
        :aria-current="store.allSelected || undefined"
        @click="select(ALL_CALENDARS)"
        @keydown.enter.space.prevent="select(ALL_CALENDARS)"
      >
        <CalendarDays :size="16" class="shrink-0 text-gray-500" />
        <span class="text-sm font-medium text-gray-700">{{ $t('app.allCalendars') }}</span>
      </div>

      <div ref="rootList" class="sidebar-list min-h-8 space-y-1">
        <FolderTreeItem
          v-for="folder in store.childFolders(null)"
          :key="folder.id"
          :folder="folder"
          :on-sort-end="handleSortEnd"
          @select="select"
          @folder-menu="(event, folder) => openMenu(event, folderMenuItems(folder))"
          @calendar-menu="(event, item) => openMenu(event, calendarMenuItems(item))"
        />

        <SidebarCalendarItem
          v-for="item in store.calendarsIn(null)"
          :key="item.calendar.id"
          :item="item"
          :selected="store.selectedId === item.calendar.id"
          @select="select"
          @context-menu="(event, calendar) => openMenu(event, calendarMenuItems(calendar))"
        />
      </div>
    </div>

    <ContextMenu
      v-if="contextMenu"
      :x="contextMenu.x"
      :y="contextMenu.y"
      :items="contextMenu.items"
      @close="contextMenu = null"
    />

    <div class="border-t border-line p-3">
      <button
        type="button"
        class="w-full rounded-lg bg-blue-600 px-3 py-2 text-sm text-white transition hover:bg-blue-700"
        @click="createCalendar"
      >
        {{ $t('app.newCalendar') }}
      </button>
    </div>

    <div
      class="absolute bottom-0 right-0 top-0 w-2 cursor-col-resize transition-colors hover:bg-blue-200/50 active:bg-blue-300/50"
      :class="{ 'bg-blue-200/50': isResizing }"
      aria-hidden="true"
      @mousedown="startResize"
    ></div>
  </aside>
</template>
