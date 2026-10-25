<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Dices, EllipsisVertical, Eye, EyeOff, Pencil, Plus, X } from '@lucide/vue'
import * as api from '@/api'
import IconButton from '@/components/IconButton.vue'
import AppModal from '@/components/AppModal.vue'
import ContextMenu, { type MenuItem } from '@/components/ContextMenu.vue'
import SearchableSelect from '@/components/SearchableSelect.vue'
import SettingsPanel from '@/components/SettingsPanel.vue'
import SettingsToggle from '@/components/SettingsToggle.vue'
import { useAction } from '@/composables/useAction'
import { useLoader } from '@/composables/useLoader'
import { confirm } from '@/services/dialog'
import { useAuthStore } from '@/stores/auth'

interface UserForm {
  id: string | null
  email: string
  display_name: string
  password: string
  is_admin: boolean
  is_active: boolean
  groups: Array<{ id: string; name: string }>
}

const roleBadges = [
  { flag: 'is_admin', label: 'app.admin', classes: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' },
] as const

const { t } = useI18n()
const auth = useAuthStore()
const { busy, run } = useAction()
const users = ref<api.AdminUser[]>([])
// null while the list is shown
const form = ref<UserForm | null>(null)
const showPassword = ref(false)
const pickedGroupId = ref<string | null>(null)
const pickedGroup = ref<api.SearchResult | null>(null)
const generatedPassword = ref<string | null>(null)
// The row's menu of further actions, under its button.
const rowMenu = ref<{ userId: string; x: number; y: number; items: MenuItem[] } | null>(null)

const { loading } = useLoader(load)

async function load() {
  users.value = await api.listAdminUsers()
}

function generatePassword() {
  const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
  const bytes = crypto.getRandomValues(new Uint32Array(16))
  return Array.from(bytes, (byte) => chars.charAt(byte % chars.length)).join('')
}

/** Fills the field with a new random password and shows it, so it can be passed on. */
function fillGeneratedPassword() {
  if (!form.value) return
  form.value.password = generatePassword()
  showPassword.value = true
}

function openForm(user: api.AdminUser | null) {
  form.value = {
    id: user?.id ?? null,
    email: user?.email ?? '',
    display_name: user?.display_name ?? '',
    password: '',
    is_admin: user?.is_admin ?? false,
    is_active: user?.is_active ?? true,
    groups: user?.groups.map(({ id, name }) => ({ id, name })) ?? [],
  }
  showPassword.value = false
  pickedGroupId.value = null
}

function addGroup() {
  const group = pickedGroup.value
  if (form.value && group && !form.value.groups.some((g) => g.id === group.id)) {
    form.value.groups.push({ id: group.id, name: group.label })
  }
  pickedGroupId.value = null
}

function removeGroup(groupId: string) {
  if (form.value) form.value.groups = form.value.groups.filter((g) => g.id !== groupId)
}

async function save() {
  const value = form.value
  if (!value?.email || !value.display_name) return
  const data = {
    email: value.email,
    display_name: value.display_name,
    is_admin: value.is_admin,
    is_active: value.is_active,
    group_ids: value.groups.map((g) => g.id),
  }
  const withPassword = value.password ? { ...data, password: value.password } : data
  // Set inside the action, so typed by assertion: TypeScript would take it for null after it.
  let created = null as api.AdminUser | null
  const saved = await run(
    async () => {
      if (value.id) await api.updateAdminUser(value.id, withPassword)
      else created = await api.createAdminUser(withPassword)
      await load()
    },
    { failure: t('app.saveFailed') },
  )
  if (!saved) return
  form.value = null
  if (created) await sendInvitation(created)
}

/** Asks whether to email the user, after adding them or again later; one without a password chooses
 * it from the link in there. */
async function sendInvitation(user: api.AdminUser) {
  const text = user.has_password ? 'app.inviteUserText' : 'app.inviteUserTextNoPassword'
  if (!(await confirm(t(text, { name: user.display_name, email: user.email }), t('app.inviteUserTitle')))) return
  await run(() => api.inviteAdminUser(user.id), {
    success: t('app.inviteUserSent', { email: user.email }),
    failure: t('app.inviteUserFailed'),
  })
}

function openRowMenu(event: MouseEvent, user: api.AdminUser) {
  const rect = (event.currentTarget as Element).getBoundingClientRect()
  const items: MenuItem[] = [
    { label: t('app.inviteUser'), action: () => void sendInvitation(user) },
    { label: t('app.resetPassword'), action: () => void resetPassword(user) },
  ]
  if (user.id !== auth.user?.id) items.push({ label: t('app.delete'), action: () => void remove(user), danger: true })
  rowMenu.value = { userId: user.id, x: rect.right, y: rect.bottom + 4, items }
}

async function remove(user: api.AdminUser) {
  if (!(await confirm(t('app.deleteUserText', { name: user.display_name }), t('app.deleteUserTitle')))) return
  await run(
    async () => {
      await api.deleteAdminUser(user.id)
      await load()
    },
    { failure: t('app.deleteFailed') },
  )
}

async function resetPassword(user: api.AdminUser) {
  if (!(await confirm(t('app.resetPasswordText', { name: user.display_name }), t('app.resetPasswordTitle')))) return
  await run(async () => {
    generatedPassword.value = (await api.resetAdminUserPassword(user.id)).password
  })
}
</script>

<template>
  <SettingsPanel
    :title="!form ? $t('app.users') : form.id ? $t('app.editUser') : $t('app.addUser')"
    :description="$t('app.usersDescription')"
    :loading="loading"
    flush
  >
    <template v-if="!form" #actions>
      <button
        type="button"
        class="rounded-lg bg-blue-600 px-3 py-2 text-sm text-white hover:bg-blue-700"
        @click="openForm(null)"
      >
        {{ $t('app.addUser') }}
      </button>
    </template>

    <div v-if="!form" class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="bg-surface-muted text-left text-xs uppercase text-gray-500">
          <tr>
            <th class="px-4 py-2">{{ $t('app.nameLabel') }}</th>
            <th class="px-4 py-2">{{ $t('auth.email') }}</th>
            <th class="px-4 py-2">{{ $t('app.role') }}</th>
            <th class="px-4 py-2">{{ $t('app.status') }}</th>
            <th class="px-4 py-2 text-right">{{ $t('app.actions') }}</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-line">
          <tr v-for="user in users" :key="user.id" class="group hover:bg-hover">
            <td class="px-4 py-2 font-medium text-gray-800">{{ user.display_name }}</td>
            <td class="px-4 py-2 text-gray-600">{{ user.email }}</td>
            <td class="px-4 py-2">
              <div class="flex flex-wrap gap-1">
                <template v-for="badge in roleBadges" :key="badge.flag">
                  <span
                    v-if="user[badge.flag]"
                    class="inline-flex items-center rounded px-2 py-0.5 text-xs font-medium"
                    :class="badge.classes"
                  >
                    {{ $t(badge.label) }}
                  </span>
                </template>
                <span v-if="!roleBadges.some((badge) => user[badge.flag])" class="text-gray-500">—</span>
              </div>
            </td>
            <td class="px-4 py-2">
              <span
                class="inline-flex items-center rounded px-2 py-0.5 text-xs font-medium"
                :class="
                  user.is_active
                    ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                    : 'bg-surface-muted text-gray-800'
                "
              >
                {{ user.is_active ? $t('app.active') : $t('app.inactive') }}
              </span>
            </td>
            <td class="px-4 py-2">
              <div class="row-actions flex justify-end gap-1">
                <IconButton :label="$t('app.edit')" tone="primary" @click="openForm(user)">
                  <Pencil :size="18" :stroke-width="2.25" />
                </IconButton>
                <IconButton
                  :label="$t('app.moreActions')"
                  aria-haspopup="menu"
                  :aria-expanded="rowMenu?.userId === user.id"
                  @click="openRowMenu($event, user)"
                >
                  <EllipsisVertical :size="18" :stroke-width="2.25" />
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

    <div v-else class="space-y-4 p-6">
      <label class="block">
        <span class="mb-1 block text-sm font-medium text-gray-700">{{ $t('auth.displayName') }}</span>
        <input v-model="form.display_name" class="w-full rounded-lg border border-line px-3 py-2" />
      </label>
      <label class="block">
        <span class="mb-1 block text-sm font-medium text-gray-700">{{ $t('auth.email') }}</span>
        <input v-model="form.email" type="email" class="w-full rounded-lg border border-line px-3 py-2" />
      </label>
      <label class="block">
        <span class="mb-1 block text-sm font-medium text-gray-700">{{ $t('auth.password') }}</span>
        <div class="relative">
          <input
            v-model="form.password"
            :type="showPassword ? 'text' : 'password'"
            :placeholder="form.id ? $t('app.passwordUnchanged') : $t('app.passwordOptional')"
            class="w-full rounded-lg border border-line px-3 py-2 pr-20"
          />
          <div class="absolute right-2 top-1/2 flex -translate-y-1/2 gap-1">
            <IconButton :label="$t('app.generatePassword')" @click="fillGeneratedPassword">
              <Dices :size="18" :stroke-width="2.25" />
            </IconButton>
            <IconButton
              :label="showPassword ? $t('auth.hidePassword') : $t('auth.showPassword')"
              @click="showPassword = !showPassword"
            >
              <Eye v-if="showPassword" :size="18" :stroke-width="2.25" />
              <EyeOff v-else :size="18" :stroke-width="2.25" />
            </IconButton>
          </div>
        </div>
      </label>
      <div class="grid gap-3 sm:grid-cols-2">
        <SettingsToggle v-model="form.is_admin" :title="$t('app.admin')" :description="$t('app.adminDescription')" />
        <SettingsToggle v-model="form.is_active" :title="$t('app.active')" :description="$t('app.activeDescription')" />
      </div>
      <div>
        <h3 class="mb-3 text-sm font-semibold text-gray-700">{{ $t('app.groups') }}</h3>
        <ul v-if="form.groups.length" class="mb-4 space-y-2">
          <li
            v-for="group in form.groups"
            :key="group.id"
            class="flex items-center justify-between rounded-lg bg-surface-muted px-3 py-2"
          >
            <span class="text-sm font-medium text-gray-800">{{ group.name }}</span>
            <IconButton :label="$t('app.delete')" tone="danger" @click="removeGroup(group.id)">
              <X :size="18" :stroke-width="2.25" />
            </IconButton>
          </li>
        </ul>
        <p v-else class="mb-4 text-sm text-gray-500">{{ $t('app.noGroups') }}</p>

        <div class="flex items-end gap-2">
          <label class="flex-1">
            <span class="mb-1 block text-sm font-medium text-gray-700">{{ $t('app.addGroup') }}</span>
            <SearchableSelect
              v-model="pickedGroupId"
              entity="groups"
              open-on-focus
              @select="(_id, option) => (pickedGroup = option)"
            />
          </label>
          <button
            type="button"
            :disabled="!pickedGroupId"
            :aria-label="$t('app.addGroup')"
            class="rounded-lg bg-blue-600 px-3 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
            @click="addGroup"
          >
            <Plus :size="18" />
          </button>
        </div>
      </div>
      <div class="flex justify-end gap-3">
        <button type="button" class="rounded-lg border border-line px-4 py-2 hover:bg-hover" @click="form = null">
          {{ $t('app.cancel') }}
        </button>
        <button
          type="button"
          :disabled="!form.email || !form.display_name || busy"
          class="rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
          @click="save"
        >
          {{ $t('app.save') }}
        </button>
      </div>
    </div>
  </SettingsPanel>

  <ContextMenu v-if="rowMenu" :x="rowMenu.x" :y="rowMenu.y" :items="rowMenu.items" align-end @close="rowMenu = null" />

  <AppModal :open="!!generatedPassword" :title="$t('app.newPassword')" @close="generatedPassword = null">
    <div class="rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-800">
      <p class="mb-1">{{ $t('app.passwordGeneratedInfo') }}</p>
      <code class="font-mono font-semibold">{{ generatedPassword }}</code>
    </div>
    <template #footer>
      <div class="flex justify-end">
        <button
          type="button"
          class="rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
          @click="generatedPassword = null"
        >
          {{ $t('app.ok') }}
        </button>
      </div>
    </template>
  </AppModal>
</template>
