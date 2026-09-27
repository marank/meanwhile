<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ChevronLeft, Pencil, Trash2 } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useCalendarStore } from '@/stores/calendars'
import { useI18n } from 'vue-i18n'
import IconButton from '@/components/IconButton.vue'
import { confirm } from '@/services/dialog'
import * as api from '@/api'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const calendarStore = useCalendarStore()
const { t } = useI18n()

const calendarId = computed(() => route.params.calendarId as string)
const tab = ref<'general' | 'members' | 'categories' | 'resources' | 'approvers' | 'share'>('general')

const calendar = ref<api.Calendar | null>(null)
const items = ref<api.CalendarListItem[]>([])
const members = ref<api.CalendarMember[]>([])
const categories = ref<api.Category[]>([])
const resources = ref<api.Resource[]>([])
const approvers = ref<api.Approver[]>([])
const feedUrl = ref('')
const search = ref('')
const searchResults = ref<api.User[]>([])
const newRole = ref('contributor')
const membership = computed(() => items.value.find((i) => i.calendar.id === calendarId.value)?.membership)
const canManage = computed(() => membership.value?.role === 'owner')

const weekdayChoices = [
  { value: 0, key: 'sunday' },
  { value: 1, key: 'monday' },
  { value: 2, key: 'tuesday' },
  { value: 3, key: 'wednesday' },
  { value: 4, key: 'thursday' },
  { value: 5, key: 'friday' },
  { value: 6, key: 'saturday' },
]
const orderedWeekendChoices = computed(() => {
  const firstWeekday = calendar.value?.first_weekday ?? 0
  return [...weekdayChoices.slice(firstWeekday), ...weekdayChoices.slice(0, firstWeekday)]
})

const categoryFormMode = ref<'list' | 'add' | 'edit'>('list')
const categoryForm = ref({ id: null as string | null, name: '', description: '', color: '#64748b' })
const resourceFormMode = ref<'list' | 'add' | 'edit'>('list')
const resourceForm = ref({
  id: null as string | null,
  name: '',
  description: '',
  color: '#f59e0b',
  requires_approval: false,
  is_active: true,
})

async function load() {
  if (!auth.token) return
  try {
    items.value = await api.listCalendars(auth.token)
    const item = items.value.find((i) => i.calendar.id === calendarId.value)
    calendar.value = item?.calendar || null
    members.value = await api.listMembers(auth.token, calendarId.value)
    categories.value = await api.listCategories(auth.token, calendarId.value)
    resources.value = await api.listResources(auth.token, calendarId.value)
    approvers.value = await api.listCalendarApprovers(auth.token, calendarId.value)
    feedUrl.value = (await api.getFeedUrl(auth.token, calendarId.value)).feed_url
  } catch (e) {
    console.error(e)
  }
}

onMounted(load)
watch(calendarId, load)

async function toggleWeekendDay(day: number) {
  if (!calendar.value || !canManage.value) return
  calendar.value.weekend_days = calendar.value.weekend_days.includes(day)
    ? calendar.value.weekend_days.filter((value) => value !== day)
    : [...calendar.value.weekend_days, day]
  await updateCalendarSettings()
}

function goToCalendar() {
  calendarStore.select(calendarId.value)
  router.push('/calendar')
}

async function updateCalendarSettings() {
  if (!auth.token || !calendar.value || !canManage.value) return
  calendar.value = await api.updateCalendar(auth.token, calendarId.value, {
    color: calendar.value.color,
    dark_color: calendar.value.dark_color,
    force_all_day: calendar.value.force_all_day,
    first_weekday: calendar.value.first_weekday,
    show_weekends: calendar.value.show_weekends,
    weekend_days: calendar.value.weekend_days,
    show_week_numbers: calendar.value.show_week_numbers,
    today_color: calendar.value.today_color,
    dark_today_color: calendar.value.dark_today_color,
    weekend_color: calendar.value.weekend_color,
    dark_weekend_color: calendar.value.dark_weekend_color,
  })
  await calendarStore.load()
}

async function doSearch() {
  if (!auth.token || search.value.length < 2) return
  searchResults.value = await api.searchUsers(auth.token, search.value)
}

async function addMember(userId: string) {
  if (!auth.token) return
  await api.addMember(auth.token, calendarId.value, userId, newRole.value)
  search.value = ''
  searchResults.value = []
  await load()
}

async function removeMember(userId: string) {
  if (!auth.token) return
  const ok = await confirm(t('app.removeMemberText'), t('app.removeMemberTitle'))
  if (!ok) return
  await api.removeMember(auth.token, calendarId.value, userId)
  await load()
}

function startAddCategory() {
  categoryForm.value = { id: null, name: '', description: '', color: '#64748b' }
  categoryFormMode.value = 'add'
}

function startEditCategory(category: api.Category) {
  categoryForm.value = {
    id: category.id,
    name: category.name,
    description: category.description || '',
    color: category.color,
  }
  categoryFormMode.value = 'edit'
}

function cancelCategoryForm() {
  categoryFormMode.value = 'list'
  categoryForm.value = { id: null, name: '', description: '', color: '#64748b' }
}

async function saveCategory() {
  if (!auth.token || !categoryForm.value.name) return
  const data = {
    name: categoryForm.value.name,
    description: categoryForm.value.description || null,
    color: categoryForm.value.color,
  }
  if (categoryForm.value.id) {
    await api.updateCategory(auth.token, categoryForm.value.id, data)
  } else {
    await api.createCategory(auth.token, calendarId.value, data)
  }
  categoryFormMode.value = 'list'
  categoryForm.value = { id: null, name: '', description: '', color: '#64748b' }
  await load()
}

async function deleteCategory(id: string) {
  if (!auth.token) return
  const ok = await confirm(t('app.deleteCategoryText'), t('app.deleteCategoryTitle'))
  if (!ok) return
  await api.deleteCategory(auth.token, id)
  await load()
}

function startAddResource() {
  resourceForm.value = {
    id: null,
    name: '',
    description: '',
    color: '#f59e0b',
    requires_approval: false,
    is_active: true,
  }
  resourceFormMode.value = 'add'
}

function startEditResource(resource: api.Resource) {
  resourceForm.value = {
    id: resource.id,
    name: resource.name,
    description: resource.description || '',
    color: resource.color,
    requires_approval: resource.requires_approval,
    is_active: resource.is_active,
  }
  resourceFormMode.value = 'edit'
}

function cancelResourceForm() {
  resourceFormMode.value = 'list'
  resourceForm.value = {
    id: null,
    name: '',
    description: '',
    color: '#f59e0b',
    requires_approval: false,
    is_active: true,
  }
}

async function saveResource() {
  if (!auth.token || !resourceForm.value.name) return
  const data = {
    name: resourceForm.value.name,
    description: resourceForm.value.description || null,
    color: resourceForm.value.color,
    requires_approval: resourceForm.value.requires_approval,
    is_active: resourceForm.value.is_active,
  }
  if (resourceForm.value.id) {
    await api.updateResource(auth.token, resourceForm.value.id, data)
  } else {
    await api.createResource(auth.token, calendarId.value, data)
  }
  resourceFormMode.value = 'list'
  resourceForm.value = {
    id: null,
    name: '',
    description: '',
    color: '#f59e0b',
    requires_approval: false,
    is_active: true,
  }
  await load()
}

async function deleteResource(id: string) {
  if (!auth.token) return
  const ok = await confirm(t('app.deleteResourceText'), t('app.deleteResourceTitle'))
  if (!ok) return
  await api.deleteResource(auth.token, id)
  await load()
}

async function addApprover(userId: string) {
  if (!auth.token) return
  await api.addCalendarApprover(auth.token, calendarId.value, userId)
  search.value = ''
  searchResults.value = []
  await load()
}

async function removeApprover(userId: string) {
  if (!auth.token) return
  await api.removeCalendarApprover(auth.token, calendarId.value, userId)
  await load()
}

async function rotateFeed() {
  if (!auth.token) return
  const resp = await api.rotateFeedToken(auth.token, calendarId.value)
  feedUrl.value = resp.feed_url
}

const caldavUrl = computed(() => {
  return `${window.location.origin}/caldav/${auth.user?.email}/${calendarId.value}`
})
</script>

<template>
  <div class="max-w-4xl mx-auto p-6">
    <div class="flex items-center gap-3 mb-2">
      <IconButton @click="goToCalendar" :label="$t('app.back')" bordered>
        <ChevronLeft :size="20" :stroke-width="2.25" />
      </IconButton>
      <h1 class="text-2xl font-bold text-gray-800">
        {{ $t('app.settings') }}: {{ calendar?.name }}
      </h1>
    </div>

    <div class="flex gap-2 mb-4 border-b border-gray-200">
      <button
        v-for="t in ['general', 'members', 'categories', 'resources', 'approvers', 'share']"
        :key="t"
        @click="tab = t as any"
        :class="{ 'border-b-2 border-blue-600 text-blue-600': tab === t }"
        class="px-4 py-2 text-sm font-medium text-gray-600 capitalize"
      >
        {{ $t(`app.${t}`) }}
      </button>
    </div>

    <div v-if="tab === 'general'" class="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
      <h2 class="font-semibold text-gray-700">{{ $t('app.calendarBehavior') }}</h2>
      <div v-if="calendar" class="overflow-hidden rounded-lg border border-gray-200">
        <table class="w-full text-sm">
          <thead class="bg-gray-50 text-left text-xs uppercase text-gray-500">
            <tr>
              <th class="px-4 py-2">{{ $t('app.usage') }}</th>
              <th class="px-4 py-2">{{ $t('app.themeLight') }}</th>
              <th class="px-4 py-2">{{ $t('app.themeDark') }}</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            <tr>
              <td class="px-4 py-2 font-medium text-gray-800">{{ $t('app.calendar') }}</td>
              <td class="px-4 py-2"><input v-model="calendar.color" @change="updateCalendarSettings" type="color" :disabled="!canManage" class="h-8 w-14 rounded border border-gray-300" /></td>
              <td class="px-4 py-2"><input v-model="calendar.dark_color" @change="updateCalendarSettings" type="color" :disabled="!canManage" class="h-8 w-14 rounded border border-gray-300" /></td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium text-gray-800">{{ $t('app.today') }}</td>
              <td class="px-4 py-2"><input v-model="calendar.today_color" @change="updateCalendarSettings" type="color" :disabled="!canManage" class="h-8 w-14 rounded border border-gray-300" /></td>
              <td class="px-4 py-2"><input v-model="calendar.dark_today_color" @change="updateCalendarSettings" type="color" :disabled="!canManage" class="h-8 w-14 rounded border border-gray-300" /></td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium text-gray-800">{{ $t('app.weekend') }}</td>
              <td class="px-4 py-2"><input v-model="calendar.weekend_color" @change="updateCalendarSettings" type="color" :disabled="!canManage" class="h-8 w-14 rounded border border-gray-300" /></td>
              <td class="px-4 py-2"><input v-model="calendar.dark_weekend_color" @change="updateCalendarSettings" type="color" :disabled="!canManage" class="h-8 w-14 rounded border border-gray-300" /></td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="calendar" class="border-t border-gray-100 pt-4 space-y-4">
        <h3 class="text-sm font-semibold text-gray-700">{{ $t('app.calendarDisplay') }}</h3>
        <label class="block max-w-sm">
          <span class="block text-sm font-medium text-gray-800 mb-1">{{ $t('app.firstWeekday') }}</span>
          <select v-model.number="calendar.first_weekday" @change="updateCalendarSettings" :disabled="!canManage" class="w-full border rounded-lg px-3 py-2">
            <option :value="0">{{ $t('event.sunday') }}</option>
            <option :value="1">{{ $t('event.monday') }}</option>
            <option :value="2">{{ $t('event.tuesday') }}</option>
            <option :value="3">{{ $t('event.wednesday') }}</option>
            <option :value="4">{{ $t('event.thursday') }}</option>
            <option :value="5">{{ $t('event.friday') }}</option>
            <option :value="6">{{ $t('event.saturday') }}</option>
          </select>
        </label>
        <div>
          <span class="block text-sm font-medium text-gray-800 mb-2">{{ $t('app.weekendDays') }}</span>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="day in orderedWeekendChoices"
              :key="day.value"
              type="button"
              @click="toggleWeekendDay(day.value)"
              :disabled="!canManage"
              class="px-3 py-1.5 rounded-full border text-sm transition-colors disabled:opacity-60"
              :class="calendar.weekend_days.includes(day.value) ? 'bg-blue-600 border-blue-600 text-white' : 'border-gray-300 text-gray-600 hover:bg-gray-50'"
            >
              {{ $t(`event.${day.key}`) }}
            </button>
          </div>
          <p class="text-xs text-gray-500 mt-1">{{ $t('app.weekendDaysHelp') }}</p>
        </div>
        <label class="flex items-start gap-3" :class="canManage ? 'cursor-pointer' : 'opacity-60'">
          <input v-model="calendar.show_weekends" @change="updateCalendarSettings" type="checkbox" :disabled="!canManage" class="mt-1" />
          <span>
            <span class="block text-sm font-medium text-gray-800">{{ $t('app.showWeekends') }}</span>
            <span class="block text-xs text-gray-500 mt-0.5">{{ $t('app.showWeekendsHelp') }}</span>
          </span>
        </label>
        <label class="flex items-start gap-3" :class="canManage ? 'cursor-pointer' : 'opacity-60'">
          <input v-model="calendar.show_week_numbers" @change="updateCalendarSettings" type="checkbox" :disabled="!canManage" class="mt-1" />
          <span>
            <span class="block text-sm font-medium text-gray-800">{{ $t('app.showWeekNumbers') }}</span>
            <span class="block text-xs text-gray-500 mt-0.5">{{ $t('app.showWeekNumbersHelp') }}</span>
          </span>
        </label>
      </div>
      <label class="flex items-start gap-3" :class="canManage ? 'cursor-pointer' : 'opacity-60'">
        <input
          v-if="calendar"
          v-model="calendar.force_all_day"
          @change="updateCalendarSettings"
          type="checkbox"
          :disabled="!canManage"
          class="mt-1"
        />
        <span>
          <span class="block text-sm font-medium text-gray-800">{{ $t('app.forceAllDay') }}</span>
          <span class="block text-xs text-gray-500 mt-0.5">{{ $t('app.forceAllDayHelp') }}</span>
        </span>
      </label>
    </div>

    <!-- Members -->
    <div v-if="tab === 'members'" class="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
      <h2 class="font-semibold text-gray-700">{{ $t('app.members') }}</h2>
      <ul class="divide-y divide-gray-100">
        <li v-for="m in members" :key="m.id" class="py-2 flex items-center justify-between">
          <div>
            <div class="font-medium text-gray-800">{{ m.display_name }} ({{ m.email }})</div>
            <div class="text-xs text-gray-500 capitalize">{{ m.role }}</div>
          </div>
          <button v-if="canManage && m.role !== 'owner'" @click="removeMember(m.user_id)" class="text-red-600 hover:underline text-sm">
            {{ $t('app.delete') }}
          </button>
        </li>
      </ul>

      <div v-if="canManage" class="border-t border-gray-100 pt-4 space-y-2">
        <div class="flex gap-2">
          <input v-model="search" @input="doSearch" placeholder="Search by email..." class="flex-1 border rounded-lg px-3 py-2" />
          <select v-model="newRole" class="border rounded-lg px-3 py-2">
            <option value="viewer">viewer</option>
            <option value="contributor">contributor</option>
            <option value="editor">editor</option>
          </select>
        </div>
        <ul v-if="searchResults.length" class="border rounded-lg divide-y divide-gray-100 max-h-40 overflow-y-auto">
          <li v-for="u in searchResults" :key="u.id" class="px-3 py-2 flex justify-between items-center hover:bg-gray-50">
            <span class="text-sm">{{ u.display_name }} ({{ u.email }})</span>
            <button @click="addMember(u.id)" class="text-blue-600 text-sm hover:underline">{{ $t('app.add') }}</button>
          </li>
        </ul>
      </div>
    </div>

    <div v-if="tab === 'categories'" class="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <div v-if="categoryFormMode === 'list'">
        <div class="px-6 py-4 flex items-center justify-between border-b border-gray-200">
          <h2 class="font-semibold text-gray-700">{{ $t('app.categories') }}</h2>
          <button v-if="canManage" @click="startAddCategory" class="px-3 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">{{ $t('app.add') }}</button>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="bg-gray-50 text-left text-xs uppercase text-gray-500">
              <tr>
                <th class="px-4 py-2 w-16">{{ $t('app.color') }}</th>
                <th class="px-4 py-2">{{ $t('app.nameLabel') }}</th>
                <th class="px-4 py-2">{{ $t('event.description') }}</th>
                <th class="px-4 py-2 text-right">{{ $t('app.actions') }}</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              <tr v-for="category in categories" :key="category.id" class="group hover:bg-gray-50">
                <td class="px-4 py-2"><span class="block w-5 h-5 rounded" :style="{ backgroundColor: category.color }"></span></td>
                <td class="px-4 py-2 font-medium text-gray-800">{{ category.name }}</td>
                <td class="px-4 py-2 text-gray-500">{{ category.description || '—' }}</td>
                <td class="px-4 py-2">
                  <div v-if="canManage" class="flex justify-end gap-1 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity">
                    <IconButton @click="startEditCategory(category)" :label="$t('app.edit')" tone="primary">
                      <Pencil :size="18" :stroke-width="2.25" />
                    </IconButton>
                    <IconButton @click="deleteCategory(category.id)" :label="$t('app.delete')" tone="danger">
                      <Trash2 :size="18" :stroke-width="2.25" />
                    </IconButton>
                  </div>
                </td>
              </tr>
              <tr v-if="!categories.length"><td colspan="4" class="px-6 py-8 text-center text-gray-500">{{ $t('app.noCategories') }}</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-else>
        <div class="px-6 py-4 flex items-center justify-between border-b border-gray-200">
          <h2 class="font-semibold text-gray-700">{{ categoryForm.id ? $t('app.editCategory') : $t('app.addCategory') }}</h2>
          <div class="h-9" aria-hidden="true"></div>
        </div>
        <div class="p-6 space-y-4">
          <label class="block">
            <span class="block text-sm font-medium text-gray-700 mb-1">{{ $t('app.nameLabel') }}</span>
            <input v-model="categoryForm.name" class="w-full border border-gray-300 rounded-lg px-3 py-2" />
          </label>
          <label class="block">
            <span class="block text-sm font-medium text-gray-700 mb-1">{{ $t('event.description') }}</span>
            <textarea v-model="categoryForm.description" rows="3" class="w-full border border-gray-300 rounded-lg px-3 py-2"></textarea>
          </label>
          <label class="block">
            <span class="block text-sm font-medium text-gray-700 mb-1">{{ $t('app.color') }}</span>
            <input v-model="categoryForm.color" type="color" class="h-10 w-16 rounded border border-gray-300" />
          </label>
          <div class="flex justify-end gap-3">
            <button @click="cancelCategoryForm" class="px-4 py-2 rounded-lg border border-gray-300 hover:bg-gray-100">{{ $t('app.cancel') }}</button>
            <button @click="saveCategory" :disabled="!categoryForm.name" class="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50">{{ $t('app.save') }}</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Resources -->
    <div v-if="tab === 'resources'" class="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <div v-if="resourceFormMode === 'list'">
        <div class="px-6 py-4 flex items-center justify-between border-b border-gray-200">
          <h2 class="font-semibold text-gray-700">{{ $t('app.resources') }}</h2>
          <button v-if="canManage" @click="startAddResource" class="px-3 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">{{ $t('app.add') }}</button>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="bg-gray-50 text-left text-xs uppercase text-gray-500">
              <tr>
                <th class="px-4 py-2 w-16">{{ $t('app.color') }}</th>
                <th class="px-4 py-2">{{ $t('app.nameLabel') }}</th>
                <th class="px-4 py-2">{{ $t('event.description') }}</th>
                <th class="px-4 py-2">{{ $t('app.approval') }}</th>
                <th class="px-4 py-2">{{ $t('app.status') }}</th>
                <th class="px-4 py-2 text-right">{{ $t('app.actions') }}</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              <tr v-for="resource in resources" :key="resource.id" class="group hover:bg-gray-50">
                <td class="px-4 py-2"><span class="block w-5 h-5 rounded" :style="{ backgroundColor: resource.color }"></span></td>
                <td class="px-4 py-2 font-medium text-gray-800">{{ resource.name }}</td>
                <td class="px-4 py-2 text-gray-500">{{ resource.description || '—' }}</td>
                <td class="px-4 py-2">{{ resource.requires_approval ? $t('app.required') : $t('app.notRequired') }}</td>
                <td class="px-4 py-2">{{ resource.is_active ? $t('app.active') : $t('app.inactive') }}</td>
                <td class="px-4 py-2">
                  <div v-if="canManage" class="flex justify-end gap-1 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity">
                    <IconButton @click="startEditResource(resource)" :label="$t('app.edit')" tone="primary">
                      <Pencil :size="18" :stroke-width="2.25" />
                    </IconButton>
                    <IconButton @click="deleteResource(resource.id)" :label="$t('app.delete')" tone="danger">
                      <Trash2 :size="18" :stroke-width="2.25" />
                    </IconButton>
                  </div>
                </td>
              </tr>
              <tr v-if="!resources.length"><td colspan="6" class="px-6 py-8 text-center text-gray-500">{{ $t('app.noResources') }}</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-else>
        <div class="px-6 py-4 flex items-center justify-between border-b border-gray-200">
          <h2 class="font-semibold text-gray-700">{{ resourceForm.id ? $t('app.editResource') : $t('app.addResource') }}</h2>
          <div class="h-9" aria-hidden="true"></div>
        </div>
        <div class="p-6 space-y-4">
          <label class="block">
            <span class="block text-sm font-medium text-gray-700 mb-1">{{ $t('app.nameLabel') }}</span>
            <input v-model="resourceForm.name" class="w-full border border-gray-300 rounded-lg px-3 py-2" />
          </label>
          <label class="block">
            <span class="block text-sm font-medium text-gray-700 mb-1">{{ $t('event.description') }}</span>
            <textarea v-model="resourceForm.description" rows="3" class="w-full border border-gray-300 rounded-lg px-3 py-2"></textarea>
          </label>
          <label class="block">
            <span class="block text-sm font-medium text-gray-700 mb-1">{{ $t('app.color') }}</span>
            <input v-model="resourceForm.color" type="color" class="h-10 w-16 rounded border border-gray-300" />
          </label>
          <label class="flex items-center gap-2 text-sm">
            <input v-model="resourceForm.requires_approval" type="checkbox" />
            {{ $t('app.requiresApproval') }}
          </label>
          <label class="flex items-center gap-2 text-sm">
            <input v-model="resourceForm.is_active" type="checkbox" />
            {{ $t('app.active') }}
          </label>
          <div class="flex justify-end gap-3">
            <button @click="cancelResourceForm" class="px-4 py-2 rounded-lg border border-gray-300 hover:bg-gray-100">{{ $t('app.cancel') }}</button>
            <button @click="saveResource" :disabled="!resourceForm.name" class="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50">{{ $t('app.save') }}</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Approvers -->
    <div v-if="tab === 'approvers'" class="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
      <h2 class="font-semibold text-gray-700">{{ $t('app.approvers') }}</h2>
      <ul class="divide-y divide-gray-100">
        <li v-for="a in approvers" :key="a.user_id" class="py-2 flex items-center justify-between">
          <div class="font-medium text-gray-800">{{ a.display_name }} ({{ a.email }})</div>
          <button v-if="canManage" @click="removeApprover(a.user_id)" class="text-red-600 hover:underline text-sm">{{ $t('app.delete') }}</button>
        </li>
      </ul>
      <div v-if="canManage" class="border-t border-gray-100 pt-4 space-y-2">
        <input v-model="search" @input="doSearch" placeholder="Search member..." class="w-full border rounded-lg px-3 py-2" />
        <ul v-if="searchResults.length" class="border rounded-lg divide-y divide-gray-100 max-h-40 overflow-y-auto">
          <li v-for="u in searchResults" :key="u.id" class="px-3 py-2 flex justify-between items-center hover:bg-gray-50">
            <span class="text-sm">{{ u.display_name }} ({{ u.email }})</span>
            <button @click="addApprover(u.id)" class="text-blue-600 text-sm hover:underline">{{ $t('app.add') }}</button>
          </li>
        </ul>
      </div>
    </div>

    <!-- Share -->
    <div v-if="tab === 'share'" class="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
      <div>
        <h2 class="font-semibold text-gray-700 mb-1">{{ $t('app.feedUrl') }}</h2>
        <code class="block bg-gray-50 border rounded-lg p-3 text-sm break-all">{{ feedUrl }}</code>
        <button @click="rotateFeed" class="mt-2 text-sm text-blue-600 hover:underline">Regenerate token</button>
      </div>
      <div>
        <h2 class="font-semibold text-gray-700 mb-1">{{ $t('app.caldavUrl') }}</h2>
        <code class="block bg-gray-50 border rounded-lg p-3 text-sm break-all">{{ caldavUrl }}</code>
      </div>
    </div>

  </div>
</template>
