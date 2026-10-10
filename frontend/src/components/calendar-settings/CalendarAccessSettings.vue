<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Plus } from 'lucide-vue-next'
import * as api from '@/api'
import RoleSelect from '@/components/RoleSelect.vue'
import SearchableSelect from '@/components/SearchableSelect.vue'
import SettingsPanel from '@/components/SettingsPanel.vue'
import SettingsToggle from '@/components/SettingsToggle.vue'
import { useAction } from '@/composables/useAction'
import { useLoader } from '@/composables/useLoader'
import { confirm } from '@/services/dialog'
import { useCalendarStore } from '@/stores/calendars'

const props = defineProps<{
  calendar: api.Calendar
  canManage: boolean
}>()

const emit = defineEmits<{
  updated: [calendar: api.Calendar]
}>()

const { t } = useI18n()
const calendarStore = useCalendarStore()
const { busy, run } = useAction()

const isPublic = ref(props.calendar.is_public)
const publicRole = ref<api.GrantableRole>(props.calendar.public_role)
const members = ref<api.CalendarMember[]>([])
const groupLinks = ref<api.CalendarGroupLink[]>([])
const newMemberId = ref<string | null>(null)
const newMemberRole = ref<api.GrantableRole>('contributor')
const newGroupId = ref<string | null>(null)
const newGroupRole = ref<api.GrantableRole>('viewer')

// Group links are only visible to owners.
const { loading } = useLoader(() => Promise.all(props.canManage ? [loadMembers(), loadGroupLinks()] : [loadMembers()]))

async function loadMembers() {
  members.value = await api.listMembers(props.calendar.id)
}

async function loadGroupLinks() {
  groupLinks.value = await api.listCalendarGroups(props.calendar.id)
}

function savePublicAccess() {
  const data: Partial<api.Calendar> = { is_public: isPublic.value }
  if (isPublic.value) data.public_role = publicRole.value
  return run(
    async () => {
      emit('updated', await calendarStore.updateCalendar(props.calendar.id, data))
    },
    { success: t('app.accessSettingsSaved'), failure: t('app.saveFailed') },
  )
}

async function addMember() {
  const userId = newMemberId.value
  if (!userId) return
  await run(
    async () => {
      await api.addMember(props.calendar.id, userId, newMemberRole.value)
      newMemberId.value = null
      await loadMembers()
    },
    { success: t('app.memberAdded') },
  )
}

async function removeMember(userId: string) {
  if (!(await confirm(t('app.removeMemberText'), t('app.removeMemberTitle')))) return
  await run(
    async () => {
      await api.removeMember(props.calendar.id, userId)
      await loadMembers()
    },
    { success: t('app.memberRemoved') },
  )
}

async function addGroupLink() {
  const groupId = newGroupId.value
  if (!groupId) return
  await run(async () => {
    await api.addCalendarGroup(props.calendar.id, { group_id: groupId, role: newGroupRole.value })
    newGroupId.value = null
    await loadGroupLinks()
  })
}

function updateGroupLink(linkId: string, role: api.GrantableRole) {
  return run(async () => {
    await api.updateCalendarGroup(props.calendar.id, linkId, { role })
    await loadGroupLinks()
  })
}

async function removeGroupLink(linkId: string) {
  if (!(await confirm(t('app.removeGroupAccessText'), t('app.removeGroupAccessTitle')))) return
  await run(
    async () => {
      await api.removeCalendarGroup(props.calendar.id, linkId)
      await loadGroupLinks()
    },
    { success: t('app.groupAccessRemoved') },
  )
}
</script>

<template>
  <SettingsPanel :title="$t('app.access')" :description="$t('app.accessDescription')" :loading="loading">
    <div class="space-y-6">
      <template v-if="canManage">
        <section class="space-y-3">
          <h3 class="text-sm font-semibold text-gray-800">{{ $t('app.publicCalendar') }}</h3>
          <div class="grid items-start gap-3 sm:grid-cols-2">
            <SettingsToggle
              v-model="isPublic"
              :title="$t('app.publicCalendar')"
              :description="$t('app.publicCalendarHelp')"
            />
            <label v-if="isPublic" class="block">
              <span class="mb-1 block text-sm font-medium text-gray-800">{{ $t('app.publicRole') }}</span>
              <RoleSelect v-model="publicRole" />
            </label>
          </div>
        </section>

        <section class="space-y-4 border-t border-line pt-6">
          <h3 class="text-sm font-semibold text-gray-800">{{ $t('app.groupAccess') }}</h3>
          <div class="flex items-start gap-2">
            <SearchableSelect v-model="newGroupId" entity="groups" open-on-focus class="flex-1" />
            <RoleSelect v-model="newGroupRole" class="w-48" />
            <button
              type="button"
              :disabled="!newGroupId || busy"
              :aria-label="$t('app.add')"
              class="rounded-lg bg-blue-600 px-3 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
              @click="addGroupLink"
            >
              <Plus :size="18" />
            </button>
          </div>
          <ul class="divide-y divide-line rounded-lg border">
            <li
              v-for="link in groupLinks"
              :key="link.id"
              class="flex items-center justify-between px-3 py-2 hover:bg-hover"
            >
              <span class="text-sm text-gray-800">{{ link.group.name }}</span>
              <div class="flex items-start gap-2">
                <RoleSelect
                  compact
                  :model-value="link.role"
                  :disabled="busy"
                  @update:model-value="updateGroupLink(link.id, $event)"
                />
                <button type="button" class="text-sm text-red-600 hover:underline" @click="removeGroupLink(link.id)">
                  {{ $t('app.delete') }}
                </button>
              </div>
            </li>
            <li v-if="!groupLinks.length" class="px-3 py-6 text-center text-sm text-gray-500">
              {{ $t('app.noGroupAccess') }}
            </li>
          </ul>
        </section>
      </template>

      <section class="space-y-4" :class="{ 'border-t border-line pt-6': canManage }">
        <h3 class="text-sm font-semibold text-gray-800">{{ $t('app.members') }}</h3>
        <ul class="divide-y divide-line">
          <li v-for="member in members" :key="member.id" class="flex items-center justify-between py-2">
            <div>
              <div class="font-medium text-gray-800">{{ member.display_name }} ({{ member.email }})</div>
              <div class="text-xs text-gray-500">{{ $t(`roles.${member.role}`) }}</div>
            </div>
            <button
              v-if="canManage && member.role !== 'owner'"
              type="button"
              class="text-sm text-red-600 hover:underline"
              @click="removeMember(member.user_id)"
            >
              {{ $t('app.delete') }}
            </button>
          </li>
        </ul>

        <div v-if="canManage" class="flex items-start gap-2">
          <SearchableSelect
            v-model="newMemberId"
            entity="users"
            :min-search-length="2"
            :placeholder="$t('app.searchUsers')"
            class="flex-1"
          />
          <RoleSelect v-model="newMemberRole" class="w-48" />
          <button
            type="button"
            :disabled="!newMemberId || busy"
            :aria-label="$t('app.add')"
            class="rounded-lg bg-blue-600 px-3 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
            @click="addMember"
          >
            <Plus :size="18" />
          </button>
        </div>
      </section>
    </div>
    <template v-if="canManage" #footer>
      <button
        type="button"
        :disabled="busy"
        class="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
        @click="savePublicAccess"
      >
        {{ $t('app.save') }}
      </button>
    </template>
  </SettingsPanel>
</template>
