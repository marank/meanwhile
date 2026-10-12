<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ChevronRight, Trash2, Users } from 'lucide-vue-next'
import * as api from '@/api'
import AccessGrantSearch from '@/components/AccessGrantSearch.vue'
import IconButton from '@/components/IconButton.vue'
import RoleSelect from '@/components/RoleSelect.vue'
import SettingsPanel from '@/components/SettingsPanel.vue'
import SettingsToggle from '@/components/SettingsToggle.vue'
import { useAction } from '@/composables/useAction'
import { useLoader } from '@/composables/useLoader'
import { useCalendarSettingsSync } from '@/composables/useCalendarSettingsSync'
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
const sync = useCalendarSettingsSync()

const isPublic = ref(props.calendar.is_public)
const publicRole = ref<api.GrantableRole>(props.calendar.public_role)
const members = ref<api.CalendarMember[]>([])
const groupLinks = ref<api.CalendarGroupLink[]>([])

// Picking someone adds them with the least privileged role; the role is changed in the new row.
const NEW_ROLE: api.GrantableRole = 'read'
const expandedGroups = ref(new Set<string>())
const ROLE_ORDER: api.CalendarRole[] = ['read', 'own', 'full', 'owner']
// The best role a person gets through groups; the highest of all their groups applies.
const bestGroupRole = computed(() => {
  const best = new Map<string, number>()
  for (const link of groupLinks.value) {
    for (const user of link.members) best.set(user.id, Math.max(best.get(user.id) ?? 0, ROLE_ORDER.indexOf(link.role)))
  }
  return best
})
const memberIds = computed(() => new Set(members.value.map((m) => m.user_id)))
const groupIds = computed(() => new Set(groupLinks.value.map((l) => l.group.id)))

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

async function addMember(userId: string) {
  await run(
    async () => {
      await api.addMember(props.calendar.id, userId, NEW_ROLE)
      await loadMembers()
      sync.membersChanged()
    },
    { success: t('app.memberAdded') },
  )
}

function updateMember(userId: string, role: api.GrantableRole) {
  return run(async () => {
    await api.updateMember(props.calendar.id, userId, role)
    await loadMembers()
  })
}

async function removeMember(userId: string) {
  if (!(await confirm(t('app.removeMemberText'), t('app.removeMemberTitle')))) return
  await run(
    async () => {
      await api.removeMember(props.calendar.id, userId)
      await loadMembers()
      // The other tabs list members, too (the approvers), and a removed one is no approver any more.
      sync.membersChanged()
    },
    { success: t('app.memberRemoved') },
  )
}

async function addGroupLink(groupId: string) {
  await run(async () => {
    await api.addCalendarGroup(props.calendar.id, { group_id: groupId, role: NEW_ROLE })
    await loadGroupLinks()
  })
}

function addAccess(target: { kind: 'user' | 'group'; id: string }) {
  return target.kind === 'user' ? addMember(target.id) : addGroupLink(target.id)
}

/** A direct role replaces every group role, and a group role is replaced by a higher one from another group. */
function isOverridden(link: api.CalendarGroupLink, userId: string) {
  return memberIds.value.has(userId) || (bestGroupRole.value.get(userId) ?? 0) > ROLE_ORDER.indexOf(link.role)
}

function toggleGroup(id: string) {
  if (!expandedGroups.value.delete(id)) expandedGroups.value.add(id)
}

function initial(name: string) {
  return (name || '?').charAt(0).toUpperCase()
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
  <div class="space-y-6">
    <SettingsPanel
      v-if="canManage"
      :title="$t('app.publicCalendar')"
      :description="$t('app.publicCalendarHelp')"
      :loading="loading"
    >
      <div class="grid items-start gap-4 sm:grid-cols-2">
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
      <template #footer>
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

    <SettingsPanel :title="$t('app.access')" :description="$t('app.accessDescription')" :loading="loading">
      <div class="space-y-4">
        <AccessGrantSearch
          v-if="canManage"
          :placeholder="$t('app.addAccessPlaceholder')"
          :disabled="busy"
          :exclude-user-ids="memberIds"
          :exclude-group-ids="groupIds"
          groups
          @pick="addAccess"
        />

        <ul class="divide-y divide-line rounded-lg border border-line">
          <li
            v-for="member in members"
            :key="member.id"
            class="group flex items-center gap-3 px-4 py-2.5 hover:bg-hover"
          >
            <span
              class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-100 text-sm font-semibold text-blue-700 dark:bg-blue-900 dark:text-blue-200"
              aria-hidden="true"
            >
              {{ initial(member.display_name) }}
            </span>
            <div class="min-w-0 flex-1">
              <div class="truncate text-sm font-medium text-gray-800">{{ member.display_name }}</div>
              <div class="truncate text-xs text-gray-500">{{ member.email }}</div>
            </div>
            <RoleSelect
              v-if="canManage && member.role !== 'owner'"
              compact
              hide-description
              class="w-44 shrink-0"
              :model-value="member.role as api.GrantableRole"
              :disabled="busy"
              @update:model-value="updateMember(member.user_id, $event)"
            />
            <span v-else class="w-44 shrink-0 px-3 text-sm text-gray-500">{{ $t(`roles.${member.role}`) }}</span>
            <div class="row-actions flex w-8 shrink-0 justify-end">
              <IconButton
                v-if="canManage && member.role !== 'owner'"
                :label="$t('app.delete')"
                tone="danger"
                :disabled="busy"
                @click="removeMember(member.user_id)"
              >
                <Trash2 :size="18" :stroke-width="2.25" />
              </IconButton>
            </div>
          </li>

          <li v-for="link in groupLinks" :key="link.id" class="group">
            <div class="flex items-center gap-3 px-4 py-2.5 hover:bg-hover">
              <button
                type="button"
                class="flex min-w-0 flex-1 items-center gap-3 text-left"
                :aria-expanded="expandedGroups.has(link.id)"
                @click="toggleGroup(link.id)"
              >
                <span
                  class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface-muted text-gray-500"
                  aria-hidden="true"
                >
                  <Users :size="16" />
                </span>
                <span class="min-w-0 flex-1">
                  <span class="block truncate text-sm font-medium text-gray-800">{{ link.group.name }}</span>
                  <span class="block text-xs text-gray-500">
                    {{ $t('app.groupMemberCount', link.members.length) }}
                  </span>
                </span>
                <ChevronRight
                  :size="16"
                  class="shrink-0 text-gray-400 transition-transform"
                  :class="{ 'rotate-90': expandedGroups.has(link.id) }"
                />
              </button>
              <RoleSelect
                compact
                hide-description
                class="w-44 shrink-0"
                :model-value="link.role"
                :disabled="busy"
                @update:model-value="updateGroupLink(link.id, $event)"
              />
              <div class="row-actions flex w-8 shrink-0 justify-end">
                <IconButton :label="$t('app.delete')" tone="danger" :disabled="busy" @click="removeGroupLink(link.id)">
                  <Trash2 :size="18" :stroke-width="2.25" />
                </IconButton>
              </div>
            </div>
            <ul v-if="expandedGroups.has(link.id)" class="border-t border-line bg-surface-muted/40">
              <li
                v-for="user in link.members"
                :key="user.id"
                class="flex items-center gap-3 py-2 pl-14 pr-4"
                :class="{ 'opacity-50': isOverridden(link, user.id) }"
              >
                <span
                  class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-100 text-xs font-semibold text-blue-700 dark:bg-blue-900 dark:text-blue-200"
                  aria-hidden="true"
                >
                  {{ initial(user.display_name) }}
                </span>
                <span class="truncate text-sm text-gray-800">{{ user.display_name }}</span>
                <span class="truncate text-xs text-gray-500">{{ user.email }}</span>
                <span v-if="isOverridden(link, user.id)" class="ml-auto shrink-0 text-xs text-gray-500">
                  {{ $t('app.overridden') }}
                </span>
              </li>
              <li v-if="!link.members.length" class="py-3 pl-14 text-sm text-gray-500">
                {{ $t('app.groupHasNoMembers') }}
              </li>
            </ul>
          </li>

          <li v-if="!members.length && !groupLinks.length" class="px-4 py-8 text-center text-sm text-gray-500">
            {{ $t('app.noMembers') }}
          </li>
        </ul>
      </div>
    </SettingsPanel>
  </div>
</template>
