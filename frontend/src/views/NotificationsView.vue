<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Bell, Calendar, Check, Mail, X } from 'lucide-vue-next'
import EventModal from '@/components/event/EventModal.vue'
import IconButton from '@/components/IconButton.vue'
import TabBar from '@/components/TabBar.vue'
import * as api from '@/api'
import type { AppNotification, NotificationGroup } from '@/api'
import { useAction } from '@/composables/useAction'
import { useLoader } from '@/composables/useLoader'
import { formatDateTime } from '@/services/datetime'
import { bookingErrorMessage } from '@/services/errors'
import { notificationText, participantStatusLabel } from '@/services/labels'
import { useNotificationsStore } from '@/stores/notifications'

type Tab = NotificationGroup | 'all'

const notifications = useNotificationsStore()
const { t } = useI18n()
const { busy, run } = useAction()

const openEventId = ref<string | null>(null)

const activeTab = computed<Tab>(() => notifications.group ?? 'all')
const tabs = computed(() => [
  { id: 'all' as const, label: t('notifications.tabAll') },
  { id: 'approvals' as const, label: t('notifications.tabApprovals'), count: notifications.openCounts.approvals },
  { id: 'invitations' as const, label: t('notifications.tabInvitations'), count: notifications.openCounts.invitations },
])

const emptyText = computed(() => {
  if (notifications.group === 'approvals') return t('notifications.emptyApprovals')
  if (notifications.group === 'invitations') return t('notifications.emptyInvitations')
  return t('notifications.empty')
})

const { loading: initialLoading } = useLoader(notifications.load)

async function selectTab(id: Tab) {
  if (id !== activeTab.value) await run(() => notifications.setGroup(id === 'all' ? null : id))
}

// Outcome of an approval request once it is no longer pending.
function requestState(notification: AppNotification): string | null {
  if (notification.type !== 'approval_requested' || notification.event_status === 'pending') return null
  switch (notification.event_status) {
    case 'approved':
    case 'confirmed':
      return t('notifications.stateApproved')
    case 'rejected':
      return t('notifications.stateRejected')
    case 'cancelled':
      return t('notifications.stateCancelled')
    default:
      return t('notifications.stateDeleted')
  }
}

function isInvitation(notification: AppNotification) {
  return notification.type === 'participant_added'
}

function closeEvent(changed: boolean) {
  openEventId.value = null
  if (changed) void run(notifications.load)
}

async function decide(notification: AppNotification, action: 'approve' | 'reject') {
  const eventId = notification.event_id
  if (!eventId) return
  await run(
    async () => {
      await (action === 'approve' ? api.approveEvent(eventId) : api.rejectEvent(eventId))
      await notifications.load()
    },
    { describeError: bookingErrorMessage },
  )
}

async function respondToInvitation(notification: AppNotification, status: api.ParticipantStatus) {
  const eventId = notification.event_id
  if (!eventId) return
  await run(async () => {
    await api.updateMyParticipation(eventId, { status })
    await notifications.load()
  })
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
        class="px-3 py-1.5 text-sm rounded-lg border border-line hover:bg-hover disabled:opacity-50"
        @click="run(notifications.markAllRead)"
      >
        {{ $t('notifications.markAllRead') }}
      </button>
    </div>

    <TabBar :tabs="tabs" :active="activeTab" class="mb-4" @select="selectTab" />

    <p v-if="initialLoading" class="text-sm text-gray-500">{{ $t('app.loading') }}</p>
    <p v-else-if="!notifications.items.length" class="text-sm text-gray-500">{{ emptyText }}</p>

    <ul v-else class="space-y-3">
      <li
        v-for="n in notifications.items"
        :key="n.id"
        class="relative group rounded-lg border border-line bg-surface p-4 flex gap-4"
        :class="n.read_at ? 'opacity-70' : ''"
      >
        <div class="shrink-0 mt-0.5">
          <Check v-if="n.type === 'approval_requested'" :size="20" class="text-blue-600" />
          <Mail v-else-if="isInvitation(n)" :size="20" class="text-green-600" />
          <Bell v-else-if="n.type === 'event_reminder'" :size="20" class="text-blue-600" />
          <Calendar v-else :size="20" class="text-gray-500" />
        </div>
        <div class="min-w-0 flex-1">
          <p class="text-sm text-gray-800">{{ notificationText(n) }}</p>
          <p class="text-xs text-gray-500 mt-1">{{ formatDateTime(n.created_at) }}</p>

          <div class="flex flex-wrap gap-2 mt-3">
            <span
              v-if="requestState(n)"
              class="inline-flex items-center rounded-lg bg-surface-muted px-2.5 py-1.5 text-xs font-medium text-gray-700"
            >
              {{ requestState(n) }}
            </span>
            <template v-else-if="n.type === 'approval_requested' && n.event_id">
              <button
                type="button"
                :disabled="busy"
                class="px-2.5 py-1.5 text-xs font-medium rounded-lg bg-green-600 text-white hover:bg-green-700 disabled:opacity-50"
                @click="decide(n, 'approve')"
              >
                {{ $t('notifications.approve') }}
              </button>
              <button
                type="button"
                :disabled="busy"
                class="px-2.5 py-1.5 text-xs font-medium rounded-lg bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
                @click="decide(n, 'reject')"
              >
                {{ $t('notifications.decline') }}
              </button>
            </template>

            <span
              v-if="isInvitation(n) && n.response_status && n.response_status !== 'needs_action'"
              class="inline-flex items-center rounded-lg bg-surface-muted px-2.5 py-1.5 text-xs font-medium text-gray-700"
            >
              {{ $t('notifications.yourAnswer', { answer: participantStatusLabel(n.response_status) }) }}
            </span>
            <template v-if="isInvitation(n) && n.event_id && n.event_status">
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
              class="px-2.5 py-1.5 text-xs font-medium rounded-lg border border-line hover:bg-hover disabled:opacity-50"
              @click="openEventId = n.event_id"
            >
              {{ $t('notifications.showEvent') }}
            </button>

            <button
              v-if="!n.read_at"
              type="button"
              :disabled="busy"
              class="ml-auto px-2 py-1 text-xs text-gray-500 hover:text-gray-700 disabled:opacity-50"
              @click="run(() => notifications.markRead(n.id))"
            >
              <Check :size="14" class="inline" />
              {{ $t('notifications.markRead') }}
            </button>
          </div>
        </div>
        <div v-if="n.deletable" class="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <IconButton :label="$t('app.delete')" @click.stop="run(() => notifications.remove(n.id))">
            <X :size="16" />
          </IconButton>
        </div>
      </li>
    </ul>

    <EventModal
      v-if="openEventId"
      :event-id="openEventId"
      @saved="closeEvent(true)"
      @cancel="closeEvent(false)"
      @deleted="closeEvent(true)"
    />
  </div>
</template>
