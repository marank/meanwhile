<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { CalendarDays, EllipsisVertical } from '@lucide/vue'
import FolderTreeItem from './FolderTreeItem.vue'
import SidebarCalendarItem from './SidebarCalendarItem.vue'
import ContextMenu, { type MenuItem } from './ContextMenu.vue'
import IconButton from './IconButton.vue'
import PublicCalendarsDialog from './PublicCalendarsDialog.vue'
import { ALL_CALENDARS, useCalendarStore } from '@/stores/calendars'
import { useAction } from '@/composables/useAction'
import { useLoader } from '@/composables/useLoader'
import { useEscapeToClose } from '@/composables/useEscapeToClose'
import { confirm, prompt } from '@/services/dialog'
import { readStorage, writeStorage } from '@/services/storage'
import { useSidebarDrag, type SidebarDrop } from '@/composables/useSidebarDrag'
import { planMove, type SidebarTree } from '@/services/sidebarDrag'
import { collapsedFolders, dropIndicator, sidebarDrawerOpen } from '@/services/sidebarState'
import { hasRole } from '@/services/roles'
import * as api from '@/api'
import type { CalendarListItem, Folder } from '@/api'

const SIDEBAR_WIDTH_KEY = 'sidebar-width'
const MIN_WIDTH = 180
const MAX_WIDTH = 500
const DEFAULT_WIDTH = 256

const store = useCalendarStore()
const router = useRouter()
const route = useRoute()
const { t } = useI18n()
const { run } = useAction()

const sidebarWidth = ref(clampWidth(Number.parseInt(readStorage(SIDEBAR_WIDTH_KEY) ?? '', 10)))
const isResizing = ref(false)
const scroller = ref<HTMLElement | null>(null)

useLoader(store.load)
useSidebarDrag(scroller, (drop) => void handleDrop(drop), openHeldMenu)
useEscapeToClose(
  () => sidebarDrawerOpen.value,
  () => (sidebarDrawerOpen.value = false),
)

// The drawer slides only while it is opened or closed, not when the window crosses the desktop breakpoint
// (a tablet turned upright), where the sidebar would otherwise visibly slide out.
const sliding = ref(false)
let slideTimer: ReturnType<typeof setTimeout> | undefined
watch(sidebarDrawerOpen, () => {
  sliding.value = true
  clearTimeout(slideTimer)
  slideTimer = setTimeout(() => (sliding.value = false), 250)
})

// The drawer closes once something in it was opened; not for the context menu, which selects its item.
watch(
  () => route.fullPath,
  () => {
    if (!contextMenu.value) sidebarDrawerOpen.value = false
  },
)

function clampWidth(width: number): number {
  return Number.isNaN(width) ? DEFAULT_WIDTH : Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, width))
}

function select(id: string) {
  void router.push(store.selectionPath(id))
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

const contextMenu = ref<{ x: number; y: number; items: MenuItem[]; above?: boolean } | null>(null)
const showPublicCalendars = ref(false)

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
  return [
    { label: t('app.createFolder'), action: () => createFolder(null) },
    { label: t('app.publicCalendars'), action: () => (showPublicCalendars.value = true) },
  ]
}

/** On touch screens a row's menu opens by holding the row (useSidebarDrag), at the finger. */
function openHeldMenu(held: { type: 'folder' | 'calendar'; id: string }, x: number, y: number) {
  const folder = held.type === 'folder' ? store.folders.find((f) => f.id === held.id) : undefined
  const item = held.type === 'calendar' ? store.items.find((i) => i.calendar.id === held.id) : undefined
  const items = folder ? folderMenuItems(folder) : item ? calendarMenuItems(item) : []
  if (items.length) contextMenu.value = { x, y, items }
}

/** The menu of the button next to "New calendar", opening upwards from it. */
function openMoreMenu(event: MouseEvent) {
  const rect = (event.currentTarget as Element).getBoundingClientRect()
  contextMenu.value = { x: rect.left, y: rect.top - 4, items: rootMenuItems(), above: true }
}

function folderMenuItems(folder: Folder): MenuItem[] {
  return [
    { label: t('app.createFolder'), action: () => createFolder(folder.id) },
    { label: t('app.rename'), action: () => renameFolder(folder) },
    { label: t('app.delete'), action: () => deleteFolder(folder) },
  ]
}

function calendarMenuItems(item: CalendarListItem): MenuItem[] {
  const role = item.membership.role
  // A public calendar the user added (they never manage it through that) leaves the sidebar again.
  if (item.access === 'public') {
    return [{ label: t('app.removeFromSidebar'), action: () => removePublicCalendar(item) }]
  }
  if (!hasRole(role, 'manage')) return []
  // Who manages a calendar changes it; only its owner deletes it.
  return [
    { label: t('app.rename'), action: () => renameCalendar(item) },
    ...(role === 'owner' ? [{ label: t('app.delete'), action: () => deleteCalendar(item) }] : []),
    { label: t('app.settings'), action: () => router.push(`/calendar/${item.calendar.id}/settings`) },
  ]
}

// Actions

async function removePublicCalendar(item: CalendarListItem) {
  await run(async () => {
    await api.removePublicCalendar(item.calendar.id)
    await store.load()
  })
}

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
  <!-- Below the desktop breakpoint the sidebar is a drawer, opened from the navbar. What it covers darkens
       and lightens again as it slides in and out. -->
  <Transition
    enter-active-class="transition-opacity duration-200"
    leave-active-class="transition-opacity duration-200"
    enter-from-class="opacity-0"
    leave-to-class="opacity-0"
  >
    <div
      v-if="sidebarDrawerOpen"
      class="absolute inset-0 z-40 bg-black/40 lg:hidden dark:bg-black/60"
      data-drawer-backdrop
      aria-hidden="true"
      @click="sidebarDrawerOpen = false"
    ></div>
  </Transition>
  <aside
    id="calendar-sidebar"
    :data-state="sidebarDrawerOpen ? 'open' : 'closed'"
    class="absolute inset-y-0 left-0 z-40 flex w-72 max-w-[85vw] flex-col border-r border-line bg-surface shadow-xl lg:relative lg:z-auto lg:w-[var(--sidebar-width)] lg:max-w-none lg:translate-none lg:shadow-none lg:transition-none"
    :class="[
      sidebarDrawerOpen ? 'translate-none' : 'max-lg:invisible -translate-x-full',
      { 'transition-[translate,visibility] duration-200': sliding },
    ]"
    :style="{ '--sidebar-width': `${sidebarWidth}px` }"
  >
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
      :above="contextMenu.above"
      @close="contextMenu = null"
    />

    <PublicCalendarsDialog v-if="showPublicCalendars" @close="showPublicCalendars = false" />

    <div class="flex items-center gap-2 border-t border-line p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
      <button
        type="button"
        class="min-w-0 flex-1 rounded-lg bg-blue-600 px-3 py-2 text-sm text-white transition hover:bg-blue-700"
        @click="createCalendar"
      >
        {{ $t('app.newCalendar') }}
      </button>
      <!-- Square, as tall as the "New calendar" button next to it. -->
      <IconButton
        bordered
        class="h-9 w-9 shrink-0"
        :label="$t('app.moreActions')"
        aria-haspopup="menu"
        @click="openMoreMenu"
      >
        <EllipsisVertical :size="18" :stroke-width="2.25" />
      </IconButton>
    </div>

    <div
      class="absolute bottom-0 right-0 top-0 hidden w-2 cursor-col-resize lg:block transition-colors hover:bg-blue-200/50 active:bg-blue-300/50"
      :class="{ 'bg-blue-200/50': isResizing }"
      aria-hidden="true"
      @mousedown="startResize"
    ></div>
  </aside>
</template>
