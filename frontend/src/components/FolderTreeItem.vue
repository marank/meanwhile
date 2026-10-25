<script setup lang="ts">
import { computed } from 'vue'
import { ChevronDown, ChevronRight, Folder as FolderIcon } from 'lucide-vue-next'
import type { CalendarListItem, Folder } from '@/api'
import SidebarCalendarItem from './SidebarCalendarItem.vue'
import { useCalendarStore } from '@/stores/calendars'
import { collapsedFolders, dropTargetFolderId } from '@/services/sidebarState'

const props = defineProps<{
  folder: Folder
}>()

const emit = defineEmits<{
  select: [id: string]
  folderMenu: [event: MouseEvent, folder: Folder]
  calendarMenu: [event: MouseEvent, item: CalendarListItem]
}>()

const store = useCalendarStore()
const expanded = computed({
  get: () => !collapsedFolders.has(props.folder.id),
  set: (open: boolean) => {
    if (open) collapsedFolders.delete(props.folder.id)
    else collapsedFolders.add(props.folder.id)
  },
})
const children = computed(() => store.childrenOf(props.folder.id))
const hasChildren = computed(() => children.value.length > 0)

function openContextMenu(event: MouseEvent) {
  emit('select', props.folder.id)
  emit('folderMenu', event, props.folder)
}
</script>

<template>
  <div class="sidebar-item" data-type="folder" :data-id="folder.id">
    <div
      class="flex h-8 cursor-pointer items-center gap-2 rounded px-2 py-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
      :class="{
        'bg-blue-100 dark:bg-blue-900': store.selectedId === folder.id,
        'bg-blue-50 ring-2 ring-blue-500 dark:bg-blue-950': dropTargetFolderId === folder.id,
      }"
      role="button"
      tabindex="0"
      :aria-current="store.selectedId === folder.id || undefined"
      :data-drop-target="dropTargetFolderId === folder.id || undefined"
      @click="emit('select', folder.id)"
      @keydown.enter.space.self.prevent="emit('select', folder.id)"
      @keydown.right.self.prevent="expanded = true"
      @keydown.left.self.prevent="expanded = false"
      @contextmenu.stop.prevent="openContextMenu"
    >
      <FolderIcon :size="16" class="shrink-0 text-yellow-500" fill="currentColor" />
      <span class="flex-1 truncate text-sm text-gray-700">{{ folder.name }}</span>
      <!-- At the end of the row, so that folders and calendars start in the same column. -->
      <button
        v-if="hasChildren"
        type="button"
        class="sidebar-no-drag text-gray-400 hover:text-gray-600 focus:outline-none"
        :aria-expanded="expanded"
        :aria-label="expanded ? $t('app.collapse') : $t('app.expand')"
        @click.stop="expanded = !expanded"
      >
        <ChevronDown v-if="expanded" :size="14" :stroke-width="2.5" />
        <ChevronRight v-else :size="14" :stroke-width="2.5" />
      </button>
    </div>

    <!-- v-show keeps the list element, which the drag and drop looks up by its folder id. -->
    <div v-show="expanded" class="sidebar-list ml-4" :data-folder-id="folder.id">
      <template v-for="child in children" :key="child.id">
        <FolderTreeItem
          v-if="child.type === 'folder'"
          :folder="child.folder"
          @select="emit('select', $event)"
          @folder-menu="(event, folder) => emit('folderMenu', event, folder)"
          @calendar-menu="(event, item) => emit('calendarMenu', event, item)"
        />
        <SidebarCalendarItem
          v-else
          :item="child.item"
          :selected="store.selectedId === child.id"
          @select="emit('select', $event)"
          @context-menu="(event, calendar) => emit('calendarMenu', event, calendar)"
        />
      </template>
    </div>
  </div>
</template>
