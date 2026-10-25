<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ChevronRight, Trash2, Users } from '@lucide/vue'
import * as api from '@/api'
import AccessGrantSearch, { type AccessGrantTarget } from '@/components/AccessGrantSearch.vue'
import IconButton from '@/components/IconButton.vue'
import RoleSelect from '@/components/RoleSelect.vue'
import SettingsPanel from '@/components/SettingsPanel.vue'
import SettingsToggle from '@/components/SettingsToggle.vue'
import { useAction } from '@/composables/useAction'
import { useLoader } from '@/composables/useLoader'
import { useCalendarSettingsSync } from '@/composables/useCalendarSettingsSync'
import { ROLE_ORDER } from '@/services/roles'
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

// Everything here is edited locally and sent with Save; until then nothing changes for anyone.
const isPublic = ref(props.calendar.is_public)
const publicRole = ref<api.PublicRole>(props.calendar.public_role)
const members = ref<api.CalendarMember[]>([])
const groupLinks = ref<api.CalendarGroupLink[]>([])
// As saved, to send only what changed.
let savedMembers: api.CalendarMember[] = []
let savedGroupLinks: api.CalendarGroupLink[] = []

// Picking someone adds them with the least privileged role; the role is changed in the new row.
const NEW_ROLE: api.GrantableRole = 'read'
// Rows added here and not saved yet have ids of their own.
const NEW_ID = 'new:'
const expandedGroups = ref(new Set<string>())
// The best role a person gets through groups; the highest of all their groups applies.
const bestGroupRole = computed(() => {
  const best = new Map<string, number>()
  for (const link of groupLinks.value) {
    for (const user of link.members) best.set(user.id, Math.max(best.get(user.id) ?? 0, ROLE_ORDER.indexOf(link.role)))
  }
  return best
})
// What each role allows, shown once above the access list instead of under every role field.
const ROLE_LEGEND = ROLE_ORDER

const memberIds = computed(() => new Set(members.value.map((m) => m.user_id)))
const groupIds = computed(() => new Set(groupLinks.value.map((l) => l.group.id)))

// Group links are only visible to owners.
const { loading } = useLoader(() => Promise.all(props.canManage ? [loadMembers(), loadGroupLinks()] : [loadMembers()]))

async function loadMembers() {
  savedMembers = await api.listMembers(props.calendar.id)
  members.value = savedMembers.map((m) => ({ ...m }))
}

async function loadGroupLinks() {
  savedGroupLinks = await api.listCalendarGroups(props.calendar.id)
  groupLinks.value = savedGroupLinks.map((l) => ({ ...l }))
}

async function addAccess(target: AccessGrantTarget) {
  if (target.kind === 'user') {
    // Removed and picked again: the saved row comes back with its role.
    const saved = savedMembers.find((m) => m.user_id === target.id)
    members.value.push(
      saved
        ? { ...saved }
        : {
            id: NEW_ID + target.id,
            calendar_id: props.calendar.id,
            user_id: target.id,
            email: target.subtitle ?? '',
            display_name: target.label,
            role: NEW_ROLE,
            folder_id: null,
            position: 0,
          },
    )
    return
  }
  const saved = savedGroupLinks.find((l) => l.group.id === target.id)
  if (saved) {
    groupLinks.value.push({ ...saved })
    return
  }
  // Its members show who gets access through it (and whose role it overrides).
  const group = await api.getUserGroup(target.id).catch(() => null)
  groupLinks.value.push({
    id: NEW_ID + target.id,
    group: { id: target.id, name: target.label },
    role: NEW_ROLE,
    members: group?.members ?? [],
  })
}

function removeMember(userId: string) {
  members.value = members.value.filter((m) => m.user_id !== userId)
}

function removeGroupLink(linkId: string) {
  groupLinks.value = groupLinks.value.filter((l) => l.id !== linkId)
}

function save() {
  let membersChanged = false
  return run(
    async () => {
      try {
        await send()
      } finally {
        // Also after a failure part way: what was sent counts as saved from now on.
        await Promise.all([loadMembers(), loadGroupLinks()])
        // The other tabs list members, too (the approvers), and a removed one is no approver any more.
        if (membersChanged) sync.membersChanged()
      }
    },
    { success: t('app.accessSettingsSaved'), failure: t('app.saveFailed') },
  )

  async function send() {
    const id = props.calendar.id
    if (
      isPublic.value !== props.calendar.is_public ||
      (isPublic.value && publicRole.value !== props.calendar.public_role)
    ) {
      const data: Partial<api.Calendar> = { is_public: isPublic.value }
      if (isPublic.value) data.public_role = publicRole.value
      emit('updated', await calendarStore.updateCalendar(id, data))
    }

    for (const saved of savedMembers) {
      if (saved.role === 'owner' || memberIds.value.has(saved.user_id)) continue
      await api.removeMember(id, saved.user_id)
      membersChanged = true
    }
    for (const member of members.value) {
      if (member.role === 'owner') continue
      const saved = savedMembers.find((m) => m.user_id === member.user_id)
      if (!saved) {
        await api.addMember(id, member.user_id, member.role as api.GrantableRole)
        membersChanged = true
      } else if (saved.role !== member.role) {
        await api.updateMember(id, member.user_id, member.role as api.GrantableRole)
      }
    }

    for (const saved of savedGroupLinks) {
      if (!groupLinks.value.some((l) => l.id === saved.id)) await api.removeCalendarGroup(id, saved.id)
    }
    for (const link of groupLinks.value) {
      const saved = savedGroupLinks.find((l) => l.id === link.id)
      if (!saved) await api.addCalendarGroup(id, { group_id: link.group.id, role: link.role })
      else if (saved.role !== link.role) await api.updateCalendarGroup(id, link.id, { role: link.role })
    }
  }
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
</script>

<template>
  <SettingsPanel :title="$t('app.access')" :description="$t('app.accessDescription')" :loading="loading">
    <div class="space-y-6">
      <dl class="grid gap-x-6 gap-y-1.5 rounded-lg bg-surface-muted px-4 py-3 text-xs sm:grid-cols-2">
        <div v-for="role in ROLE_LEGEND" :key="role">
          <dt class="inline font-semibold text-gray-700">{{ $t(`roles.${role}`) }}:</dt>
          {{ ' ' }}
          <dd class="inline text-gray-500">{{ $t(`roles.${role}Description`) }}</dd>
        </div>
      </dl>

      <div v-if="canManage" class="grid items-start gap-4 sm:grid-cols-2">
        <SettingsToggle
          v-model="isPublic"
          :title="$t('app.publicCalendar')"
          :description="$t('app.publicCalendarHelp')"
        />
        <label v-if="isPublic" class="block">
          <span class="mb-1 block text-sm font-medium text-gray-800">{{ $t('app.publicRole') }}</span>
          <RoleSelect v-model="publicRole" public-access />
        </label>
      </div>

      <div class="space-y-4" :class="{ 'border-t border-line pt-6': canManage }">
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
            class="group flex flex-wrap items-center gap-x-2 gap-y-2 px-3 py-2.5 hover:bg-hover sm:flex-nowrap sm:gap-3 sm:px-4"
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
              class="role-field"
              :model-value="member.role as api.GrantableRole"
              :disabled="busy"
              @update:model-value="member.role = $event"
            />
            <span v-else class="role-field text-sm text-gray-500 sm:px-3">{{ $t(`roles.${member.role}`) }}</span>
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
            <div
              class="flex flex-wrap items-center gap-x-2 gap-y-2 px-3 py-2.5 hover:bg-hover sm:flex-nowrap sm:gap-3 sm:px-4"
            >
              <button
                type="button"
                class="flex min-w-0 flex-1 items-center gap-2 text-left sm:gap-3"
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
                class="role-field"
                :model-value="link.role"
                :disabled="busy"
                @update:model-value="link.role = $event"
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
    </div>

    <template v-if="canManage" #footer>
      <button
        type="button"
        :disabled="busy"
        class="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
        @click="save"
      >
        {{ $t('app.save') }}
      </button>
    </template>
  </SettingsPanel>
</template>

<style scoped>
/*
 * The role field of a row: next to the name where there is room, else on a line of its own below the
 * name (phones), so neither the name nor the role gets cut off.
 */
.role-field {
  order: 1;
  flex-shrink: 0;
  width: calc(100% - 2.5rem);
  margin-left: 2.5rem;
}

@media (width >= 40rem) {
  .role-field {
    order: 0;
    width: 11rem;
    margin-left: 0;
  }
}
</style>
