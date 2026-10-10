<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Pencil, Plus, RotateCw, Trash2, X } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useCalendarStore } from '@/stores/calendars'
import { useI18n } from 'vue-i18n'
import ColorPaletteSelect from '@/components/ColorPaletteSelect.vue'
import IconButton from '@/components/IconButton.vue'
import SearchableSelect from '@/components/SearchableSelect.vue'
import SettingsPage from '@/components/SettingsPage.vue'
import SettingsPanel from '@/components/SettingsPanel.vue'
import SettingsToggle from '@/components/SettingsToggle.vue'
import { confirm } from '@/services/dialog'
import { errorMessage, toast } from '@/services/toast'
import { calendarColorPalettes, type CalendarColorPalette } from '@/services/calendarColors'
import * as api from '@/api'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const calendarStore = useCalendarStore()
const { locale, t } = useI18n()

type Tab = 'general' | 'access' | 'categories' | 'resources' | 'share'
const validTabs: Tab[] = ['general', 'access', 'categories', 'resources', 'share']
const calendarId = computed(() => route.params.calendarId as string)
const tab = computed<Tab>(() => validTabs.includes(route.query.tab as Tab) ? route.query.tab as Tab : 'general')
const tabs = computed(() => validTabs.map((id) => ({ id, label: t(`app.${id}`) })))
const loading = ref(true)
const busy = ref(false)

function selectTab(id: string) {
  if (!validTabs.includes(id as Tab)) return
  categoryFormMode.value = 'list'
  resourceFormMode.value = 'list'
  router.push({ query: { ...route.query, tab: id } })
}

const calendar = ref<api.Calendar | null>(null)
const calendarForm = ref<Partial<api.Calendar> | null>(null)
const items = ref<api.CalendarListItem[]>([])
const members = ref<api.CalendarMember[]>([])
const categories = ref<api.Category[]>([])
const resources = ref<api.Resource[]>([])
const approvers = ref<api.Approver[]>([])
const feedUrl = ref('')
const selectedMemberId = ref<string | null>(null)
const selectedApproverId = ref<string | null>(null)
const selectedResourceApproverId = ref<string | null>(null)
const newRole = ref('contributor')
const calendarGroups = ref<api.CalendarGroupLink[]>([])
const newGroupId = ref<string | null>(null)
const newGroupRole = ref('viewer')
const membership = computed(() => items.value.find((i) => i.calendar.id === calendarId.value)?.membership)
const canManage = computed(() => membership.value?.role === 'owner')
const defaultApproverNames = computed(() => approvers.value.map((a) => a.display_name).join(', '))

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
  const firstWeekday = calendarForm.value?.first_weekday ?? calendar.value?.first_weekday ?? 0
  return [...weekdayChoices.slice(firstWeekday), ...weekdayChoices.slice(0, firstWeekday)]
})

function paletteMatches(palette: CalendarColorPalette) {
  return calendarForm.value?.color === palette.light.calendar
    && calendarForm.value?.today_color === palette.light.today
    && calendarForm.value?.weekend_color === palette.light.weekend
    && calendarForm.value?.dark_color === palette.dark.calendar
    && calendarForm.value?.dark_today_color === palette.dark.today
    && calendarForm.value?.dark_weekend_color === palette.dark.weekend
}

const selectedPaletteId = computed(() => calendarColorPalettes.find(paletteMatches)?.id ?? null)

const colorPaletteOptions = computed(() => calendarColorPalettes.map((palette) => ({
  id: palette.id,
  label: locale.value.startsWith('de') ? palette.name.de : palette.name.en,
  colors: [palette.light.calendar, palette.light.today, palette.light.weekend],
})))

function applyColorPalette(id: string) {
  if (!calendarForm.value || !canManage.value) return
  const palette = calendarColorPalettes.find((item) => item.id === id)
  if (!palette) return
  calendarForm.value.color = palette.light.calendar
  calendarForm.value.today_color = palette.light.today
  calendarForm.value.weekend_color = palette.light.weekend
  calendarForm.value.dark_color = palette.dark.calendar
  calendarForm.value.dark_today_color = palette.dark.today
  calendarForm.value.dark_weekend_color = palette.dark.weekend
}

const categoryFormMode = ref<'list' | 'add' | 'edit'>('list')
const categoryForm = ref({ id: null as string | null, name: '', description: '', color: '#64748b' })
const resourceFormMode = ref<'list' | 'add' | 'edit'>('list')
type ResourceFormState = {
  id: string | null
  name: string
  description: string
  color: string
  requires_approval: boolean
  is_active: boolean
  approval_mode: 'default' | 'custom'
  approvers: api.Approver[]
}

function emptyResourceForm(): ResourceFormState {
  return {
    id: null,
    name: '',
    description: '',
    color: '#f59e0b',
    requires_approval: false,
    is_active: true,
    approval_mode: 'default',
    approvers: [],
  }
}

const resourceForm = ref<ResourceFormState>(emptyResourceForm())
const resourceFormInvalid = computed(() =>
  !resourceForm.value.name
  || (resourceForm.value.requires_approval
    && resourceForm.value.approval_mode === 'custom'
    && !resourceForm.value.approvers.length),
)

async function load() {
  if (!auth.isLoggedIn) return
  loading.value = true
  try {
    items.value = await api.listCalendars()
    const item = items.value.find((i) => i.calendar.id === calendarId.value)
    calendar.value = item?.calendar || null
    if (calendar.value) {
      calendarForm.value = {
        color: calendar.value.color,
        dark_color: calendar.value.dark_color,
        force_all_day: calendar.value.force_all_day,
        first_weekday: calendar.value.first_weekday,
        show_weekends: calendar.value.show_weekends,
        weekend_days: [...calendar.value.weekend_days],
        show_week_numbers: calendar.value.show_week_numbers,
        today_color: calendar.value.today_color,
        dark_today_color: calendar.value.dark_today_color,
        weekend_color: calendar.value.weekend_color,
        dark_weekend_color: calendar.value.dark_weekend_color,
        is_public: calendar.value.is_public,
        public_role: calendar.value.public_role,
      }
    }
    members.value = await api.listMembers(calendarId.value)
    calendarGroups.value = await api.listCalendarGroups(calendarId.value)
    categories.value = await api.listCategories(calendarId.value)
    resources.value = await api.listResources(calendarId.value)
    approvers.value = await api.listCalendarApprovers(calendarId.value)
    feedUrl.value = (await api.getFeedUrl(calendarId.value)).feed_url
  } catch (error) {
    toast.error(errorMessage(error, t('app.loadFailed')))
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(calendarId, load)
watch(() => route.query.tab, (value) => {
  if (value && !validTabs.includes(value as Tab)) router.replace({ query: { ...route.query, tab: 'general' } })
})

function toggleWeekendDay(day: number) {
  if (!calendarForm.value || !canManage.value) return
  const current = calendarForm.value.weekend_days || []
  calendarForm.value.weekend_days = current.includes(day)
    ? current.filter((value) => value !== day)
    : [...current, day]
}

function goToCalendar() {
  calendarStore.select(calendarId.value)
  router.push('/calendar')
}

async function perform(action: () => Promise<void>, success: string) {
  if (busy.value) return
  busy.value = true
  try {
    await action()
    toast.success(success)
  } catch (error) {
    toast.error(errorMessage(error, t('app.actionFailed')))
  } finally {
    busy.value = false
  }
}

async function saveGeneralSettings() {
  if (!auth.isLoggedIn || !calendar.value || !calendarForm.value || !canManage.value || busy.value) return
  busy.value = true
  try {
    calendar.value = await api.updateCalendar(calendarId.value, {
      color: calendarForm.value.color,
      dark_color: calendarForm.value.dark_color,
      force_all_day: calendarForm.value.force_all_day,
      first_weekday: calendarForm.value.first_weekday,
      show_weekends: calendarForm.value.show_weekends,
      weekend_days: calendarForm.value.weekend_days,
      show_week_numbers: calendarForm.value.show_week_numbers,
      today_color: calendarForm.value.today_color,
      dark_today_color: calendarForm.value.dark_today_color,
      weekend_color: calendarForm.value.weekend_color,
      dark_weekend_color: calendarForm.value.dark_weekend_color,
    })
    toast.success(t('app.calendarSettingsSaved'))
  } catch (error) {
    toast.error(errorMessage(error, t('app.saveFailed')))
  } finally {
    busy.value = false
  }
}

async function saveAccessSettings() {
  if (!auth.isLoggedIn || !calendar.value || !calendarForm.value || !canManage.value || busy.value) return
  busy.value = true
  try {
    const data: Partial<api.Calendar> = { is_public: calendarForm.value.is_public }
    if (calendarForm.value.is_public) data.public_role = calendarForm.value.public_role
    calendar.value = await api.updateCalendar(calendarId.value, data)
    toast.success(t('app.accessSettingsSaved'))
  } catch (error) {
    toast.error(errorMessage(error, t('app.saveFailed')))
  } finally {
    busy.value = false
  }
}

async function addMember() {
  if (!auth.isLoggedIn || !selectedMemberId.value) return
  const userId = selectedMemberId.value
  await perform(async () => {
    await api.addMember(calendarId.value, userId, newRole.value)
    selectedMemberId.value = null
    await load()
  }, t('app.memberAdded'))
}

async function removeMember(userId: string) {
  if (!auth.isLoggedIn) return
  const ok = await confirm(t('app.removeMemberText'), t('app.removeMemberTitle'))
  if (!ok) return
  await perform(async () => {
    await api.removeMember(calendarId.value, userId)
    await load()
  }, t('app.memberRemoved'))
}

async function addCalendarGroupLink() {
  if (!auth.isLoggedIn || !newGroupId.value) return
  await api.addCalendarGroup(calendarId.value, {
    group_id: newGroupId.value,
    role: newGroupRole.value,
  })
  await load()
}

async function updateCalendarGroupLink(linkId: string, event: Event) {
  if (!auth.isLoggedIn) return
  const target = event.target as HTMLSelectElement
  await api.updateCalendarGroup(calendarId.value, linkId, { role: target.value })
  await load()
}

async function removeCalendarGroupLink(linkId: string) {
  if (!auth.isLoggedIn) return
  const ok = await confirm(t('app.removeGroupAccessText'), t('app.removeGroupAccessTitle'))
  if (!ok) return
  await perform(async () => {
    await api.removeCalendarGroup(calendarId.value, linkId)
    await load()
  }, t('app.groupAccessRemoved'))
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
  if (!auth.isLoggedIn || !categoryForm.value.name) return
  const data = {
    name: categoryForm.value.name,
    description: categoryForm.value.description || null,
    color: categoryForm.value.color,
  }
  if (categoryForm.value.id) {
    await api.updateCategory(calendarId.value, categoryForm.value.id, data)
  } else {
    await api.createCategory(calendarId.value, data)
  }
  categoryFormMode.value = 'list'
  categoryForm.value = { id: null, name: '', description: '', color: '#64748b' }
  await load()
}

async function deleteCategory(id: string) {
  if (!auth.isLoggedIn) return
  const ok = await confirm(t('app.deleteCategoryText'), t('app.deleteCategoryTitle'))
  if (!ok) return
  await api.deleteCategory(calendarId.value, id)
  await load()
}

function startAddResource() {
  resourceForm.value = emptyResourceForm()
  selectedResourceApproverId.value = null
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
    approval_mode: resource.approvers.length ? 'custom' : 'default',
    approvers: [...resource.approvers],
  }
  selectedResourceApproverId.value = null
  resourceFormMode.value = 'edit'
}

function cancelResourceForm() {
  resourceFormMode.value = 'list'
  resourceForm.value = emptyResourceForm()
}

function resourceApprovalLabel(resource: api.Resource) {
  if (!resource.requires_approval) return t('app.approvalNone')
  if (resource.approvers.length) return resource.approvers.map((a) => a.display_name).join(', ')
  return `${t('app.approvalDefault')} (${defaultApproverNames.value || t('app.nobody')})`
}

async function onResourceApproverPicked(userId: string | null, option: api.SearchResult | null) {
  if (userId && option && !resourceForm.value.approvers.some((a) => a.user_id === userId)) {
    resourceForm.value.approvers.push({ user_id: userId, display_name: option.label, email: option.subtitle ?? '' })
  }
  // Let the select show the pick for one tick before clearing it for the next search.
  await nextTick()
  selectedResourceApproverId.value = null
}

function removeResourceFormApprover(userId: string) {
  resourceForm.value.approvers = resourceForm.value.approvers.filter((a) => a.user_id !== userId)
}

async function saveResource() {
  if (!auth.isLoggedIn || resourceFormInvalid.value) return
  const form = resourceForm.value
  const data = {
    name: form.name,
    description: form.description || null,
    color: form.color,
    requires_approval: form.requires_approval,
    is_active: form.is_active,
  }
  await perform(async () => {
    const saved = form.id
      ? await api.updateResource(calendarId.value, form.id, data)
      : await api.createResource(calendarId.value, data)
    // Own approvers only apply while approval is required; otherwise the defaults take over.
    const wanted = form.requires_approval && form.approval_mode === 'custom' ? form.approvers : []
    const current = saved.approvers
    for (const approver of wanted) {
      if (!current.some((a) => a.user_id === approver.user_id)) {
        await api.addResourceApprover(calendarId.value, saved.id, approver.user_id)
      }
    }
    for (const approver of current) {
      if (!wanted.some((a) => a.user_id === approver.user_id)) {
        await api.removeResourceApprover(calendarId.value, saved.id, approver.user_id)
      }
    }
    resourceFormMode.value = 'list'
    resourceForm.value = emptyResourceForm()
    await load()
  }, t('app.resourceSaved'))
}

async function deleteResource(id: string) {
  if (!auth.isLoggedIn) return
  const ok = await confirm(t('app.deleteResourceText'), t('app.deleteResourceTitle'))
  if (!ok) return
  await api.deleteResource(calendarId.value, id)
  await load()
}

async function onDefaultApproverPicked(userId: string | null) {
  if (!auth.isLoggedIn || !userId) return
  if (approvers.value.some((a) => a.user_id === userId)) {
    selectedApproverId.value = null
    return
  }
  await perform(async () => {
    await api.addCalendarApprover(calendarId.value, userId)
    await load()
  }, t('app.approverAdded'))
  selectedApproverId.value = null
}

async function removeApprover(userId: string) {
  if (!auth.isLoggedIn) return
  const ok = await confirm(t('app.removeApproverText'), t('app.removeApproverTitle'))
  if (!ok) return
  await perform(async () => {
    await api.removeCalendarApprover(calendarId.value, userId)
    await load()
  }, t('app.approverRemoved'))
}

async function rotateFeed() {
  if (!auth.isLoggedIn) return
  const ok = await confirm(t('app.rotateFeedText'), t('app.rotateFeedTitle'))
  if (!ok) return
  await perform(async () => {
    const resp = await api.rotateFeedToken(calendarId.value)
    feedUrl.value = resp.feed_url
  }, t('app.feedRotated'))
}

const caldavUrl = computed(() => {
  return `${window.location.origin}/caldav/${auth.user?.email}/${calendarId.value}`
})
</script>

<template>
  <SettingsPage :title="`${$t('app.settings')}: ${calendar?.name || ''}`" :tabs="tabs" :active-tab="tab" @back="goToCalendar" @select-tab="selectTab">
    <SettingsPanel v-if="tab === 'general'" :title="$t('app.calendarBehavior')" :description="$t('app.calendarGeneralDescription')" :loading="loading">
      <div class="space-y-6">
      <section v-if="calendarForm" class="space-y-3">
        <div>
          <h3 class="text-sm font-semibold text-gray-800">{{ $t('app.calendarAppearance') }}</h3>
        </div>
        <div class="sm:w-1/2 sm:pr-1.5">
          <ColorPaletteSelect
            :model-value="selectedPaletteId"
            :options="colorPaletteOptions"
            :label="$t('app.colorPresets')"
            :placeholder="$t('app.colorPresetCustom')"
            :disabled="!canManage"
            @update:model-value="applyColorPalette"
          />
        </div>
        <div class="overflow-hidden rounded-lg border border-gray-200">
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
              <td class="px-4 py-2"><input v-model="calendarForm.color" type="color" :disabled="!canManage" class="h-8 w-14 rounded border border-gray-300" /></td>
              <td class="px-4 py-2"><input v-model="calendarForm.dark_color" type="color" :disabled="!canManage" class="h-8 w-14 rounded border border-gray-300" /></td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium text-gray-800">{{ $t('app.today') }}</td>
              <td class="px-4 py-2"><input v-model="calendarForm.today_color" type="color" :disabled="!canManage" class="h-8 w-14 rounded border border-gray-300" /></td>
              <td class="px-4 py-2"><input v-model="calendarForm.dark_today_color" type="color" :disabled="!canManage" class="h-8 w-14 rounded border border-gray-300" /></td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium text-gray-800">{{ $t('app.weekend') }}</td>
              <td class="px-4 py-2"><input v-model="calendarForm.weekend_color" type="color" :disabled="!canManage" class="h-8 w-14 rounded border border-gray-300" /></td>
              <td class="px-4 py-2"><input v-model="calendarForm.dark_weekend_color" type="color" :disabled="!canManage" class="h-8 w-14 rounded border border-gray-300" /></td>
            </tr>
          </tbody>
        </table>
        </div>
      </section>
      <section v-if="calendarForm" class="space-y-4 border-t border-gray-100 pt-6">
        <div>
          <h3 class="text-sm font-semibold text-gray-800">{{ $t('app.calendarDisplay') }}</h3>
        </div>
        <div class="grid gap-3 sm:grid-cols-2">
          <label class="block">
            <span class="mb-1 block text-sm font-medium text-gray-800">{{ $t('app.firstWeekday') }}</span>
            <select v-model.number="calendarForm.first_weekday" :disabled="!canManage" class="w-full rounded-lg border px-3 py-2">
              <option :value="0">{{ $t('event.sunday') }}</option>
              <option :value="1">{{ $t('event.monday') }}</option>
              <option :value="2">{{ $t('event.tuesday') }}</option>
              <option :value="3">{{ $t('event.wednesday') }}</option>
              <option :value="4">{{ $t('event.thursday') }}</option>
              <option :value="5">{{ $t('event.friday') }}</option>
              <option :value="6">{{ $t('event.saturday') }}</option>
            </select>
          </label>
        </div>
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
              :class="(calendarForm.weekend_days || []).includes(day.value) ? 'bg-blue-600 border-blue-600 text-white' : 'border-gray-300 text-gray-600 hover:bg-gray-50'"
            >
              {{ $t(`event.${day.key}`) }}
            </button>
          </div>
          <p class="text-xs text-gray-500 mt-1">{{ $t('app.weekendDaysHelp') }}</p>
        </div>
        <div class="grid gap-3 sm:grid-cols-2">
          <SettingsToggle v-model="calendarForm.show_weekends" :disabled="!canManage" :title="$t('app.showWeekends')" :description="$t('app.showWeekendsHelp')" />
          <SettingsToggle v-model="calendarForm.show_week_numbers" :disabled="!canManage" :title="$t('app.showWeekNumbers')" :description="$t('app.showWeekNumbersHelp')" />
        </div>
      </section>
      <section class="space-y-4 border-t border-gray-100 pt-6">
        <div>
          <h3 class="text-sm font-semibold text-gray-800">{{ $t('app.eventBehavior') }}</h3>
        </div>
      <SettingsToggle v-if="calendarForm" v-model="calendarForm.force_all_day" :disabled="!canManage" :title="$t('app.forceAllDay')" :description="$t('app.forceAllDayHelp')" />
      </section>
      </div>
      <template #footer>
        <button type="button" :disabled="!calendarForm || !canManage || busy" class="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50" @click="saveGeneralSettings">{{ $t('app.save') }}</button>
      </template>
    </SettingsPanel>

    <SettingsPanel v-else-if="tab === 'access'" :title="$t('app.access')" :description="$t('app.accessDescription')" :loading="loading">
      <div class="space-y-6">
      <template v-if="canManage">
        <!-- Public access -->
        <section class="space-y-3">
          <h3 class="text-sm font-semibold text-gray-800">{{ $t('app.publicCalendar') }}</h3>
          <div class="grid items-start gap-3 sm:grid-cols-2">
            <SettingsToggle v-if="calendarForm" v-model="calendarForm.is_public" :disabled="!canManage" :title="$t('app.publicCalendar')" :description="$t('app.publicCalendarHelp')" />
            <label v-if="calendarForm?.is_public" class="block">
              <span class="mb-1 block text-sm font-medium text-gray-800">{{ $t('app.publicRole') }}</span>
              <select v-model="calendarForm.public_role" :disabled="!canManage" class="w-full rounded-lg border px-3 py-2">
                <option value="viewer">{{ $t('roles.viewer') }}</option>
                <option value="contributor">{{ $t('roles.contributor') }}</option>
                <option value="editor">{{ $t('roles.editor') }}</option>
              </select>
              <p class="mt-1 text-xs text-gray-500">{{ $t('roles.' + calendarForm.public_role + 'Description') }}</p>
            </label>
          </div>
        </section>

        <!-- Group access -->
        <section class="space-y-4 border-t border-gray-100 pt-6">
          <h3 class="text-sm font-semibold text-gray-800">{{ $t('app.groupAccess') }}</h3>
          <div class="flex gap-2">
            <div class="flex-1">
              <SearchableSelect v-model="newGroupId" entity="groups" open-on-focus :placeholder="$t('app.search')" />
            </div>
            <select v-model="newGroupRole" class="border rounded-lg px-3 py-2">
              <option value="viewer">{{ $t('roles.viewer') }}</option>
              <option value="contributor">{{ $t('roles.contributor') }}</option>
              <option value="editor">{{ $t('roles.editor') }}</option>
            </select>
            <button
              type="button"
              @click="addCalendarGroupLink"
              :disabled="!newGroupId"
              class="px-3 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
            >
              <Plus :size="18" />
            </button>
          </div>
          <p class="text-xs text-gray-500 mt-1">{{ $t('roles.' + newGroupRole + 'Description') }}</p>
          <ul class="mt-3 divide-y divide-gray-100 border rounded-lg">
            <li
              v-for="link in calendarGroups"
              :key="link.id"
              class="px-3 py-2 flex items-center justify-between hover:bg-gray-50"
            >
              <span class="text-sm text-gray-800">{{ link.group.name }}</span>
              <div class="flex items-start gap-2">
                <div>
                  <select
                    :value="link.role"
                    @change="updateCalendarGroupLink(link.id, $event)"
                    class="border rounded-lg px-2 py-1 text-sm"
                  >
                    <option value="viewer">{{ $t('roles.viewer') }}</option>
                    <option value="contributor">{{ $t('roles.contributor') }}</option>
                    <option value="editor">{{ $t('roles.editor') }}</option>
                  </select>
                  <p class="text-xs text-gray-500 mt-1">{{ $t('roles.' + link.role + 'Description') }}</p>
                </div>
                <button
                  @click="removeCalendarGroupLink(link.id)"
                  class="text-red-600 hover:underline text-sm"
                >
                  {{ $t('app.delete') }}
                </button>
              </div>
            </li>
            <li v-if="!calendarGroups.length" class="px-3 py-6 text-center text-sm text-gray-500">
              {{ $t('app.noGroupAccess') }}
            </li>
          </ul>
        </section>
      </template>

      <!-- Direct members -->
      <section class="space-y-4 border-t border-gray-100 pt-6">
        <h3 class="text-sm font-semibold text-gray-800">{{ $t('app.members') }}</h3>
        <ul class="divide-y divide-gray-100">
          <li v-for="m in members" :key="m.id" class="py-2 flex items-center justify-between">
            <div>
              <div class="font-medium text-gray-800">{{ m.display_name }} ({{ m.email }})</div>
              <div class="text-xs text-gray-500">{{ $t('roles.' + m.role) }}</div>
            </div>
            <button v-if="canManage && m.role !== 'owner'" @click="removeMember(m.user_id)" class="text-red-600 hover:underline text-sm">
              {{ $t('app.delete') }}
            </button>
          </li>
        </ul>

        <div v-if="canManage" class="mt-4 space-y-2">
          <div class="flex gap-2">
            <div class="flex-1">
              <SearchableSelect v-model="selectedMemberId" entity="users" :min-search-length="2" :placeholder="$t('app.searchUsers')" />
            </div>
            <select v-model="newRole" class="border rounded-lg px-3 py-2">
              <option value="viewer">{{ $t('roles.viewer') }}</option>
              <option value="contributor">{{ $t('roles.contributor') }}</option>
              <option value="editor">{{ $t('roles.editor') }}</option>
            </select>
            <button
              type="button"
              @click="addMember"
              :disabled="!selectedMemberId"
              class="px-3 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
            >
              <Plus :size="18" />
            </button>
          </div>
          <p class="text-xs text-gray-500">{{ $t('roles.' + newRole + 'Description') }}</p>
        </div>
      </section>
      </div>
      <template #footer>
        <button v-if="canManage" type="button" :disabled="busy" class="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50" @click="saveAccessSettings">{{ $t('app.save') }}</button>
      </template>
    </SettingsPanel>

    <SettingsPanel v-else-if="tab === 'categories'" :title="$t('app.categories')" :description="$t('app.categoriesDescription')" :loading="loading" flush>
      <template v-if="categoryFormMode === 'list' && canManage" #actions>
        <button @click="startAddCategory" class="rounded-lg bg-blue-600 px-3 py-2 text-sm text-white hover:bg-blue-700">{{ $t('app.add') }}</button>
      </template>
      <div v-if="categoryFormMode === 'list'">
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
                  <div v-if="canManage" class="flex justify-end gap-1 opacity-100 md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100 transition-opacity">
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
          <h3 class="font-semibold text-gray-700">{{ categoryForm.id ? $t('app.editCategory') : $t('app.addCategory') }}</h3>
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
    </SettingsPanel>

    <SettingsPanel v-else-if="tab === 'resources'" :title="$t('app.resources')" :description="$t('app.resourcesDescription')" :loading="loading" flush>
      <template v-if="resourceFormMode === 'list' && canManage" #actions>
        <button @click="startAddResource" class="rounded-lg bg-blue-600 px-3 py-2 text-sm text-white hover:bg-blue-700">{{ $t('app.add') }}</button>
      </template>
      <div v-if="resourceFormMode === 'list'">
        <section class="space-y-3 border-b border-gray-200 px-5 py-4 sm:px-6">
          <div>
            <h3 class="text-sm font-semibold text-gray-800">{{ $t('app.defaultApprovers') }}</h3>
            <p class="mt-0.5 text-sm text-gray-500">{{ $t('app.defaultApproversDescription') }}</p>
          </div>
          <p v-if="!approvers.length" class="text-sm text-gray-500">{{ $t('app.noDefaultApprovers') }}</p>
          <ul v-if="approvers.length" class="flex flex-wrap gap-2">
            <li v-for="a in approvers" :key="a.user_id" class="inline-flex items-center gap-2 rounded-full border border-gray-200 py-1 pl-1 pr-2 text-sm" :title="a.email">
              <span class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-100 text-xs font-semibold text-blue-700 dark:bg-blue-900 dark:text-blue-200" aria-hidden="true">{{ (a.display_name || a.email).charAt(0).toUpperCase() }}</span>
              <span class="font-medium text-gray-800">{{ a.display_name }}</span>
              <button v-if="canManage" type="button" :disabled="busy" class="rounded-full p-0.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700 disabled:opacity-50" :aria-label="$t('app.delete')" @click="removeApprover(a.user_id)">
                <X :size="14" />
              </button>
            </li>
          </ul>
          <div v-if="canManage" class="sm:w-1/2">
            <SearchableSelect v-model="selectedApproverId" entity="members" :calendar-id="calendarId" :min-search-length="0" open-on-focus :placeholder="$t('app.addApprover')" :disabled="busy" @select="onDefaultApproverPicked" />
          </div>
        </section>
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
              <tr v-for="resource in resources" :key="resource.id" class="group hover:bg-gray-50" :class="{ 'opacity-60': !resource.is_active }">
                <td class="px-4 py-2"><span class="block w-5 h-5 rounded" :style="{ backgroundColor: resource.color }"></span></td>
                <td class="px-4 py-2 font-medium text-gray-800">{{ resource.name }}</td>
                <td class="px-4 py-2 text-gray-500">{{ resource.description || '—' }}</td>
                <td class="px-4 py-2" :class="resource.requires_approval ? 'text-gray-800' : 'text-gray-500'">{{ resourceApprovalLabel(resource) }}</td>
                <td class="px-4 py-2">{{ resource.is_active ? $t('app.active') : $t('app.inactive') }}</td>
                <td class="px-4 py-2">
                  <div v-if="canManage" class="flex justify-end gap-1 opacity-100 md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100 transition-opacity">
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
          <h3 class="font-semibold text-gray-700">{{ resourceForm.id ? $t('app.editResource') : $t('app.addResource') }}</h3>
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
          <div class="grid gap-3 sm:grid-cols-2">
            <SettingsToggle v-model="resourceForm.requires_approval" :title="$t('app.requiresApproval')" />
            <SettingsToggle v-model="resourceForm.is_active" :title="$t('app.active')" />
          </div>
          <fieldset v-if="resourceForm.requires_approval" class="space-y-3 rounded-lg border border-gray-200 p-4">
            <legend class="px-1 text-sm font-medium text-gray-700">{{ $t('app.approvedBy') }}</legend>
            <label class="flex items-center gap-2 text-sm">
              <input v-model="resourceForm.approval_mode" type="radio" value="default" />
              <span class="font-medium text-gray-800">{{ $t('app.useDefaultApprovers') }}</span>
              <span class="text-gray-500">({{ defaultApproverNames || $t('app.nobody') }})</span>
            </label>
            <label class="flex items-center gap-2 text-sm">
              <input v-model="resourceForm.approval_mode" type="radio" value="custom" />
              <span class="font-medium text-gray-800">{{ $t('app.useCustomApprovers') }}</span>
            </label>
            <div v-if="resourceForm.approval_mode === 'custom'" class="space-y-2 pl-6">
              <ul v-if="resourceForm.approvers.length" class="flex flex-wrap gap-2">
                <li v-for="a in resourceForm.approvers" :key="a.user_id" class="inline-flex items-center gap-2 rounded-full border border-gray-200 py-1 pl-1 pr-2 text-sm" :title="a.email">
                  <span class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-100 text-xs font-semibold text-blue-700 dark:bg-blue-900 dark:text-blue-200" aria-hidden="true">{{ (a.display_name || a.email).charAt(0).toUpperCase() }}</span>
                  <span class="font-medium text-gray-800">{{ a.display_name }}</span>
                  <button type="button" class="rounded-full p-0.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700" :aria-label="$t('app.delete')" @click="removeResourceFormApprover(a.user_id)">
                    <X :size="14" />
                  </button>
                </li>
              </ul>
              <p v-else class="text-sm text-gray-500">{{ $t('app.customApproversRequired') }}</p>
              <div class="sm:w-2/3">
                <SearchableSelect v-model="selectedResourceApproverId" entity="members" :calendar-id="calendarId" :min-search-length="0" open-on-focus :placeholder="$t('app.addApprover')" @select="onResourceApproverPicked" />
              </div>
            </div>
          </fieldset>
          <div class="flex justify-end gap-3">
            <button @click="cancelResourceForm" class="px-4 py-2 rounded-lg border border-gray-300 hover:bg-gray-100">{{ $t('app.cancel') }}</button>
            <button @click="saveResource" :disabled="resourceFormInvalid || busy" class="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50">{{ $t('app.save') }}</button>
          </div>
        </div>
      </div>
    </SettingsPanel>

    <SettingsPanel v-else :title="$t('app.share')" :description="$t('app.shareDescription')" :loading="loading">
      <div class="space-y-6">
      <div>
        <h2 class="font-semibold text-gray-700 mb-1">{{ $t('app.feedUrl') }}</h2>
        <code class="block bg-gray-50 border rounded-lg p-3 text-sm break-all">{{ feedUrl }}</code>
        <button @click="rotateFeed" class="mt-2 inline-flex items-center gap-2 text-sm text-blue-600 hover:underline"><RotateCw :size="16" />{{ $t('app.regenerateToken') }}</button>
      </div>
      <div>
        <h2 class="font-semibold text-gray-700 mb-1">{{ $t('app.caldavUrl') }}</h2>
        <code class="block bg-gray-50 border rounded-lg p-3 text-sm break-all">{{ caldavUrl }}</code>
      </div>
      </div>
    </SettingsPanel>
  </SettingsPage>
</template>
