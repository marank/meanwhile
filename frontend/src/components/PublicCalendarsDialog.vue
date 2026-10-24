<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Search } from 'lucide-vue-next'
import * as api from '@/api'
import AppModal from '@/components/AppModal.vue'
import { useAction } from '@/composables/useAction'
import { useCalendarStore } from '@/stores/calendars'

const emit = defineEmits<{
  close: []
}>()

const store = useCalendarStore()
const { busy, run } = useAction()

/** Public calendars one isn't a member of; null while loading. */
const calendars = ref<api.PublicCalendar[] | null>(null)
const query = ref('')

onMounted(() => run(async () => (calendars.value = await api.listPublicCalendars())))

const shown = computed(() => {
  const q = query.value.trim().toLowerCase()
  return (calendars.value ?? []).filter((calendar) =>
    [calendar.name, calendar.description, calendar.owner_name].some((text) => text.toLowerCase().includes(q)),
  )
})

/** Adds the calendar to the sidebar, or takes it out again. */
function toggle(calendar: api.PublicCalendar) {
  return run(async () => {
    await (calendar.added ? api.removePublicCalendar(calendar.id) : api.addPublicCalendar(calendar.id))
    calendar.added = !calendar.added
    await store.load()
  })
}
</script>

<template>
  <AppModal open size="xl" :title="$t('app.publicCalendars')" @close="emit('close')">
    <p class="mb-4 text-sm text-gray-500">{{ $t('app.publicCalendarsHint') }}</p>

    <div v-if="calendars?.length" class="relative mb-3">
      <Search :size="16" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
      <input
        v-model="query"
        type="search"
        :placeholder="$t('app.searchPublicCalendars')"
        :aria-label="$t('app.searchPublicCalendars')"
        class="w-full rounded-lg border py-2 pl-9 pr-3 text-sm"
      />
    </div>

    <p v-if="calendars === null" class="text-sm text-gray-500">{{ $t('app.loading') }}</p>
    <p v-else-if="!calendars.length" class="text-sm text-gray-500">{{ $t('app.noPublicCalendars') }}</p>
    <p v-else-if="!shown.length" class="text-sm text-gray-500">{{ $t('app.noSearchResults') }}</p>
    <ul v-else class="divide-y divide-line rounded-lg border border-line">
      <li v-for="calendar in shown" :key="calendar.id" class="flex items-center gap-3 px-4 py-3">
        <div class="min-w-0 flex-1">
          <div class="truncate text-sm font-medium text-gray-800">{{ calendar.name }}</div>
          <div class="truncate text-xs text-gray-500">
            {{ $t('app.publicCalendarOwner', { name: calendar.owner_name }) }}
            <template v-if="calendar.description"> · {{ calendar.description }}</template>
          </div>
        </div>
        <button
          type="button"
          :disabled="busy"
          class="shrink-0 rounded-lg px-3 py-1.5 text-sm disabled:opacity-50"
          :class="calendar.added ? 'border border-line hover:bg-hover' : 'bg-blue-600 text-white hover:bg-blue-700'"
          @click="toggle(calendar)"
        >
          {{ calendar.added ? $t('app.removeFromSidebar') : $t('app.addToSidebar') }}
        </button>
      </li>
    </ul>
  </AppModal>
</template>
