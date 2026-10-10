<script setup lang="ts">
import { computed, ref } from 'vue'
import { Plus } from 'lucide-vue-next'
import SearchableSelect from '@/components/SearchableSelect.vue'
import * as api from '@/api'
import { useAction } from '@/composables/useAction'
import { useLoader } from '@/composables/useLoader'
import { participantStatusLabel, participantStatuses } from '@/services/labels'

/** A participant of an event that hasn't been saved yet; sent along when the event is created. */
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

const { busy, run } = useAction()
const participants = ref<api.EventParticipant[]>([])
const inputValue = ref<string | null>(null)
const selectedUser = ref<api.SearchResult | null>(null)

const items = computed<ParticipantItem[]>(() => [
  ...participants.value.map((participant) => ({
    key: participant.id,
    email: participant.email,
    display_name: participant.display_name,
    status: participant.status,
    remove: () => removeParticipant(participant.id),
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

// New events have no saved participants to load.
const { loading } = useLoader(load, { immediate: !!props.eventId })

async function load() {
  if (props.eventId) participants.value = await api.listEventParticipants(props.eventId)
}

function onSelect(_value: string | null, option: api.SearchResult | null) {
  selectedUser.value = option
}

function resetInput() {
  inputValue.value = null
  selectedUser.value = null
}

async function addParticipant() {
  const value = inputValue.value?.trim()
  if (!value) return
  // A picked user's value is their id; free text is an email address.
  const user = selectedUser.value
  const email = user?.subtitle || value
  if (items.value.some((item) => item.email.toLowerCase() === email.toLowerCase())) {
    resetInput()
    return
  }

  if (!props.eventId) {
    pending.value = [
      ...pending.value,
      {
        tempId: crypto.randomUUID(),
        user_id: user ? value : undefined,
        email,
        display_name: user?.label || email,
        status: 'needs_action',
      },
    ]
    resetInput()
    return
  }

  const eventId = props.eventId
  const data: api.EventParticipantCreate = user ? { user_id: value } : { email: value }
  const added = await run(async () => {
    await api.addEventParticipant(eventId, { ...data, status: 'needs_action' })
    await load()
  })
  if (added) resetInput()
}

async function removeParticipant(participantId: string) {
  const eventId = props.eventId
  if (!eventId) return
  await run(async () => {
    await api.removeEventParticipant(eventId, participantId)
    await load()
  })
}
</script>

<template>
  <div class="space-y-4 pb-4">
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
            <button
              v-if="canManage"
              type="button"
              :disabled="busy"
              class="text-xs text-red-600 hover:underline disabled:opacity-50"
              @click="item.remove()"
            >
              {{ $t('app.delete') }}
            </button>
          </li>
        </ul>
      </div>
    </div>

    <form v-if="canManage" class="flex items-end gap-2 border-t border-line pt-4" @submit.prevent="addParticipant">
      <label class="min-w-0 flex-1 text-xs font-medium text-gray-700">
        {{ $t('event.participantEmail') }}
        <SearchableSelect
          v-model="inputValue"
          entity="users"
          :min-search-length="2"
          allow-free-text
          :free-text-validator="isEmail"
          class="mt-1"
          @select="onSelect"
        />
      </label>
      <button
        type="submit"
        :disabled="busy || !inputValue?.trim()"
        :aria-label="$t('event.addParticipant')"
        class="rounded-lg bg-blue-600 px-3 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
      >
        <Plus :size="18" />
      </button>
    </form>
  </div>
</template>
