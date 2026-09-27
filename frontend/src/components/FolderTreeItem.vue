<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import type Sortable from 'sortablejs'
import type { CalendarListItem, Folder } from '@/api'
import { useCalendarStore } from '@/stores/calendars'
import { useThemeStore } from '@/stores/theme'

const props = defineProps<{
  folder: Folder
  selectedId: string
  onSortEnd?: (evt: Sortable.SortableEvent) => void
}>()

const emit = defineEmits<{
  (e: 'select-calendar', id: string): void
  (e: 'select-folder', id: string): void
  (e: 'delete-folder', id: string): void
  (e: 'goto-settings', item: CalendarListItem): void
  (e: 'context-menu-folder', event: MouseEvent, folder: Folder): void
  (e: 'context-menu-calendar', event: MouseEvent, item: CalendarListItem): void
}>()

const store = useCalendarStore()
const themeStore = useThemeStore()
const expanded = ref(true)
const isSelected = computed(() => props.selectedId === props.folder.id)
const childList = ref<HTMLElement | null>(null)
let sortable: Sortable | null = null

function childrenOf(parentId: string | null): Folder[] {
  return store.folders.filter((f) => f.parent_id === parentId)
}

function calendarsInFolder(folderId: string): CalendarListItem[] {
  return store.items.filter((i) => i.membership.folder_id === folderId)
}

onMounted(() => {
  if (!childList.value || !props.onSortEnd) return
  import('sortablejs').then((module) => {
    const Sortable = module.default
    sortable = Sortable.create(childList.value!, {
      group: 'sidebar',
      animation: 150,
      draggable: '.sidebar-item',
      filter: '.sidebar-no-drag',
      preventOnFilter: false,
      onEnd: props.onSortEnd,
    })
  })
})

onUnmounted(() => {
  sortable?.destroy()
  sortable = null
})
</script>

<template>
  <div class="sidebar-item" data-type="folder" :data-id="folder.id">
    <div
      class="flex items-center h-8 gap-1 px-2 py-1 rounded cursor-pointer group"
      :class="{ 'bg-blue-100 dark:bg-blue-900': isSelected }"
      @contextmenu.stop.prevent="emit('select-folder', folder.id); emit('context-menu-folder', $event, folder)"
      @click="emit('select-folder', folder.id)"
    >
      <button
        @click.stop="expanded = !expanded"
        class="sidebar-no-drag text-gray-400 hover:text-gray-600 focus:outline-none"
        v-if="childrenOf(folder.id).length || calendarsInFolder(folder.id).length"
      >
        <svg v-if="expanded" class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" />
        </svg>
        <svg v-else class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" />
        </svg>
      </button>
      <span v-else class="w-3"></span>
      <svg class="w-4 h-4 text-yellow-500" fill="currentColor" viewBox="0 0 20 20">
        <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
      </svg>
      <span class="text-sm text-gray-700 flex-1 truncate">{{ folder.name }}</span>
    </div>

    <div
      v-if="expanded"
      ref="childList"
      class="sidebar-list folder-children ml-4"
      :data-folder-id="folder.id"
    >
      <div
        v-for="item in calendarsInFolder(folder.id)"
        :key="item.calendar.id"
        class="sidebar-item group flex items-center h-8 gap-2 px-2 py-1 rounded cursor-pointer"
        :class="{ 'bg-blue-100 dark:bg-blue-900': selectedId === item.calendar.id }"
        data-type="calendar"
        :data-id="item.calendar.id"
        @click="emit('select-calendar', item.calendar.id)"
        @contextmenu.stop.prevent="emit('select-calendar', item.calendar.id); emit('context-menu-calendar', $event, item)"
      >
        <span
          class="w-3 h-3 rounded-full border border-white shadow-sm"
          :style="{ backgroundColor: themeStore.resolved === 'dark' ? item.calendar.dark_color : item.calendar.color }"
        ></span>
        <span class="text-sm text-gray-700 truncate flex-1">{{ item.calendar.name }}</span>
      </div>
      <FolderTreeItem
        v-for="child in childrenOf(folder.id)"
        :key="child.id"
        :folder="child"
        :selectedId="selectedId"
        :on-sort-end="onSortEnd"
        @select-calendar="emit('select-calendar', $event)"
        @select-folder="emit('select-folder', $event)"
        @delete-folder="emit('delete-folder', $event)"
        @goto-settings="emit('goto-settings', $event)"
        @context-menu-folder="(event: MouseEvent, folder: Folder) => emit('context-menu-folder', event, folder)"
        @context-menu-calendar="(event: MouseEvent, item: CalendarListItem) => emit('context-menu-calendar', event, item)"
      />
    </div>
  </div>
</template>
