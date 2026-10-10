<script setup lang="ts">
import { computed, ref } from 'vue'
import type Sortable from 'sortablejs'
import { ChevronDown, ChevronRight, Folder as FolderIcon } from 'lucide-vue-next'
import type { CalendarListItem, Folder } from '@/api'
import SidebarCalendarItem from './SidebarCalendarItem.vue'
import { useCalendarStore } from '@/stores/calendars'
import { useSidebarSortable } from '@/composables/useSidebarSortable'

const props = defineProps<{
  folder: Folder
  onSortEnd: (event: Sortable.SortableEvent) => void
}>()

const emit = defineEmits<{
  select: [id: string]
  folderMenu: [event: MouseEvent, folder: Folder]
  calendarMenu: [event: MouseEvent, item: CalendarListItem]
}>()

const store = useCalendarStore()
const expanded = ref(true)
const childList = ref<HTMLElement | null>(null)
const childFolders = computed(() => store.childFolders(props.folder.id))
const calendars = computed(() => store.calendarsIn(props.folder.id))
const hasChildren = computed(() => childFolders.value.length > 0 || calendars.value.length > 0)

useSidebarSortable(childList, props.onSortEnd)

function openContextMenu(event: MouseEvent) {
  emit('select', props.folder.id)
  emit('folderMenu', event, props.folder)
}
</script>

<template>
  <div class="sidebar-item" data-type="folder" :data-id="folder.id">
    <div
      class="flex h-8 cursor-pointer items-center gap-1 rounded px-2 py-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
      :class="{ 'bg-blue-100 dark:bg-blue-900': store.selectedId === folder.id }"
      role="button"
      tabindex="0"
      :aria-current="store.selectedId === folder.id || undefined"
      @click="emit('select', folder.id)"
      @keydown.enter.space.self.prevent="emit('select', folder.id)"
      @keydown.right.self.prevent="expanded = true"
      @keydown.left.self.prevent="expanded = false"
      @contextmenu.stop.prevent="openContextMenu"
    >
      <button
        v-if="hasChildren"
        type="button"
        class="sidebar-no-drag text-gray-400 hover:text-gray-600 focus:outline-none"
        :aria-expanded="expanded"
        @click.stop="expanded = !expanded"
      >
        <ChevronDown v-if="expanded" :size="12" :stroke-width="3" />
        <ChevronRight v-else :size="12" :stroke-width="3" />
      </button>
      <span v-else class="w-3"></span>
      <FolderIcon :size="16" class="text-yellow-500" fill="currentColor" />
      <span class="flex-1 truncate text-sm text-gray-700">{{ folder.name }}</span>
    </div>

    <!-- v-show keeps the list element, so it stays registered with Sortable while collapsed. -->
    <div v-show="expanded" ref="childList" class="sidebar-list ml-4" :data-folder-id="folder.id">
      <SidebarCalendarItem
        v-for="item in calendars"
        :key="item.calendar.id"
        :item="item"
        :selected="store.selectedId === item.calendar.id"
        @select="emit('select', $event)"
        @context-menu="(event, calendar) => emit('calendarMenu', event, calendar)"
      />
      <FolderTreeItem
        v-for="child in childFolders"
        :key="child.id"
        :folder="child"
        :on-sort-end="onSortEnd"
        @select="emit('select', $event)"
        @folder-menu="(event, folder) => emit('folderMenu', event, folder)"
        @calendar-menu="(event, item) => emit('calendarMenu', event, item)"
      />
    </div>
  </div>
</template>
