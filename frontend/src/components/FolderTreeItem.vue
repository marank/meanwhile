<script setup lang="ts">
import { computed, ref } from 'vue'
import type { CalendarListItem, Folder } from '@/api'
import { useThemeStore } from '@/stores/theme'

const props = defineProps<{
  folder: Folder
  childFolders: Folder[]
  calendars: CalendarListItem[]
  selectedId: string
}>()

const emit = defineEmits<{
  (e: 'select-calendar', id: string): void
  (e: 'select-folder', id: string): void
  (e: 'delete-folder', id: string): void
}>()

const themeStore = useThemeStore()
const expanded = ref(true)
const isSelected = computed(() => props.selectedId === props.folder.id)

function childrenOf(parentId: string | null): Folder[] {
  return props.childFolders.filter((f) => f.parent_id === parentId)
}
</script>

<template>
  <div class="ml-2">
    <div
      class="flex items-center gap-1 px-2 py-1 rounded cursor-pointer group"
      :class="{ 'bg-blue-100': isSelected }"
      @click="emit('select-folder', folder.id)"
    >
      <button
        @click.stop="expanded = !expanded"
        class="text-gray-400 hover:text-gray-600 focus:outline-none"
        v-if="childFolders.length || calendars.length"
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
      <button
        @click.stop="emit('delete-folder', folder.id)"
        class="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-600 p-1"
        title="Delete"
      >
        ×
      </button>
    </div>

    <div v-if="expanded" class="ml-4">
      <div
        v-for="item in calendars"
        :key="item.calendar.id"
        @click="emit('select-calendar', item.calendar.id)"
        class="flex items-center gap-2 px-2 py-1 rounded cursor-pointer"
        :class="{ 'bg-blue-100': selectedId === item.calendar.id }"
      >
        <span
          class="w-3 h-3 rounded-full border border-white shadow-sm"
          :style="{ backgroundColor: themeStore.resolved === 'dark' ? item.calendar.dark_color : item.calendar.color }"
        ></span>
        <span class="text-sm text-gray-700 truncate flex-1">{{ item.calendar.name }}</span>
        <span class="text-[10px] uppercase text-gray-400">{{ item.membership.role }}</span>
      </div>
      <FolderTreeItem
        v-for="child in childrenOf(folder.id)"
        :key="child.id"
        :folder="child"
        :childFolders="childFolders.filter((f) => f.parent_id === child.id)"
        :calendars="[]"
        :selectedId="selectedId"
        @select-calendar="emit('select-calendar', $event)"
        @select-folder="emit('select-folder', $event)"
        @delete-folder="emit('delete-folder', $event)"
      />
    </div>
  </div>
</template>
