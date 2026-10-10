<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Eye, EyeOff, KeyRound, Pencil, Plus, Trash2, X } from 'lucide-vue-next'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useSettingsStore } from '@/stores/settings'
import * as api from '@/api'
import IconButton from '@/components/IconButton.vue'
import Modal from '@/components/Modal.vue'
import SearchableSelect from '@/components/SearchableSelect.vue'
import SettingsPage from '@/components/SettingsPage.vue'
import SettingsPanel from '@/components/SettingsPanel.vue'
import SettingsToggle from '@/components/SettingsToggle.vue'
import { confirm } from '@/services/dialog'
import { errorMessage, toast } from '@/services/toast'
import { useI18n } from 'vue-i18n'

const auth = useAuthStore()
const settingsStore = useSettingsStore()
const route = useRoute()
const router = useRouter()
const { t } = useI18n()

type Tab = 'general' | 'users' | 'groups'
const validTabs: Tab[] = ['general', 'users', 'groups']
const tab = computed<Tab>(() => validTabs.includes(route.query.tab as Tab) ? route.query.tab as Tab : 'general')
const tabs = computed(() => validTabs.map((id) => ({ id, label: t(`app.${id}`) })))

function selectTab(id: string) {
  if (!validTabs.includes(id as Tab)) return
  cancelUserForm()
  cancelGroupForm()
  router.push({ query: { ...route.query, tab: id } })
}

const settings = ref<api.AppSettings>({
  id: 1,
  app_name: 'Calendar',
  logo_url: null,
  favicon_url: null,
  default_first_weekday: 0,
  default_show_weekends: true,
  default_weekend_days: [0, 6],
  default_show_week_numbers: false,
})
const weekdayChoices = [
  { value: 0, key: 'sunday' },
  { value: 1, key: 'monday' },
  { value: 2, key: 'tuesday' },
  { value: 3, key: 'wednesday' },
  { value: 4, key: 'thursday' },
  { value: 5, key: 'friday' },
  { value: 6, key: 'saturday' },
]
const orderedWeekendChoices = computed(() => [
  ...weekdayChoices.slice(settings.value.default_first_weekday),
  ...weekdayChoices.slice(0, settings.value.default_first_weekday),
])
const users = ref<api.AdminUser[]>([])
const groups = ref<api.UserGroup[]>([])
const loading = ref(true)
const busy = ref(false)
const message = ref('')

const userFormMode = ref<'list' | 'add' | 'edit'>('list')
const userForm = ref({
  id: null as string | null,
  email: '',
  display_name: '',
  password: '',
  is_admin: false,
  is_staff: false,
  is_superuser: false,
  is_active: true,
  group_ids: [] as string[],
})
const generatedPassword = ref<string | null>(null)
const showPassword = ref(false)
const selectedUserGroupId = ref<string | null>(null)

const groupFormMode = ref<'list' | 'add' | 'edit'>('list')
const groupForm = ref({
  id: null as string | null,
  name: '',
  description: '',
})
const groupFormMembers = ref<api.UserGroupMember[]>([])
const groupFormOriginalMemberIds = ref<string[]>([])
const selectedMemberUserId = ref<string | null>(null)

onMounted(async () => {
  await load()
})

watch(() => route.query.tab, (value) => {
  if (value && !validTabs.includes(value as Tab)) router.replace({ query: { ...route.query, tab: 'general' } })
})

async function load() {
  if (!auth.isLoggedIn) return
  try {
    loading.value = true
    const [_, u, g] = await Promise.all([
      settingsStore.load(),
      api.listAdminUsers(),
      api.listUserGroups(),
    ])
    if (settingsStore.settings) {
      settings.value = { ...settingsStore.settings }
    }
    users.value = u
    groups.value = g
  } catch (error) {
    toast.error(errorMessage(error, t('app.loadFailed')))
  } finally {
    loading.value = false
  }
}

async function saveSettings() {
  if (!auth.isLoggedIn) return
  busy.value = true
  try {
    settings.value = await settingsStore.update({
      app_name: settings.value.app_name,
      logo_url: settings.value.logo_url,
      favicon_url: settings.value.favicon_url,
      default_first_weekday: settings.value.default_first_weekday,
      default_show_weekends: settings.value.default_show_weekends,
      default_weekend_days: settings.value.default_weekend_days,
      default_show_week_numbers: settings.value.default_show_week_numbers,
    })
    message.value = t('app.settingsSaved')
    toast.success(t('app.settingsSaved'))
  } catch (error) {
    toast.error(errorMessage(error, t('app.saveFailed')))
  } finally {
    busy.value = false
  }
}

function toggleDefaultWeekendDay(day: number) {
  const days = settings.value.default_weekend_days
  if (days.includes(day)) {
    settings.value.default_weekend_days = days.filter((d) => d !== day)
  } else {
    settings.value.default_weekend_days = [...days, day].sort((a, b) => a - b)
  }
}

function readFileAsDataURL(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

async function onLogoChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  settings.value.logo_url = await readFileAsDataURL(file)
}

async function onFaviconChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  settings.value.favicon_url = await readFileAsDataURL(file)
}

function startAddUser() {
  userForm.value = {
    id: null,
    email: '',
    display_name: '',
    password: '',
    is_admin: false,
    is_staff: false,
    is_superuser: false,
    is_active: true,
    group_ids: [],
  }
  generatedPassword.value = null
  showPassword.value = false
  userFormMode.value = 'add'
}

function startEditUser(user: api.AdminUser) {
  userForm.value = {
    id: user.id,
    email: user.email,
    display_name: user.display_name,
    password: '',
    is_admin: user.is_admin,
    is_staff: user.is_staff,
    is_superuser: user.is_superuser,
    is_active: user.is_active,
    group_ids: user.groups.map((g) => g.id),
  }
  generatedPassword.value = null
  showPassword.value = false
  userFormMode.value = 'edit'
}

function cancelUserForm() {
  userFormMode.value = 'list'
  userForm.value = {
    id: null,
    email: '',
    display_name: '',
    password: '',
    is_admin: false,
    is_staff: false,
    is_superuser: false,
    is_active: true,
    group_ids: [],
  }
  selectedUserGroupId.value = null
  showPassword.value = false
}

const selectedUserGroups = computed(() =>
  groups.value.filter((g) => userForm.value.group_ids.includes(g.id)).sort((a, b) => a.name.localeCompare(b.name)),
)

const availableUserGroups = computed(() =>
  groups.value.filter((g) => !userForm.value.group_ids.includes(g.id)).sort((a, b) => a.name.localeCompare(b.name)),
)

function addUserGroup() {
  const groupId = selectedUserGroupId.value
  if (!groupId || userForm.value.group_ids.includes(groupId)) return
  userForm.value.group_ids.push(groupId)
  selectedUserGroupId.value = null
}

function removeUserGroup(groupId: string) {
  userForm.value.group_ids = userForm.value.group_ids.filter((id) => id !== groupId)
}

async function saveUser() {
  if (!auth.isLoggedIn || !userForm.value.email || !userForm.value.display_name) return
  try {
    const groupIds = userForm.value.group_ids
    if (userForm.value.id) {
      const data: api.AdminUserUpdate = {
        email: userForm.value.email,
        display_name: userForm.value.display_name,
        is_admin: userForm.value.is_admin,
        is_staff: userForm.value.is_staff,
        is_superuser: userForm.value.is_superuser,
        is_active: userForm.value.is_active,
        group_ids: groupIds,
      }
      if (userForm.value.password) {
        data.password = userForm.value.password
      }
      await api.updateAdminUser(userForm.value.id, data)
      cancelUserForm()
    } else {
      const password = userForm.value.password || generatePassword()
      await api.createAdminUser({
        email: userForm.value.email,
        display_name: userForm.value.display_name,
        password,
        is_admin: userForm.value.is_admin,
        is_staff: userForm.value.is_staff,
        is_superuser: userForm.value.is_superuser,
        is_active: userForm.value.is_active,
        group_ids: groupIds,
      })
      if (!userForm.value.password) {
        generatedPassword.value = password
      }
      cancelUserForm()
    }
    await load()
  } catch (error) {
    toast.error(errorMessage(error, t('app.saveFailed')))
  }
}

function startAddGroup() {
  groupForm.value = {
    id: null,
    name: '',
    description: '',
  }
  groupFormMembers.value = []
  groupFormOriginalMemberIds.value = []
  selectedMemberUserId.value = null
  groupFormMode.value = 'add'
}

async function startEditGroup(group: api.UserGroup) {
  if (!auth.isLoggedIn) return
  groupForm.value = {
    id: group.id,
    name: group.name,
    description: group.description ?? '',
  }
  groupFormMembers.value = []
  groupFormOriginalMemberIds.value = []
  selectedMemberUserId.value = null
  try {
    const detail = await api.getUserGroup(group.id)
    groupFormMembers.value = detail.members
    groupFormOriginalMemberIds.value = detail.members.map((m) => m.id)
  } catch (error) {
    toast.error(errorMessage(error, t('app.loadFailed')))
  }
  groupFormMode.value = 'edit'
}

function cancelGroupForm() {
  groupFormMode.value = 'list'
  groupForm.value = {
    id: null,
    name: '',
    description: '',
  }
  groupFormMembers.value = []
  groupFormOriginalMemberIds.value = []
  selectedMemberUserId.value = null
}

async function saveGroup() {
  if (!auth.isLoggedIn || !groupForm.value.name) return
  const groupId = groupForm.value.id
  try {
    const isNew = !groupId
    let group: api.UserGroupDetail
    if (isNew) {
      group = await api.createUserGroup({
        name: groupForm.value.name,
        description: groupForm.value.description || null,
      })
    } else {
      group = await api.updateUserGroup(groupId, {
        name: groupForm.value.name,
        description: groupForm.value.description || null,
      })
    }

    const currentIds = groupFormMembers.value.map((m) => m.id)
    if (isNew) {
      for (const member of groupFormMembers.value) {
        await api.addUserGroupMember(group.id, member.id)
      }
    } else {
      const added = currentIds.filter((id) => !groupFormOriginalMemberIds.value.includes(id))
      const removed = groupFormOriginalMemberIds.value.filter((id) => !currentIds.includes(id))
      for (const userId of added) {
        await api.addUserGroupMember(group.id, userId)
      }
      for (const userId of removed) {
        await api.removeUserGroupMember(group.id, userId)
      }
    }

    cancelGroupForm()
    await load()
  } catch (error) {
    toast.error(errorMessage(error, t('app.saveFailed')))
  }
}

async function deleteGroup(group: api.UserGroup) {
  if (!auth.isLoggedIn) return
  const ok = await confirm(`Delete ${group.name}?`, 'Delete group')
  if (!ok) return
  await api.deleteUserGroup(group.id)
  await load()
}

function addGroupMember() {
  const userId = selectedMemberUserId.value
  if (!userId) return
  const user = users.value.find((u) => u.id === userId)
  if (!user) return
  if (groupFormMembers.value.some((m) => m.id === userId)) return
  groupFormMembers.value.push({
    id: user.id,
    email: user.email,
    display_name: user.display_name,
  })
  selectedMemberUserId.value = null
}

function removeGroupMember(member: api.UserGroupMember) {
  groupFormMembers.value = groupFormMembers.value.filter((m) => m.id !== member.id)
}

const availableGroupMembers = computed(() => {
  const memberIds = new Set(groupFormMembers.value.map((m) => m.id))
  return users.value
    .filter((u) => !memberIds.has(u.id))
    .sort((a, b) => a.display_name.localeCompare(b.display_name))
})

function generatePassword() {
  const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
  let password = ''
  for (let i = 0; i < 16; i++) {
    password += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  return password
}

async function deleteUser(user: api.AdminUser) {
  if (!auth.isLoggedIn) return
  const ok = await confirm(`Delete ${user.display_name}?`, 'Delete user')
  if (!ok) return
  await api.deleteAdminUser(user.id)
  await load()
}

async function resetPassword(user: api.AdminUser) {
  if (!auth.isLoggedIn) return
  const ok = await confirm(`Reset password for ${user.display_name}?`, 'Reset password')
  if (!ok) return
  const resp = await api.resetAdminUserPassword(user.id)
  generatedPassword.value = resp.password
}

const isCurrentUser = computed(() => {
  return (id: string) => id === auth.user?.id
})
</script>

<template>
  <SettingsPage :title="$t('app.administration')" :tabs="tabs" :active-tab="tab" @back="router.back()" @select-tab="selectTab">
    <SettingsPanel v-if="tab === 'general'" :title="$t('app.generalSettings')" :description="$t('app.adminGeneralDescription')" :loading="loading">
      <div class="space-y-6">
      <div>
        <label class="block text-sm font-medium text-gray-800 mb-1">{{ $t('app.appName') }}</label>
        <input v-model="settings.app_name" class="w-full border rounded-lg px-3 py-2" />
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-800 mb-1">{{ $t('app.logo') }}</label>
        <div class="flex items-center gap-4">
          <div
            v-if="settings.logo_url"
            class="w-16 h-16 rounded-lg border border-gray-200 bg-white flex items-center justify-center overflow-hidden"
          >
            <img :src="settings.logo_url" alt="Logo preview" class="max-w-full max-h-full object-contain" />
          </div>
          <div v-else class="w-16 h-16 rounded-lg border border-gray-200 bg-gray-50 flex items-center justify-center text-gray-400 text-sm">
            {{ $t('app.noLogo') }}
          </div>
          <div>
            <input type="file" accept="image/*" @change="onLogoChange" class="block text-sm text-gray-600" />
            <button
              v-if="settings.logo_url"
              @click="settings.logo_url = null"
              class="mt-2 text-sm text-red-600 hover:underline"
            >
              {{ $t('app.removeLogo') }}
            </button>
          </div>
        </div>
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-800 mb-1">{{ $t('app.favicon') }}</label>
        <div class="flex items-center gap-4">
          <div
            v-if="settings.favicon_url"
            class="w-10 h-10 rounded border border-gray-200 bg-white flex items-center justify-center overflow-hidden"
          >
            <img :src="settings.favicon_url" alt="Favicon preview" class="max-w-full max-h-full object-contain" />
          </div>
          <div v-else class="w-10 h-10 rounded border border-gray-200 bg-gray-50 flex items-center justify-center text-gray-400 text-xs">
            {{ $t('app.noFavicon') }}
          </div>
          <div>
            <input type="file" accept="image/*" @change="onFaviconChange" class="block text-sm text-gray-600" />
            <button
              v-if="settings.favicon_url"
              @click="settings.favicon_url = null"
              class="mt-2 text-sm text-red-600 hover:underline"
            >
              {{ $t('app.removeFavicon') }}
            </button>
          </div>
        </div>
      </div>

      <div class="border-t border-gray-100 pt-4 space-y-4">
        <h3 class="text-sm font-semibold text-gray-700">{{ $t('app.calendarDisplay') }}</h3>
        <p class="text-xs text-gray-500">{{ $t('app.defaultCalendarSettingsHelp') }}</p>
        <div class="grid gap-3 sm:grid-cols-2">
          <label class="block">
            <span class="mb-1 block text-sm font-medium text-gray-800">{{ $t('app.firstWeekday') }}</span>
            <select v-model.number="settings.default_first_weekday" class="w-full rounded-lg border px-3 py-2">
              <option v-for="day in weekdayChoices" :key="day.value" :value="day.value">{{ $t(`event.${day.key}`) }}</option>
            </select>
          </label>
        </div>
        <div class="grid gap-3 sm:grid-cols-2">
          <SettingsToggle v-model="settings.default_show_weekends" :title="$t('app.showWeekends')" :description="$t('app.showWeekendsHelp')" />
          <SettingsToggle v-model="settings.default_show_week_numbers" :title="$t('app.showWeekNumbers')" :description="$t('app.showWeekNumbersHelp')" />
        </div>
        <div>
          <span class="block text-sm font-medium text-gray-800 mb-2">{{ $t('app.weekendDays') }}</span>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="day in orderedWeekendChoices"
              :key="day.value"
              type="button"
              @click="toggleDefaultWeekendDay(day.value)"
              class="px-3 py-1.5 rounded-full border text-sm transition-colors"
              :class="settings.default_weekend_days.includes(day.value) ? 'bg-blue-600 border-blue-600 text-white' : 'border-gray-300 text-gray-600 hover:bg-gray-50'"
            >
              {{ $t(`event.${day.key}`) }}
            </button>
          </div>
        </div>
      </div>

        <p v-if="message" class="text-sm text-green-600">{{ message }}</p>
      </div>
      <template #footer>
        <button @click="saveSettings" :disabled="busy" class="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50">{{ $t('app.save') }}</button>
      </template>
    </SettingsPanel>

    <SettingsPanel v-else-if="tab === 'users'" :title="userFormMode === 'list' ? $t('app.users') : (userForm.id ? $t('app.editUser') : $t('app.addUser'))" :description="$t('app.usersDescription')" :loading="loading" flush>
      <div v-if="userFormMode === 'list'">
        <div class="flex justify-end p-4">
          <button @click="startAddUser" class="rounded-lg bg-blue-600 px-3 py-2 text-sm text-white hover:bg-blue-700">{{ $t('app.addUser') }}</button>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="bg-gray-50 text-left text-xs uppercase text-gray-500">
              <tr>
                <th class="px-4 py-2">{{ $t('app.nameLabel') }}</th>
                <th class="px-4 py-2">{{ $t('auth.email') }}</th>
                <th class="px-4 py-2">{{ $t('app.role') }}</th>
                <th class="px-4 py-2">{{ $t('app.status') }}</th>
                <th class="px-4 py-2 text-right">{{ $t('app.actions') }}</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              <tr v-for="user in users" :key="user.id" class="group hover:bg-gray-50">
                <td class="px-4 py-2 font-medium text-gray-800">{{ user.display_name }}</td>
                <td class="px-4 py-2 text-gray-600">{{ user.email }}</td>
                <td class="px-4 py-2">
                  <div class="flex flex-wrap gap-1">
                    <span
                      v-if="user.is_admin"
                      class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200"
                    >
                      {{ $t('app.admin') }}
                    </span>
                    <span
                      v-if="user.is_staff"
                      class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200"
                    >
                      {{ $t('app.staff') }}
                    </span>
                    <span
                      v-if="user.is_superuser"
                      class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200"
                    >
                      {{ $t('app.superuser') }}
                    </span>
                    <span v-if="!user.is_admin && !user.is_staff && !user.is_superuser" class="text-gray-500">—</span>
                  </div>
                </td>
                <td class="px-4 py-2">
                  <span
                    :class="user.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'"
                    class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
                  >
                    {{ user.is_active ? $t('app.active') : $t('app.inactive') }}
                  </span>
                </td>
                <td class="px-4 py-2">
                  <div class="flex justify-end gap-1 opacity-100 md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100 transition-opacity">
                    <IconButton @click="startEditUser(user)" :label="$t('app.edit')" tone="primary">
                      <Pencil :size="18" :stroke-width="2.25" />
                    </IconButton>
                    <IconButton @click="resetPassword(user)" :label="$t('app.resetPassword')" tone="primary">
                      <KeyRound :size="18" :stroke-width="2.25" />
                    </IconButton>
                    <IconButton
                      v-if="!isCurrentUser(user.id)"
                      @click="deleteUser(user)"
                      :label="$t('app.delete')"
                      tone="danger"
                    >
                      <Trash2 :size="18" :stroke-width="2.25" />
                    </IconButton>
                  </div>
                </td>
              </tr>
              <tr v-if="!users.length">
                <td colspan="5" class="px-6 py-8 text-center text-gray-500">{{ $t('app.noUsers') }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-else>
        <div class="px-6 py-4 flex items-center justify-between border-b border-gray-200">
          <h2 class="font-semibold text-gray-700">{{ userForm.id ? $t('app.editUser') : $t('app.addUser') }}</h2>
          <div class="h-9" aria-hidden="true"></div>
        </div>
        <div class="p-6 space-y-4">
          <div class="space-y-4">
            <label class="block">
              <span class="block text-sm font-medium text-gray-700 mb-1">{{ $t('auth.displayName') }}</span>
              <input v-model="userForm.display_name" class="w-full border border-gray-300 rounded-lg px-3 py-2" />
            </label>
            <label class="block">
              <span class="block text-sm font-medium text-gray-700 mb-1">{{ $t('auth.email') }}</span>
              <input v-model="userForm.email" type="email" class="w-full border border-gray-300 rounded-lg px-3 py-2" />
            </label>
            <label class="block">
              <span class="block text-sm font-medium text-gray-700 mb-1">{{ $t('auth.password') }}</span>
              <div class="relative">
                <input
                  v-model="userForm.password"
                  :type="showPassword ? 'text' : 'password'"
                  :placeholder="userForm.id ? $t('app.passwordUnchanged') : $t('app.passwordGenerated')"
                  class="w-full border border-gray-300 rounded-lg px-3 py-2 pr-10"
                />
                <IconButton
                  type="button"
                  class="absolute right-2 top-1/2 -translate-y-1/2"
                  :label="showPassword ? $t('auth.hidePassword') : $t('auth.showPassword')"
                  @click="showPassword = !showPassword"
                >
                  <Eye v-if="showPassword" :size="18" :stroke-width="2.25" />
                  <EyeOff v-else :size="18" :stroke-width="2.25" />
                </IconButton>
              </div>
            </label>
            <div class="grid gap-3 sm:grid-cols-2">
              <SettingsToggle v-model="userForm.is_admin" :title="$t('app.admin')" />
              <SettingsToggle v-model="userForm.is_staff" :title="$t('app.staff')" />
              <SettingsToggle v-model="userForm.is_superuser" :title="$t('app.superuser')" />
              <SettingsToggle v-model="userForm.is_active" :title="$t('app.active')" />
            </div>
            <div>
              <h3 class="text-sm font-semibold text-gray-700 mb-3">{{ $t('app.groups') }}</h3>
              <div v-if="selectedUserGroups.length" class="space-y-2 mb-4">
                <div
                  v-for="group in selectedUserGroups"
                  :key="group.id"
                  class="flex items-center justify-between px-3 py-2 bg-gray-50 rounded-lg"
                >
                  <div>
                    <p class="text-sm font-medium text-gray-800">{{ group.name }}</p>
                  </div>
                  <IconButton
                    type="button"
                    @click="removeUserGroup(group.id)"
                    :label="$t('app.delete')"
                    tone="danger"
                  >
                    <X :size="18" :stroke-width="2.25" />
                  </IconButton>
                </div>
              </div>
              <p v-else class="text-sm text-gray-500 mb-4">{{ $t('app.noGroups') }}</p>

              <div v-if="availableUserGroups.length" class="flex items-end gap-2">
                <div class="flex-1">
                  <span class="block text-sm font-medium text-gray-700 mb-1">{{ $t('app.addGroup') }}</span>
                  <SearchableSelect
                    v-model="selectedUserGroupId"
                    entity="groups"
                    open-on-focus
                    :placeholder="$t('app.search')"
                  />
                </div>
                <button
                  type="button"
                  @click="addUserGroup"
                  :disabled="!selectedUserGroupId"
                  class="px-3 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
                >
                  <Plus :size="18" />
                </button>
              </div>
            </div>
          </div>
          <div class="flex justify-end gap-3">
            <button @click="cancelUserForm" class="px-4 py-2 rounded-lg border border-gray-300 hover:bg-gray-100">
              {{ $t('app.cancel') }}
            </button>
            <button
              @click="saveUser"
              :disabled="!userForm.email || !userForm.display_name"
              class="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {{ $t('app.save') }}
            </button>
          </div>
        </div>
      </div>
    </SettingsPanel>

    <SettingsPanel v-else :title="groupFormMode === 'list' ? $t('app.groups') : (groupForm.id ? $t('app.editGroup') : $t('app.addGroup'))" :description="$t('app.groupsDescription')" :loading="loading" flush>
      <div v-if="groupFormMode === 'list'">
        <div class="flex justify-end p-4">
          <button type="button" @click="startAddGroup" class="rounded-lg bg-blue-600 px-3 py-2 text-sm text-white hover:bg-blue-700">{{ $t('app.addGroup') }}</button>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="bg-gray-50 text-left text-xs uppercase text-gray-500">
              <tr>
                <th class="px-4 py-2">{{ $t('app.groupName') }}</th>
                <th class="px-4 py-2">{{ $t('app.groupDescription') }}</th>
                <th class="px-4 py-2">{{ $t('app.members') }}</th>
                <th class="px-4 py-2 text-right">{{ $t('app.actions') }}</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              <tr v-for="group in groups" :key="group.id" class="group hover:bg-gray-50">
                <td class="px-4 py-2 font-medium text-gray-800">{{ group.name }}</td>
                <td class="px-4 py-2 text-gray-600">
                  <span v-if="group.description" class="line-clamp-1">{{ group.description }}</span>
                  <span v-else class="text-gray-400">—</span>
                </td>
                <td class="px-4 py-2 text-gray-600">
                  {{ group.member_count ?? 0 }}
                </td>
                <td class="px-4 py-2">
                  <div class="flex justify-end gap-1 opacity-100 md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100 transition-opacity">
                    <IconButton @click="startEditGroup(group)" :label="$t('app.edit')" tone="primary">
                      <Pencil :size="18" :stroke-width="2.25" />
                    </IconButton>
                    <IconButton @click="deleteGroup(group)" :label="$t('app.delete')" tone="danger">
                      <Trash2 :size="18" :stroke-width="2.25" />
                    </IconButton>
                  </div>
                </td>
              </tr>
              <tr v-if="!groups.length">
                <td colspan="4" class="px-6 py-8 text-center text-gray-500">{{ $t('app.noGroups') }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-else>
        <div class="px-6 py-4 flex items-center justify-between border-b border-gray-200">
          <h2 class="font-semibold text-gray-700">{{ groupForm.id ? $t('app.editGroup') : $t('app.addGroup') }}</h2>
          <div class="h-9" aria-hidden="true"></div>
        </div>
        <div class="p-6 space-y-6">
          <div class="space-y-4">
            <label class="block">
              <span class="block text-sm font-medium text-gray-700 mb-1">{{ $t('app.groupName') }}</span>
              <input v-model="groupForm.name" class="w-full border border-gray-300 rounded-lg px-3 py-2" />
            </label>
            <label class="block">
              <span class="block text-sm font-medium text-gray-700 mb-1">{{ $t('app.groupDescription') }}</span>
              <textarea
                v-model="groupForm.description"
                rows="3"
                class="w-full border border-gray-300 rounded-lg px-3 py-2"
              ></textarea>
            </label>
          </div>

          <div class="border-t border-gray-100 pt-4">
            <h3 class="text-sm font-semibold text-gray-700 mb-3">{{ $t('app.members') }}</h3>
            <div v-if="groupFormMembers.length" class="space-y-2 mb-4">
              <div
                v-for="member in groupFormMembers"
                :key="member.id"
                class="flex items-center justify-between px-3 py-2 bg-gray-50 rounded-lg"
              >
                <div>
                  <p class="text-sm font-medium text-gray-800">{{ member.display_name }}</p>
                  <p class="text-xs text-gray-500">{{ member.email }}</p>
                </div>
                <IconButton
                  type="button"
                  @click="removeGroupMember(member)"
                  :label="$t('app.removeMember')"
                  tone="danger"
                >
                  <X :size="18" :stroke-width="2.25" />
                </IconButton>
              </div>
            </div>
            <p v-else class="text-sm text-gray-500 mb-4">{{ $t('app.noMembers') }}</p>

            <div v-if="groupForm.id" class="flex items-end gap-2">
              <div class="flex-1">
                <span class="block text-sm font-medium text-gray-700 mb-1">{{ $t('app.addMember') }}</span>
                <SearchableSelect
                  v-model="selectedMemberUserId"
                  entity="users"
                  :min-search-length="2"
                  :placeholder="$t('app.searchUsers')"
                />
              </div>
              <button
                type="button"
                @click="addGroupMember"
                :disabled="!selectedMemberUserId"
                class="px-3 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
              >
                <Plus :size="18" />
              </button>
            </div>
          </div>

          <div class="flex justify-end gap-3 border-t border-gray-100 pt-4">
            <button
              type="button"
              @click="cancelGroupForm"
              class="px-4 py-2 rounded-lg border border-gray-300 hover:bg-gray-100"
            >
              {{ $t('app.cancel') }}
            </button>
            <button
              type="button"
              @click="saveGroup"
              :disabled="!groupForm.name"
              class="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {{ $t('app.save') }}
            </button>
          </div>
        </div>
      </div>
    </SettingsPanel>

    <Modal :open="!!generatedPassword" :title="$t('app.newPassword')" @close="generatedPassword = null">
      <div class="bg-green-50 border border-green-200 rounded-lg p-4 text-sm text-green-800">
        <p class="mb-1">{{ $t('app.passwordGeneratedInfo') }}</p>
        <code class="font-mono font-semibold">{{ generatedPassword }}</code>
      </div>
      <template #footer>
        <div class="flex justify-end">
          <button @click="generatedPassword = null" class="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700">
            {{ $t('app.ok') }}
          </button>
        </div>
      </template>
    </Modal>
  </SettingsPage>
</template>
