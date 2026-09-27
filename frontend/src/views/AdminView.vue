<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ChevronLeft, Pencil, Trash2, KeyRound } from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useSettingsStore } from '@/stores/settings'
import * as api from '@/api'
import IconButton from '@/components/IconButton.vue'
import Modal from '@/components/Modal.vue'
import { confirm } from '@/services/dialog'

const auth = useAuthStore()
const settingsStore = useSettingsStore()
const router = useRouter()

type Tab = 'general' | 'users'
const tab = ref<Tab>('general')

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
const busy = ref(false)
const message = ref('')

const userFormMode = ref<'list' | 'add' | 'edit'>('list')
const userForm = ref({
  id: null as string | null,
  email: '',
  display_name: '',
  password: '',
  is_admin: false,
  is_active: true,
})
const generatedPassword = ref<string | null>(null)

onMounted(async () => {
  await load()
})

async function load() {
  if (!auth.token) return
  try {
    busy.value = true
    const [_, u] = await Promise.all([
      settingsStore.load(),
      api.listAdminUsers(auth.token),
    ])
    if (settingsStore.settings) {
      settings.value = { ...settingsStore.settings }
    }
    users.value = u
  } catch (e) {
    console.error(e)
  } finally {
    busy.value = false
  }
}

async function saveSettings() {
  if (!auth.token) return
  busy.value = true
  try {
    settings.value = await settingsStore.update(auth.token, {
      app_name: settings.value.app_name,
      logo_url: settings.value.logo_url,
      favicon_url: settings.value.favicon_url,
      default_first_weekday: settings.value.default_first_weekday,
      default_show_weekends: settings.value.default_show_weekends,
      default_weekend_days: settings.value.default_weekend_days,
      default_show_week_numbers: settings.value.default_show_week_numbers,
    })
    message.value = 'Settings saved'
  } catch (e) {
    console.error(e)
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
    is_active: true,
  }
  generatedPassword.value = null
  userFormMode.value = 'add'
}

function startEditUser(user: api.AdminUser) {
  userForm.value = {
    id: user.id,
    email: user.email,
    display_name: user.display_name,
    password: '',
    is_admin: user.is_admin,
    is_active: user.is_active,
  }
  generatedPassword.value = null
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
    is_active: true,
  }
}

async function saveUser() {
  if (!auth.token || !userForm.value.email || !userForm.value.display_name) return
  try {
    if (userForm.value.id) {
      const data: api.AdminUserUpdate = {
        email: userForm.value.email,
        display_name: userForm.value.display_name,
        is_admin: userForm.value.is_admin,
        is_active: userForm.value.is_active,
      }
      if (userForm.value.password) {
        data.password = userForm.value.password
      }
      await api.updateAdminUser(auth.token, userForm.value.id, data)
      cancelUserForm()
    } else {
      const password = userForm.value.password || generatePassword()
      await api.createAdminUser(auth.token, {
        email: userForm.value.email,
        display_name: userForm.value.display_name,
        password,
        is_admin: userForm.value.is_admin,
        is_active: userForm.value.is_active,
      })
      if (!userForm.value.password) {
        generatedPassword.value = password
      }
      cancelUserForm()
    }
    await load()
  } catch (e) {
    console.error(e)
  }
}

function generatePassword() {
  const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
  let password = ''
  for (let i = 0; i < 16; i++) {
    password += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  return password
}

async function deleteUser(user: api.AdminUser) {
  if (!auth.token) return
  const ok = await confirm(`Delete ${user.display_name}?`, 'Delete user')
  if (!ok) return
  await api.deleteAdminUser(auth.token, user.id)
  await load()
}

async function resetPassword(user: api.AdminUser) {
  if (!auth.token) return
  const ok = await confirm(`Reset password for ${user.display_name}?`, 'Reset password')
  if (!ok) return
  const resp = await api.resetAdminUserPassword(auth.token, user.id)
  generatedPassword.value = resp.password
}

const isCurrentUser = computed(() => {
  return (id: string) => id === auth.user?.id
})
</script>

<template>
  <div class="max-w-4xl mx-auto p-6">
    <div class="flex items-center gap-3 mb-2">
      <IconButton @click="router.back()" :label="$t('app.back')" bordered>
        <ChevronLeft :size="20" :stroke-width="2.25" />
      </IconButton>
      <h1 class="text-2xl font-bold text-gray-800">{{ $t('app.administration') }}</h1>
    </div>

    <div class="flex gap-2 mb-4 border-b border-gray-200">
      <button
        v-for="t in ['general', 'users']"
        :key="t"
        @click="tab = t as Tab"
        :class="{ 'border-b-2 border-blue-600 text-blue-600': tab === t }"
        class="px-4 py-2 text-sm font-medium text-gray-600 capitalize"
      >
        {{ $t(`app.${t}`) }}
      </button>
    </div>

    <div v-if="tab === 'general'" class="bg-white rounded-xl border border-gray-200 p-6 space-y-6">
      <h2 class="font-semibold text-gray-700">{{ $t('app.generalSettings') }}</h2>
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
        <label class="block">
          <span class="block text-sm font-medium text-gray-800 mb-1">{{ $t('app.firstWeekday') }}</span>
          <select v-model.number="settings.default_first_weekday" class="w-full border rounded-lg px-3 py-2">
            <option v-for="day in weekdayChoices" :key="day.value" :value="day.value">{{ $t(`event.${day.key}`) }}</option>
          </select>
        </label>
        <label class="flex items-start gap-3">
          <input v-model="settings.default_show_weekends" type="checkbox" class="mt-1" />
          <span>
            <span class="block text-sm font-medium text-gray-800">{{ $t('app.showWeekends') }}</span>
            <span class="block text-xs text-gray-500 mt-0.5">{{ $t('app.showWeekendsHelp') }}</span>
          </span>
        </label>
        <label class="flex items-start gap-3">
          <input v-model="settings.default_show_week_numbers" type="checkbox" class="mt-1" />
          <span>
            <span class="block text-sm font-medium text-gray-800">{{ $t('app.showWeekNumbers') }}</span>
            <span class="block text-xs text-gray-500 mt-0.5">{{ $t('app.showWeekNumbersHelp') }}</span>
          </span>
        </label>
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

      <div>
        <button
          @click="saveSettings"
          :disabled="busy"
          class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          {{ $t('app.save') }}
        </button>
        <p v-if="message" class="mt-2 text-sm text-green-600">{{ message }}</p>
      </div>
    </div>

    <div v-if="tab === 'users'" class="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <div v-if="userFormMode === 'list'">
        <div class="px-6 py-4 flex items-center justify-between border-b border-gray-200">
          <h2 class="font-semibold text-gray-700">{{ $t('app.users') }}</h2>
          <button @click="startAddUser" class="px-3 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
            {{ $t('app.addUser') }}
          </button>
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
                  <span
                    v-if="user.is_admin"
                    class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200"
                  >
                    {{ $t('app.admin') }}
                  </span>
                  <span v-else class="text-gray-500">—</span>
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
                  <div class="flex justify-end gap-1 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity">
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
              <input
                v-model="userForm.password"
                type="text"
                :placeholder="userForm.id ? $t('app.passwordUnchanged') : $t('app.passwordGenerated')"
                class="w-full border border-gray-300 rounded-lg px-3 py-2"
              />
            </label>
            <div class="flex gap-6">
              <label class="flex items-center gap-2 text-sm">
                <input v-model="userForm.is_admin" type="checkbox" />
                {{ $t('app.admin') }}
              </label>
              <label class="flex items-center gap-2 text-sm">
                <input v-model="userForm.is_active" type="checkbox" />
                {{ $t('app.active') }}
              </label>
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
    </div>

    <Modal :open="!!generatedPassword" title="New password" @close="generatedPassword = null">
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
  </div>
</template>
