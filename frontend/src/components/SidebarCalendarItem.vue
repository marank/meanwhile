<script setup lang="ts">
import { computed } from 'vue'
import { EllipsisVertical } from '@lucide/vue'
import type { CalendarListItem } from '@/api'
import { hasRole } from '@/services/roles'
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

// The same calendars CalendarSidebar's menu has entries for: one added from the public ones (to remove
// it again), or one the user manages (rename, settings, delete).
const hasMenu = computed(() => props.item.access === 'public' || hasRole(props.item.membership.role, 'manage'))

function openContextMenu(event: MouseEvent) {
  emit('select', props.item.calendar.id)
  emit('contextMenu', event, props.item)
}
</script>

<template>
  <div
    class="sidebar-item group flex h-8 cursor-pointer items-center gap-2 rounded px-2 py-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
    :class="{ 'bg-blue-100 dark:bg-blue-900': selected }"
    role="button"
    tabindex="0"
    :aria-current="selected || undefined"
    data-type="calendar"
    :data-id="item.calendar.id"
    @click="emit('select', item.calendar.id)"
    @keydown.enter.space.self.prevent="emit('select', item.calendar.id)"
    @contextmenu.stop.prevent="openContextMenu"
  >
    <span
      class="mx-0.5 h-3 w-3 shrink-0 rounded-full border border-white shadow-sm"
      :style="{ backgroundColor: theme.isDark ? item.calendar.dark_event_color : item.calendar.event_color }"
    ></span>
    <span class="flex-1 truncate text-sm text-gray-700">{{ item.calendar.name }}</span>
    <!-- The context menu, for who doesn't right-click (or can't, on a phone). Shown on the selected
         calendar, on hover and on touch screens, which have no hover. -->
    <button
      v-if="hasMenu"
      type="button"
      class="sidebar-no-drag -mr-1 rounded p-0.5 text-gray-400 hover:text-gray-700 focus:outline-none focus-visible:opacity-100 focus-visible:ring-2 focus-visible:ring-blue-500 group-hover:opacity-100 [@media(hover:none)]:opacity-100"
      :class="selected ? 'opacity-100' : 'opacity-0'"
      :aria-label="$t('app.calendarActions', { name: item.calendar.name })"
      :title="$t('app.calendarActions', { name: item.calendar.name })"
      aria-haspopup="menu"
      @click.stop="openContextMenu"
    >
      <EllipsisVertical :size="16" :stroke-width="2.25" />
    </button>
  </div>
</template>
