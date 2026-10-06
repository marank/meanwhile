<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Check, X, Calendar, Mail } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useNotificationsStore } from '@/stores/notifications'
import IconButton from '@/components/IconButton.vue'
import { formatDateTime } from '@/services/datetime'
import * as api from '@/api'
import type { AppNotification } from '@/api'
import EventModal from '@/components/EventModal.vue'

const auth = useAuthStore()
const notifications = useNotificationsStore()
const { t } = useI18n()

const busy = ref(false)
const initialLoading = ref(true)
const showModal = ref(false)
const modalCalendarId = ref('')
const modalEventId = ref<string | null>(null)

onMounted(async () => {
  await notifications.load()
  initialLoading.value = false
})

function notificationText(n: AppNotification): string {
  const params = { actor: n.actor_name || t('app.someone'), title: n.title }
  switch (n.type) {
    case 'approval_requested':
      return t('notifications.approvalRequested', params)
    case 'booking_approved':
      return t('notifications.bookingApproved', params)
    case 'booking_rejected':
      return t('notifications.bookingRejected', params)
    case 'booking_cancelled':
      return t('notifications.bookingCancelled', params)
    case 'participant_added':
      return t('notifications.participantAdded', params)
    case 'member_added':
      return t('notifications.memberAdded', params)
    case 'member_role_changed':
      return t('notifications.memberRoleChanged', params)
    case 'comment_added':
      return t('notifications.commentAdded', params)
    default:
      return n.title
  }
}

function showEvent(n: AppNotification) {
  if (!n.event_id || !n.calendar_id) return
  modalCalendarId.value = n.calendar_id
  modalEventId.value = n.event_id
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  modalEventId.value = null
}

function saved() {
  closeModal()
  void notifications.load()
}

async function markRead(id: string) {
  busy.value = true
  try {
    await notifications.markRead(id)
  } finally {
    busy.value = false
  }
}

async function markAllRead() {
  busy.value = true
  try {
    await notifications.markAllRead()
  } finally {
    busy.value = false
  }
}

async function approveBooking(n: AppNotification) {
  if (!auth.token || !n.event_id) return
  busy.value = true
  try {
    await api.approveEvent(auth.token, n.event_id)
    await notifications.load()
  } finally {
    busy.value = false
  }
}

async function declineBooking(n: AppNotification) {
  if (!auth.token || !n.event_id) return
  busy.value = true
  try {
    await api.rejectEvent(auth.token, n.event_id)
    await notifications.load()
  } finally {
    busy.value = false
  }
}

async function respondToInvitation(n: AppNotification, status: api.EventParticipant['status']) {
  if (!auth.token || !n.event_id) return
  busy.value = true
  try {
    const participants = await api.listEventParticipants(auth.token, n.event_id)
    const me = participants.find((p) => p.user_id === auth.user?.id)
    if (me) {
      await api.updateEventParticipant(auth.token, n.event_id, me.id, { status })
      await notifications.load()
    }
  } finally {
    busy.value = false
  }
}

function notificationIcon(n: AppNotification) {
  if (n.type === 'approval_requested') return 'approval'
  if (n.type === 'participant_added') return 'invite'
  return 'default'
}

function canDeleteNotification(n: AppNotification) {
  return n.type !== 'approval_requested' && n.type !== 'participant_added'
}

async function removeNotification(id: string) {
  await notifications.remove(id)
}
</script>

<template>
  <div class="max-w-3xl mx-auto p-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-semibold text-gray-800">{{ $t('notifications.title') }}</h1>
      <button
        v-if="notifications.items.length"
        type="button"
        :disabled="busy"
        class="px-3 py-1.5 text-sm rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-50"
        @click="markAllRead"
      >
        {{ $t('notifications.markAllRead') }}
      </button>
    </div>

    <p v-if="initialLoading" class="text-sm text-gray-500">{{ $t('app.loading') }}</p>
    <p v-else-if="!notifications.items.length" class="text-sm text-gray-500">{{ $t('notifications.empty') }}</p>

    <ul v-else class="space-y-3">
      <li
        v-for="n in notifications.items"
        :key="n.id"
        class="relative group rounded-lg border border-gray-200 bg-white p-4 flex gap-4"
        :class="n.read_at ? 'opacity-70' : ''"
      >
        <div class="shrink-0 mt-0.5">
          <Check v-if="notificationIcon(n) === 'approval'" :size="20" class="text-blue-600" />
          <Mail v-else-if="notificationIcon(n) === 'invite'" :size="20" class="text-green-600" />
          <Calendar v-else :size="20" class="text-gray-500" />
        </div>
        <div class="min-w-0 flex-1">
          <p class="text-sm text-gray-800">{{ notificationText(n) }}</p>
          <p class="text-xs text-gray-500 mt-1">{{ formatDateTime(n.created_at) }}</p>

          <div class="flex flex-wrap gap-2 mt-3">
            <template v-if="n.type === 'approval_requested' && n.event_id">
              <button
                type="button"
                :disabled="busy"
                class="px-2.5 py-1.5 text-xs font-medium rounded-lg bg-green-600 text-white hover:bg-green-700 disabled:opacity-50"
                @click="approveBooking(n)"
              >
                {{ $t('notifications.approve') }}
              </button>
              <button
                type="button"
                :disabled="busy"
                class="px-2.5 py-1.5 text-xs font-medium rounded-lg bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
                @click="declineBooking(n)"
              >
                {{ $t('notifications.decline') }}
              </button>
            </template>

            <template v-if="n.type === 'participant_added' && n.event_id">
              <button
                type="button"
                :disabled="busy"
                class="px-2.5 py-1.5 text-xs font-medium rounded-lg bg-green-600 text-white hover:bg-green-700 disabled:opacity-50"
                @click="respondToInvitation(n, 'accepted')"
              >
                {{ $t('notifications.accept') }}
              </button>
              <button
                type="button"
                :disabled="busy"
                class="px-2.5 py-1.5 text-xs font-medium rounded-lg bg-yellow-500 text-white hover:bg-yellow-600 disabled:opacity-50"
                @click="respondToInvitation(n, 'tentative')"
              >
                {{ $t('notifications.tentative') }}
              </button>
              <button
                type="button"
                :disabled="busy"
                class="px-2.5 py-1.5 text-xs font-medium rounded-lg bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
                @click="respondToInvitation(n, 'declined')"
              >
                {{ $t('notifications.decline') }}
              </button>
            </template>

            <button
              v-if="n.event_id"
              type="button"
              :disabled="busy"
              class="px-2.5 py-1.5 text-xs font-medium rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-50"
              @click="showEvent(n)"
            >
              {{ $t('notifications.showEvent') }}
            </button>

            <button
              v-if="!n.read_at"
              type="button"
              :disabled="busy"
              class="ml-auto px-2 py-1 text-xs text-gray-500 hover:text-gray-700 disabled:opacity-50"
              @click="markRead(n.id)"
            >
              <Check :size="14" class="inline" />
              {{ $t('notifications.markRead') }}
            </button>
          </div>
        </div>
        <div
          v-if="canDeleteNotification(n)"
          class="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity"
        >
          <IconButton
            :label="$t('app.delete')"
            @click.stop="removeNotification(n.id)"
          >
            <X :size="16" />
          </IconButton>
        </div>
      </li>
    </ul>

    <EventModal
      v-if="showModal"
      :calendar-id="modalCalendarId"
      :event-id="modalEventId"
      @saved="saved"
      @cancel="closeModal"
      @deleted="saved"
    />
  </div>
</template>
