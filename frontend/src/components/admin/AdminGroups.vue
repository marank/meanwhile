<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Pencil, Plus, Trash2, X } from 'lucide-vue-next'
import * as api from '@/api'
import IconButton from '@/components/IconButton.vue'
import SearchableSelect from '@/components/SearchableSelect.vue'
import SettingsPanel from '@/components/SettingsPanel.vue'
import { useAction } from '@/composables/useAction'
import { useLoader } from '@/composables/useLoader'
import { confirm } from '@/services/dialog'

interface GroupForm {
  id: string | null
  name: string
  description: string
  members: api.UserGroupMember[]
}

const { t } = useI18n()
const { busy, run } = useAction()
const groups = ref<api.UserGroup[]>([])
// null while the list is shown
const form = ref<GroupForm | null>(null)
const pickedUserId = ref<string | null>(null)
const pickedUser = ref<api.SearchResult | null>(null)

const { loading } = useLoader(load)

async function load() {
  groups.value = await api.listUserGroups()
}

function startAdd() {
  form.value = { id: null, name: '', description: '', members: [] }
  pickedUserId.value = null
}

async function startEdit(group: api.UserGroup) {
  await run(
    async () => {
      const detail = await api.getUserGroup(group.id)
      form.value = {
        id: group.id,
        name: group.name,
        description: group.description ?? '',
        members: detail.members,
      }
      pickedUserId.value = null
    },
    { failure: t('app.loadFailed') },
  )
}

function addMember() {
  const user = pickedUser.value
  if (form.value && user && !form.value.members.some((m) => m.id === user.id)) {
    form.value.members.push({ id: user.id, display_name: user.label, email: user.subtitle ?? '' })
  }
  pickedUserId.value = null
}

function removeMember(memberId: string) {
  if (form.value) form.value.members = form.value.members.filter((m) => m.id !== memberId)
}

async function save() {
  const value = form.value
  if (!value?.name) return
  const data = {
    name: value.name,
    description: value.description || null,
    member_ids: value.members.map((m) => m.id),
  }
  const saved = await run(
    async () => {
      if (value.id) await api.updateUserGroup(value.id, data)
      else await api.createUserGroup(data)
      await load()
    },
    { failure: t('app.saveFailed') },
  )
  if (saved) form.value = null
}

async function remove(group: api.UserGroup) {
  if (!(await confirm(t('app.deleteGroupText', { name: group.name }), t('app.deleteGroupTitle')))) return
  await run(
    async () => {
      await api.deleteUserGroup(group.id)
      await load()
    },
    { failure: t('app.deleteFailed') },
  )
}
</script>

<template>
  <SettingsPanel
    :title="!form ? $t('app.groups') : form.id ? $t('app.editGroup') : $t('app.addGroup')"
    :description="$t('app.groupsDescription')"
    :loading="loading"
    flush
  >
    <template v-if="!form" #actions>
      <button
        type="button"
        class="rounded-lg bg-blue-600 px-3 py-2 text-sm text-white hover:bg-blue-700"
        @click="startAdd"
      >
        {{ $t('app.addGroup') }}
      </button>
    </template>

    <div v-if="!form" class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="bg-surface-muted text-left text-xs uppercase text-gray-500">
          <tr>
            <th class="px-4 py-2">{{ $t('app.groupName') }}</th>
            <th class="px-4 py-2">{{ $t('app.groupDescription') }}</th>
            <th class="px-4 py-2">{{ $t('app.members') }}</th>
            <th class="px-4 py-2 text-right">{{ $t('app.actions') }}</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-line">
          <tr v-for="group in groups" :key="group.id" class="group hover:bg-hover">
            <td class="px-4 py-2 font-medium text-gray-800">{{ group.name }}</td>
            <td class="px-4 py-2 text-gray-600">
              <span v-if="group.description" class="line-clamp-1">{{ group.description }}</span>
              <span v-else class="text-gray-400">—</span>
            </td>
            <td class="px-4 py-2 text-gray-600">{{ group.member_count ?? 0 }}</td>
            <td class="px-4 py-2">
              <div class="row-actions flex justify-end gap-1">
                <IconButton :label="$t('app.edit')" tone="primary" :disabled="busy" @click="startEdit(group)">
                  <Pencil :size="18" :stroke-width="2.25" />
                </IconButton>
                <IconButton :label="$t('app.delete')" tone="danger" :disabled="busy" @click="remove(group)">
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

    <div v-else class="space-y-6 p-6">
      <div class="space-y-4">
        <label class="block">
          <span class="mb-1 block text-sm font-medium text-gray-700">{{ $t('app.groupName') }}</span>
          <input v-model="form.name" class="w-full rounded-lg border border-line px-3 py-2" />
        </label>
        <label class="block">
          <span class="mb-1 block text-sm font-medium text-gray-700">{{ $t('app.groupDescription') }}</span>
          <textarea
            v-model="form.description"
            rows="3"
            class="w-full rounded-lg border border-line px-3 py-2"
          ></textarea>
        </label>
      </div>

      <div class="border-t border-line pt-4">
        <h3 class="mb-3 text-sm font-semibold text-gray-700">{{ $t('app.members') }}</h3>
        <ul v-if="form.members.length" class="mb-4 space-y-2">
          <li
            v-for="member in form.members"
            :key="member.id"
            class="flex items-center justify-between rounded-lg bg-surface-muted px-3 py-2"
          >
            <div>
              <p class="text-sm font-medium text-gray-800">{{ member.display_name }}</p>
              <p class="text-xs text-gray-500">{{ member.email }}</p>
            </div>
            <IconButton :label="$t('app.removeMember')" tone="danger" @click="removeMember(member.id)">
              <X :size="18" :stroke-width="2.25" />
            </IconButton>
          </li>
        </ul>
        <p v-else class="mb-4 text-sm text-gray-500">{{ $t('app.noMembers') }}</p>

        <div class="flex items-end gap-2">
          <label class="flex-1">
            <span class="mb-1 block text-sm font-medium text-gray-700">{{ $t('app.addMember') }}</span>
            <SearchableSelect
              v-model="pickedUserId"
              entity="users"
              :min-search-length="2"
              :placeholder="$t('app.searchUsers')"
              @select="(_id, option) => (pickedUser = option)"
            />
          </label>
          <button
            type="button"
            :disabled="!pickedUserId"
            :aria-label="$t('app.addMember')"
            class="rounded-lg bg-blue-600 px-3 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
            @click="addMember"
          >
            <Plus :size="18" />
          </button>
        </div>
      </div>

      <div class="flex justify-end gap-3 border-t border-line pt-4">
        <button type="button" class="rounded-lg border border-line px-4 py-2 hover:bg-hover" @click="form = null">
          {{ $t('app.cancel') }}
        </button>
        <button
          type="button"
          :disabled="!form.name || busy"
          class="rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
          @click="save"
        >
          {{ $t('app.save') }}
        </button>
      </div>
    </div>
  </SettingsPanel>
</template>
