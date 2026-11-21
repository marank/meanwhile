<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import SearchableSelect from '@/components/SearchableSelect.vue'
import * as api from '@/api'
import { participantStatusLabel, participantStatuses } from '@/services/labels'
import { nonEmpty } from '@/services/text'

/** A participant added in the dialog but not saved yet; sent along when the event is saved. */
export interface PendingParticipant {
  tempId: string
  user_id?: string
  email: string
  display_name: string
  status: api.ParticipantStatus
}

interface ParticipantItem {
  key: string
  email: string
  display_name: string | null
  status: api.ParticipantStatus
  remove: () => void
}

const props = defineProps<{
  eventId?: string | null
  canManage: boolean
}>()

const pending = defineModel<PendingParticipant[]>('pending', { required: true })
/** Saved participants removed in the dialog; they are removed when the event is saved. */
const removed = defineModel<string[]>('removed', { required: true })
/** The saved participants of an existing event, loaded by the dialog; null while loading. */
const participants = defineModel<api.EventParticipant[] | null>('participants', { default: null })

const inputValue = ref<string | null>(null)

const items = computed<ParticipantItem[]>(() => [
  ...(participants.value ?? [])
    .filter((participant) => !removed.value.includes(participant.id))
    .map((participant) => ({
      key: participant.id,
      email: participant.email,
      display_name: participant.display_name,
      status: participant.status,
      remove: () => {
        removed.value = [...removed.value, participant.id]
      },
    })),
  ...pending.value.map((participant) => ({
    key: participant.tempId,
    email: participant.email,
    display_name: participant.display_name,
    status: participant.status,
    remove: () => {
      pending.value = pending.value.filter((p) => p.tempId !== participant.tempId)
    },
  })),
])

const groups = computed(() =>
  participantStatuses
    .map((status) => ({ status, items: items.value.filter((item) => item.status === status) }))
    .filter((group) => group.items.length),
)

const isEmail = (value: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)

// New events have no saved participants to wait for.
const loading = computed(() => !!props.eventId && participants.value === null)

/** Picking a user or entering an email address adds them to the list right away; saving sends them. */
function add(value: string | null, user: api.SearchResult | null) {
  // Emptied after the field took the pick, so it sees the change and clears its text.
  void nextTick(() => (inputValue.value = null))
  const picked = value?.trim()
  if (!picked) return
  // A picked user's value is their id; free text is an email address.
  const email = nonEmpty(user?.subtitle) ?? picked
  if (items.value.some((item) => item.email.toLowerCase() === email.toLowerCase())) return
  // Removed and added again: the saved participant simply stays.
  const saved = participants.value?.find((p) => p.email.toLowerCase() === email.toLowerCase())
  if (saved) {
    removed.value = removed.value.filter((id) => id !== saved.id)
    return
  }
  pending.value = [
    ...pending.value,
    {
      tempId: crypto.randomUUID(),
      user_id: user ? picked : undefined,
      email,
      display_name: nonEmpty(user?.label) ?? email,
      status: 'needs_action',
    },
  ]
}
</script>

<template>
  <div class="space-y-4 pb-4">
    <label v-if="canManage" class="block text-xs font-medium text-gray-700">
      {{ $t('event.addParticipant') }}
      <SearchableSelect
        v-model="inputValue"
        entity="users"
        :min-search-length="2"
        allow-free-text
        :free-text-validator="isEmail"
        class="mt-1"
        @select="add"
      />
    </label>
    <p v-if="loading" class="text-sm text-gray-500">{{ $t('app.loading') }}</p>
    <p v-else-if="!items.length" class="text-sm text-gray-500">{{ $t('event.noParticipants') }}</p>
    <div v-else class="space-y-3">
      <div v-for="group in groups" :key="group.status">
        <p class="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">
          {{ participantStatusLabel(group.status) }}
        </p>
        <ul class="divide-y divide-line rounded-lg border border-line">
          <li v-for="item in group.items" :key="item.key" class="flex items-center justify-between gap-3 p-3">
            <div class="min-w-0">
              <p class="truncate text-sm font-medium text-gray-800">{{ item.display_name || item.email }}</p>
              <p v-if="item.display_name && item.display_name !== item.email" class="truncate text-xs text-gray-500">
                {{ item.email }}
              </p>
            </div>
            <button v-if="canManage" type="button" class="text-xs text-red-600 hover:underline" @click="item.remove()">
              {{ $t('app.delete') }}
            </button>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>
