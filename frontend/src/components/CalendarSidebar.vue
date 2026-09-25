<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { Settings } from 'lucide-vue-next'
import IconButton from './IconButton.vue'
import FolderTreeItem from './FolderTreeItem.vue'
import { useCalendarStore } from '@/stores/calendars'
import { useThemeStore } from '@/stores/theme'
import { confirm, prompt } from '@/services/dialog'
import type { CalendarListItem } from '@/api'

const store = useCalendarStore()
const themeStore = useThemeStore()
const router = useRouter()
const { t } = useI18n()

onMounted(() => {
  store.load()
})

const topFolders = computed(() => store.folders.filter((f) => !f.parent_id))
const ungrouped = computed(() => store.items.filter((i) => !i.membership.folder_id))

function calendarColor(calendar: CalendarListItem['calendar']) {
  return themeStore.resolved === 'dark' ? calendar.dark_color : calendar.color
}

function calendarsInFolder(folderId: string | null) {
  return store.items.filter((i) => i.membership.folder_id === folderId)
}

function childFolders(parentId: string | null) {
  return store.folders.filter((f) => f.parent_id === parentId)
}

async function createCalendar() {
  const name = await prompt(
    t('app.calendarNamePrompt'),
    '',
    t('app.newCalendar'),
  )
  if (!name) return
  await store.create(name)
}

async function createFolder() {
  const name = await prompt(
    t('app.folderNamePrompt'),
    '',
    t('app.createFolder'),
  )
  if (!name) return
  const { useAuthStore } = await import('@/stores/auth')
  const auth = useAuthStore()
  if (!auth.token) return
  const { createFolder: apiCreate } = await import('@/api')
  await apiCreate(auth.token, name)
  await store.load()
}

function selectCalendar(id: string) {
  store.select(id)
  router.push('/calendar')
}

function selectFolder(id: string) {
  store.select(id)
  router.push('/calendar')
}

function gotoSettings(item: CalendarListItem) {
  router.push(`/settings/${item.calendar.id}`)
}

async function deleteFolder(id: string) {
  const ok = await confirm(t('app.deleteFolderText'), t('app.deleteFolderTitle'))
  if (!ok) return
  const { useAuthStore } = await import('@/stores/auth')
  const auth = useAuthStore()
  if (!auth.token) return
  const { deleteFolder: apiDelete } = await import('@/api')
  await apiDelete(auth.token, id)
  await store.load()
}
</script>

<template>
  <aside class="w-64 bg-white border-r border-gray-200 flex flex-col">
    <div class="p-4 border-b border-gray-100 flex items-center justify-between">
      <h2 class="font-semibold text-gray-700">{{ $t('app.calendar') }}</h2>
      <button @click="createFolder" class="text-xs text-blue-600 hover:underline">+ {{ $t('app.createFolder') }}</button>
    </div>

    <div class="flex-1 overflow-y-auto p-2 space-y-1">
      <div
        @click="selectCalendar('all')"
        class="flex items-center gap-2 px-2 py-1 rounded cursor-pointer"
        :class="{ 'bg-blue-100': store.allSelected }"
      >
        <svg class="w-4 h-4 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
          <path d="M6 2a1 1 0 00-1 1v1H4a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2h-1V3a1 1 0 10-2 0v1H7V3a1 1 0 00-1-1zm0 5a1 1 0 000 2h8a1 1 0 100-2H6z" />
        </svg>
        <span class="text-sm font-medium text-gray-700">{{ $t('app.allCalendars') }}</span>
      </div>

      <div v-for="folder in topFolders" :key="folder.id" class="mt-1">
        <FolderTreeItem
          :folder="folder"
          :childFolders="childFolders(folder.id)"
          :calendars="calendarsInFolder(folder.id)"
          :selectedId="store.selectedId"
          @select-calendar="selectCalendar"
          @select-folder="selectFolder"
          @delete-folder="deleteFolder"
        />
      </div>

      <div
        v-for="item in ungrouped"
        :key="item.calendar.id"
        @click="selectCalendar(item.calendar.id)"
        class="flex items-center gap-2 px-2 py-1 rounded cursor-pointer group"
        :class="{ 'bg-blue-100': store.selectedId === item.calendar.id }"
      >
        <span
          class="w-3 h-3 rounded-full border border-white shadow-sm"
          :style="{ backgroundColor: calendarColor(item.calendar) }"
        ></span>
        <span class="text-sm text-gray-700 truncate flex-1">{{ item.calendar.name }}</span>
        <span class="text-[10px] uppercase text-gray-400">{{ item.membership.role }}</span>
        <IconButton
          v-if="item.membership.role === 'owner'"
          @click.stop="gotoSettings(item)"
          class="opacity-0 group-hover:opacity-100 group-focus-within:opacity-100"
          :label="$t('app.settings')"
        >
          <Settings :size="17" :stroke-width="2.25" />
        </IconButton>
      </div>
    </div>

    <div class="p-3 border-t border-gray-100">
      <button
        @click="createCalendar"
        class="w-full py-2 px-3 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition"
      >
        {{ $t('app.newCalendar') }}
      </button>
    </div>
  </aside>
</template>
