<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { CalendarDays } from 'lucide-vue-next'
import FolderTreeItem from './FolderTreeItem.vue'
import SidebarCalendarItem from './SidebarCalendarItem.vue'
import ContextMenu, { type MenuItem } from './ContextMenu.vue'
import { ALL_CALENDARS, useCalendarStore } from '@/stores/calendars'
import { useAction } from '@/composables/useAction'
import { useLoader } from '@/composables/useLoader'
import { confirm, prompt } from '@/services/dialog'
import { readStorage, writeStorage } from '@/services/storage'
import { useSidebarDrag, type SidebarDrop } from '@/composables/useSidebarDrag'
import { planMove, type SidebarTree } from '@/services/sidebarDrag'
import { collapsedFolders, dropIndicator } from '@/services/sidebarState'
import type { CalendarListItem, Folder } from '@/api'

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
const scroller = ref<HTMLElement | null>(null)

useLoader(store.load)
useSidebarDrag(scroller, handleDrop)

function clampWidth(width: number): number {
  return Number.isNaN(width) ? DEFAULT_WIDTH : Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, width))
}

function select(id: string) {
  router.push(store.selectionPath(id))
}

// Drag and drop

const tree = computed<SidebarTree>(() => ({
  folders: store.folders.map((f) => ({ id: f.id, parentId: f.parent_id ?? null, position: f.position, name: f.name })),
  calendars: store.items.map((i) => ({
    id: i.calendar.id,
    parentId: i.membership.folder_id ?? null,
    position: i.membership.position,
    name: i.calendar.name,
  })),
}))

async function handleDrop({ type, id, parentId, anchor }: SidebarDrop) {
  // A folder that received an item shows it.
  if (parentId) collapsedFolders.delete(parentId)
  const updates = planMove(tree.value, type, id, parentId, anchor)
  if (updates.length) await run(() => store.reorder(updates))
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
    <div
      ref="scroller"
      class="relative flex-1 select-none space-y-1 overflow-y-auto p-2"
      @contextmenu.prevent="openMenu($event, rootMenuItems())"
    >
      <!-- Outside the tree: nothing is dropped above it. -->
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

      <div class="sidebar-list min-h-8 space-y-1">
        <template v-for="child in store.childrenOf(null)" :key="child.id">
          <FolderTreeItem
            v-if="child.type === 'folder'"
            :folder="child.folder"
            @select="select"
            @folder-menu="(event, folder) => openMenu(event, folderMenuItems(folder))"
            @calendar-menu="(event, item) => openMenu(event, calendarMenuItems(item))"
          />
          <SidebarCalendarItem
            v-else
            :item="child.item"
            :selected="store.selectedId === child.id"
            @select="select"
            @context-menu="(event, calendar) => openMenu(event, calendarMenuItems(calendar))"
          />
        </template>
      </div>

      <!-- Where the dragged item would go between rows. -->
      <div
        v-if="dropIndicator"
        class="pointer-events-none absolute h-0.5 rounded-full bg-blue-500"
        :style="{ top: `${dropIndicator.top}px`, left: `${dropIndicator.left}px`, width: `${dropIndicator.width}px` }"
        aria-hidden="true"
      ></div>
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
