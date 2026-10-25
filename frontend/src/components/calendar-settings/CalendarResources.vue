<script setup lang="ts">
import { computed, nextTick, onActivated, onDeactivated, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Pencil, Trash2 } from '@lucide/vue'
import * as api from '@/api'
import IconButton from '@/components/IconButton.vue'
import PersonChip from '@/components/PersonChip.vue'
import SearchableSelect from '@/components/SearchableSelect.vue'
import SettingsPanel from '@/components/SettingsPanel.vue'
import ResourceIcon from '@/components/ResourceIcon.vue'
import ResourceIconPicker from '@/components/ResourceIconPicker.vue'
import SettingsToggle from '@/components/SettingsToggle.vue'
import { useAction } from '@/composables/useAction'
import { useLoader } from '@/composables/useLoader'
import { useCalendarSettingsSync } from '@/composables/useCalendarSettingsSync'
import { confirm } from '@/services/dialog'

interface ResourceForm {
  id: string | null
  name: string
  description: string
  color: string
  icon: string
  requires_approval: boolean
  is_location: boolean
  is_active: boolean
  approval_mode: 'default' | 'custom'
  approvers: api.Approver[]
}

const props = defineProps<{
  calendarId: string
  canManage: boolean
}>()

const { t } = useI18n()
const { busy, run } = useAction()
const resources = ref<api.Resource[]>([])
const defaultApprovers = ref<api.Approver[]>([])
const pickedDefaultApproverId = ref<string | null>(null)
const pickedResourceApproverId = ref<string | null>(null)
// null while the list is shown
const form = ref<ResourceForm | null>(null)

const defaultApproverNames = computed(() => defaultApprovers.value.map((a) => a.display_name).join(', '))
const formInvalid = computed(
  () =>
    !form.value?.name ||
    (form.value.requires_approval && form.value.approval_mode === 'custom' && !form.value.approvers.length),
)

const { loading } = useLoader(() => Promise.all([loadResources(), loadDefaultApprovers()]))

async function loadResources() {
  resources.value = await api.listResources(props.calendarId)
}

async function loadDefaultApprovers() {
  defaultApprovers.value = await api.listCalendarApprovers(props.calendarId)
}

// This tab stays alive while the access tab is open. When members are added or removed there, it
// loads again (at once if it is shown, else when it is next shown): a removed member is no approver
// any more, and the suggestions for approvers are the members.
const sync = useCalendarSettingsSync()
/** Counts up to renew the member suggestions, which load once when they appear. */
const suggestionsKey = ref(0)
let shown = true
let membersStale = false

async function refreshAfterMembersChanged() {
  const before = new Map(resources.value.map((r) => [r.id, r.approvers.map((a) => a.user_id)]))
  try {
    await Promise.all([loadResources(), loadDefaultApprovers()])
  } catch {
    // Keep what is shown; the next time this tab is shown, it tries again.
    membersStale = true
    return
  }
  suggestionsKey.value++
  // A resource being edited loses the approvers who were removed; what else was changed stays.
  const editing = form.value
  if (editing?.id) {
    const now = new Set(resources.value.find((r) => r.id === editing.id)?.approvers.map((a) => a.user_id))
    const removed = (before.get(editing.id) ?? []).filter((id) => !now.has(id))
    editing.approvers = editing.approvers.filter((a) => !removed.includes(a.user_id))
  }
}

watch(sync.membersVersion, () => {
  if (shown) void refreshAfterMembersChanged()
  else membersStale = true
})
onActivated(() => {
  shown = true
  if (membersStale) {
    membersStale = false
    void refreshAfterMembersChanged()
  }
})
onDeactivated(() => {
  shown = false
})

function approvalLabel(resource: api.Resource) {
  if (!resource.requires_approval) return t('app.approvalNone')
  if (resource.approvers.length) return resource.approvers.map((a) => a.display_name).join(', ')
  return `${t('app.approvalDefault')} (${defaultApproverNames.value || t('app.nobody')})`
}

// Default approvers

async function onDefaultApproverPicked(userId: string | null) {
  if (userId && !defaultApprovers.value.some((a) => a.user_id === userId)) {
    await run(
      async () => {
        defaultApprovers.value = await api.setCalendarApprovers(props.calendarId, [
          ...defaultApprovers.value.map((a) => a.user_id),
          userId,
        ])
      },
      { success: t('app.approverAdded') },
    )
  }
  pickedDefaultApproverId.value = null
}

async function removeDefaultApprover(userId: string) {
  if (!(await confirm(t('app.removeApproverText'), t('app.removeApproverTitle')))) return
  await run(
    async () => {
      defaultApprovers.value = await api.setCalendarApprovers(
        props.calendarId,
        defaultApprovers.value.map((a) => a.user_id).filter((id) => id !== userId),
      )
    },
    { success: t('app.approverRemoved') },
  )
}

// Resource form

function startAdd() {
  form.value = {
    id: null,
    name: '',
    description: '',
    color: '#f59e0b',
    icon: '',
    requires_approval: false,
    is_location: false,
    is_active: true,
    approval_mode: 'default',
    approvers: [],
  }
}

function startEdit(resource: api.Resource) {
  form.value = {
    id: resource.id,
    name: resource.name,
    description: resource.description,
    color: resource.color,
    icon: resource.icon,
    requires_approval: resource.requires_approval,
    is_location: resource.is_location,
    is_active: resource.is_active,
    approval_mode: resource.approvers.length ? 'custom' : 'default',
    approvers: [...resource.approvers],
  }
}

async function onResourceApproverPicked(userId: string | null, option: api.SearchResult | null) {
  const value = form.value
  if (value && userId && option && !value.approvers.some((a) => a.user_id === userId)) {
    value.approvers.push({ user_id: userId, display_name: option.label, email: option.subtitle ?? '' })
  }
  // Let the select show the pick for one tick before clearing it for the next search.
  await nextTick()
  pickedResourceApproverId.value = null
}

function removeFormApprover(userId: string) {
  if (form.value) form.value.approvers = form.value.approvers.filter((a) => a.user_id !== userId)
}

async function save() {
  const value = form.value
  if (!value || formInvalid.value) return
  const ownApprovers = value.requires_approval && value.approval_mode === 'custom'
  const data: api.ResourceInput = {
    name: value.name,
    description: value.description,
    color: value.color,
    icon: value.icon,
    requires_approval: value.requires_approval,
    is_location: value.is_location,
    is_active: value.is_active,
  }
  // Own approvers only apply while approval is required; otherwise the defaults take over.
  const approverIds = ownApprovers ? value.approvers.map((a) => a.user_id) : []
  const saved = await run(
    async () => {
      const before = value.id ? resources.value.find((r) => r.id === value.id)?.approvers.map((a) => a.user_id) : []
      const resource = value.id
        ? await api.updateResource(props.calendarId, value.id, data)
        : await api.createResource(props.calendarId, data)
      if ([...approverIds].sort().join() !== [...(before ?? [])].sort().join()) {
        await api.setResourceApprovers(props.calendarId, resource.id, approverIds)
      }
      await loadResources()
    },
    { success: t('app.resourceSaved'), failure: t('app.saveFailed') },
  )
  if (saved) form.value = null
}

async function remove(id: string) {
  if (!(await confirm(t('app.deleteResourceText'), t('app.deleteResourceTitle')))) return
  await run(
    async () => {
      await api.deleteResource(props.calendarId, id)
      await loadResources()
    },
    { failure: t('app.deleteFailed') },
  )
}
</script>

<template>
  <SettingsPanel :title="$t('app.resources')" :description="$t('app.resourcesDescription')" :loading="loading" flush>
    <template v-if="!form && canManage" #actions>
      <button
        type="button"
        class="rounded-lg bg-blue-600 px-3 py-2 text-sm text-white hover:bg-blue-700"
        @click="startAdd"
      >
        {{ $t('app.add') }}
      </button>
    </template>

    <div v-if="!form">
      <section class="space-y-3 border-b border-line px-5 py-4 sm:px-6">
        <div>
          <h3 class="text-sm font-semibold text-gray-800">{{ $t('app.defaultApprovers') }}</h3>
          <p class="mt-0.5 text-sm text-gray-500">{{ $t('app.defaultApproversDescription') }}</p>
        </div>
        <ul v-if="defaultApprovers.length" class="flex flex-wrap gap-2">
          <PersonChip
            v-for="approver in defaultApprovers"
            :key="approver.user_id"
            :name="approver.display_name"
            :email="approver.email"
            :removable="canManage"
            :disabled="busy"
            @remove="removeDefaultApprover(approver.user_id)"
          />
        </ul>
        <p v-else class="text-sm text-gray-500">{{ $t('app.noDefaultApprovers') }}</p>
        <div v-if="canManage" class="sm:w-1/2">
          <SearchableSelect
            :key="`default-${suggestionsKey}`"
            v-model="pickedDefaultApproverId"
            entity="members"
            :calendar-id="calendarId"
            open-on-focus
            :placeholder="$t('app.addApprover')"
            :disabled="busy"
            @select="onDefaultApproverPicked"
          />
        </div>
      </section>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="bg-surface-muted text-left text-xs uppercase text-gray-500">
            <tr>
              <th class="w-16 px-4 py-2">{{ $t('app.color') }}</th>
              <th class="px-4 py-2">{{ $t('app.nameLabel') }}</th>
              <th class="px-4 py-2">{{ $t('event.description') }}</th>
              <th class="px-4 py-2">{{ $t('app.approval') }}</th>
              <th class="px-4 py-2">{{ $t('app.status') }}</th>
              <th class="px-4 py-2 text-right">{{ $t('app.actions') }}</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-line">
            <tr
              v-for="resource in resources"
              :key="resource.id"
              class="group hover:bg-hover"
              :class="{ 'opacity-60': !resource.is_active }"
            >
              <td class="px-4 py-2">
                <span class="block h-5 w-5 rounded" :style="{ backgroundColor: resource.color }"></span>
              </td>
              <td class="px-4 py-2 font-medium text-gray-800">
                <div class="flex items-center gap-2">
                  <!-- The slot stays when there is no icon, so the names line up. -->
                  <span class="flex h-4 w-4 shrink-0 items-center justify-center text-gray-500">
                    <ResourceIcon :name="resource.icon" :size="16" />
                  </span>
                  <span>{{ resource.name }}</span>
                  <span
                    v-if="resource.is_location"
                    class="rounded bg-surface-muted px-1.5 py-0.5 text-xs font-normal text-gray-600"
                    >{{ $t('app.locationBadge') }}</span
                  >
                </div>
              </td>
              <td class="px-4 py-2 text-gray-500">{{ resource.description || '—' }}</td>
              <td class="px-4 py-2" :class="resource.requires_approval ? 'text-gray-800' : 'text-gray-500'">
                {{ approvalLabel(resource) }}
              </td>
              <td class="px-4 py-2">{{ resource.is_active ? $t('app.active') : $t('app.inactive') }}</td>
              <td class="px-4 py-2">
                <div v-if="canManage" class="row-actions flex justify-end gap-1">
                  <IconButton :label="$t('app.edit')" tone="primary" @click="startEdit(resource)">
                    <Pencil :size="18" :stroke-width="2.25" />
                  </IconButton>
                  <IconButton :label="$t('app.delete')" tone="danger" :disabled="busy" @click="remove(resource.id)">
                    <Trash2 :size="18" :stroke-width="2.25" />
                  </IconButton>
                </div>
              </td>
            </tr>
            <tr v-if="!resources.length">
              <td colspan="6" class="px-6 py-8 text-center text-gray-500">{{ $t('app.noResources') }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-else>
      <div class="border-b border-line px-6 py-4">
        <h3 class="font-semibold text-gray-700">{{ form.id ? $t('app.editResource') : $t('app.addResource') }}</h3>
      </div>
      <div class="space-y-4 p-6">
        <label class="block">
          <span class="mb-1 block text-sm font-medium text-gray-700">{{ $t('app.nameLabel') }}</span>
          <input v-model="form.name" class="w-full rounded-lg border border-line px-3 py-2" />
        </label>
        <label class="block">
          <span class="mb-1 block text-sm font-medium text-gray-700">{{ $t('event.description') }}</span>
          <textarea
            v-model="form.description"
            rows="3"
            class="w-full rounded-lg border border-line px-3 py-2"
          ></textarea>
        </label>
        <label class="block">
          <span class="mb-1 block text-sm font-medium text-gray-700">{{ $t('app.color') }}</span>
          <input v-model="form.color" type="color" class="h-10 w-16 rounded border border-line" />
        </label>
        <div>
          <span class="mb-1 block text-sm font-medium text-gray-700">{{ $t('app.icon') }}</span>
          <ResourceIconPicker v-model="form.icon" />
        </div>
        <div class="grid gap-3 sm:grid-cols-2">
          <SettingsToggle v-model="form.requires_approval" :title="$t('app.requiresApproval')" />
          <SettingsToggle v-model="form.is_active" :title="$t('app.active')" />
        </div>
        <SettingsToggle
          v-model="form.is_location"
          :title="$t('app.isLocation')"
          :description="$t('app.isLocationHint')"
        />
        <fieldset v-if="form.requires_approval" class="space-y-3 rounded-lg border border-line p-4">
          <legend class="px-1 text-sm font-medium text-gray-700">{{ $t('app.approvedBy') }}</legend>
          <label class="flex items-center gap-2 text-sm">
            <input v-model="form.approval_mode" type="radio" value="default" />
            <span class="font-medium text-gray-800">{{ $t('app.useDefaultApprovers') }}</span>
            <span class="text-gray-500">({{ defaultApproverNames || $t('app.nobody') }})</span>
          </label>
          <label class="flex items-center gap-2 text-sm">
            <input v-model="form.approval_mode" type="radio" value="custom" />
            <span class="font-medium text-gray-800">{{ $t('app.useCustomApprovers') }}</span>
          </label>
          <div v-if="form.approval_mode === 'custom'" class="space-y-2 pl-6">
            <ul v-if="form.approvers.length" class="flex flex-wrap gap-2">
              <PersonChip
                v-for="approver in form.approvers"
                :key="approver.user_id"
                :name="approver.display_name"
                :email="approver.email"
                removable
                @remove="removeFormApprover(approver.user_id)"
              />
            </ul>
            <p v-else class="text-sm text-gray-500">{{ $t('app.customApproversRequired') }}</p>
            <div class="sm:w-2/3">
              <SearchableSelect
                :key="`resource-${suggestionsKey}`"
                v-model="pickedResourceApproverId"
                entity="members"
                :calendar-id="calendarId"
                open-on-focus
                :placeholder="$t('app.addApprover')"
                @select="onResourceApproverPicked"
              />
            </div>
          </div>
        </fieldset>
        <div class="flex justify-end gap-3">
          <button type="button" class="rounded-lg border border-line px-4 py-2 hover:bg-hover" @click="form = null">
            {{ $t('app.cancel') }}
          </button>
          <button
            type="button"
            :disabled="formInvalid || busy"
            class="rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
            @click="save"
          >
            {{ $t('app.save') }}
          </button>
        </div>
      </div>
    </div>
  </SettingsPanel>
</template>
