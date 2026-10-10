<script setup lang="ts">
import type { CalendarListItem } from '@/api'
import { useThemeStore } from '@/stores/theme'

const props = defineProps<{
  item: CalendarListItem
  selected: boolean
}>()

const emit = defineEmits<{
  select: [id: string]
  contextMenu: [event: MouseEvent, item: CalendarListItem]
}>()

const theme = useThemeStore()

function openContextMenu(event: MouseEvent) {
  emit('select', props.item.calendar.id)
  emit('contextMenu', event, props.item)
}
</script>

<template>
  <div
    class="sidebar-item flex h-8 cursor-pointer items-center gap-2 rounded px-2 py-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
    :class="{ 'bg-blue-100 dark:bg-blue-900': selected }"
    role="button"
    tabindex="0"
    :aria-current="selected || undefined"
    data-type="calendar"
    :data-id="item.calendar.id"
    @click="emit('select', item.calendar.id)"
    @keydown.enter.space.prevent="emit('select', item.calendar.id)"
    @contextmenu.stop.prevent="openContextMenu"
  >
    <span
      class="h-3 w-3 rounded-full border border-white shadow-sm"
      :style="{ backgroundColor: theme.isDark ? item.calendar.dark_event_color : item.calendar.event_color }"
    ></span>
    <span class="flex-1 truncate text-sm text-gray-700">{{ item.calendar.name }}</span>
  </div>
</template>
