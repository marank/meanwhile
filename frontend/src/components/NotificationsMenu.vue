<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, type Component } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  AlarmClock,
  ArrowRight,
  Bell,
  CalendarX,
  CheckCheck,
  ChevronRight,
  CircleCheck,
  CircleX,
  Mail,
  MessageSquare,
  Reply,
  ShieldCheck,
  UserCog,
  UserPlus,
} from '@lucide/vue'
import IconButton from '@/components/IconButton.vue'
import type { AppNotification, NotificationGroup, NotificationType } from '@/api'
import { useAction } from '@/composables/useAction'
import { useLoader } from '@/composables/useLoader'
import { daysAgo, formatDateTime, formatTimeAgo } from '@/services/datetime'
import { notificationText } from '@/services/labels'
import { useNotificationsStore } from '@/stores/notifications'

const emit = defineEmits<{ navigate: [path: string] }>()

const notifications = useNotificationsStore()
const { t } = useI18n()
const { run } = useAction()

// The menu has its own list, loaded whenever it opens and kept current while it is open.
const { loading } = useLoader(notifications.loadRecent)
onMounted(() => notifications.setRecentShown(true))
onBeforeUnmount(() => notifications.setRecentShown(false))

type Tone = 'blue' | 'green' | 'red' | 'amber' | 'violet' | 'gray'

// A Record over the union makes the compiler point out notification types without an icon.
const kinds: Record<NotificationType, { icon: Component; tone: Tone }> = {
  approval_requested: { icon: ShieldCheck, tone: 'amber' },
  booking_approved: { icon: CircleCheck, tone: 'green' },
  booking_rejected: { icon: CircleX, tone: 'red' },
  booking_cancelled: { icon: CalendarX, tone: 'gray' },
  participant_added: { icon: Mail, tone: 'blue' },
  member_added: { icon: UserPlus, tone: 'violet' },
  member_role_changed: { icon: UserCog, tone: 'violet' },
  comment_added: { icon: MessageSquare, tone: 'blue' },
  event_reminder: { icon: AlarmClock, tone: 'amber' },
  participant_replied: { icon: Reply, tone: 'gray' },
}

const replyTones: Record<string, Tone> = { accepted: 'green', tentative: 'amber', declined: 'red' }

// Tinted the same in both themes: a translucent background under the color's own text.
const toneClasses: Record<Tone, string> = {
  blue: 'bg-blue-500/12 text-blue-600 dark:text-blue-400',
  green: 'bg-green-500/12 text-green-600 dark:text-green-400',
  red: 'bg-red-500/12 text-red-600 dark:text-red-400',
  amber: 'bg-amber-500/15 text-amber-600 dark:text-amber-400',
  violet: 'bg-violet-500/12 text-violet-600 dark:text-violet-400',
  gray: 'bg-gray-500/12 text-gray-600',
}

function kind(notification: AppNotification) {
  // Types added on the server before the client knows them get a plain bell.
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition -- the server may know more types
  const { icon, tone } = kinds[notification.type] ?? { icon: Bell, tone: 'gray' }
  const status = notification.type === 'participant_replied' ? String(notification.data?.status ?? '') : ''
  return { icon, toneClass: toneClasses[replyTones[status] ?? tone] }
}

const now = new Date()

/** The list by day: today, yesterday, earlier; days without any are left out. */
const sections = computed(() => {
  const byAge = [
    { id: 'today', label: t('notifications.sectionToday'), items: [] as AppNotification[] },
    { id: 'yesterday', label: t('notifications.sectionYesterday'), items: [] as AppNotification[] },
    { id: 'earlier', label: t('notifications.sectionEarlier'), items: [] as AppNotification[] },
  ]
  for (const notification of notifications.recent) {
    byAge[Math.min(2, Math.max(0, daysAgo(notification.created_at, now)))]!.items.push(notification)
  }
  return byAge.filter((section) => section.items.length)
})

/** Requests and invitations still waiting for the user, each leading to its tab of the page. */
const waiting = computed(() =>
  (['approvals', 'invitations'] as const)
    .map((group) => ({ group, count: notifications.openCounts[group] }))
    .filter(({ count }) => count > 0)
    .map(({ group, count }) => ({
      group,
      icon: group === 'approvals' ? ShieldCheck : Mail,
      label: t(group === 'approvals' ? 'notifications.openApprovals' : 'notifications.openInvitations', count),
    })),
)

function openGroup(group: NotificationGroup) {
  notifications.group = group
  emit('navigate', '/notifications')
}

// Each leads where the server says (its event, its invitation, a calendar or the notifications page).
async function open(notification: AppNotification) {
  // Where it leads is worth showing even if marking it read failed (reported as a toast).
  if (!notification.read_at) await run(() => notifications.markRead(notification.id))
  emit('navigate', notification.link)
}

function showAll() {
  notifications.group = null
  emit('navigate', '/notifications')
}
</script>

<template>
  <div
    class="flex flex-col overflow-hidden rounded-xl border border-line bg-surface shadow-xl"
    :aria-label="$t('notifications.title')"
    role="dialog"
  >
    <header class="flex items-center gap-2 px-4 pb-2 pt-3">
      <h2 class="text-base font-semibold text-gray-900">{{ $t('notifications.title') }}</h2>
      <span
        v-if="notifications.unreadCount > 0"
        class="rounded-full bg-blue-600/10 px-2 py-0.5 text-xs font-medium text-blue-600 dark:text-blue-400"
      >
        {{ $t('notifications.unreadCount', { count: notifications.unreadCount }) }}
      </span>
      <IconButton
        v-if="notifications.unreadCount > 0"
        class="ml-auto rounded-md"
        tone="primary"
        :label="$t('notifications.markAllRead')"
        @click="run(notifications.markAllRead)"
      >
        <CheckCheck :size="18" :stroke-width="2.25" />
      </IconButton>
    </header>

    <div v-if="waiting.length" class="space-y-1 px-2 pb-2">
      <button
        v-for="item in waiting"
        :key="item.group"
        type="button"
        class="flex w-full items-center gap-2.5 rounded-lg bg-amber-500/10 px-3 py-2 text-left text-sm font-medium text-amber-800 transition-colors hover:bg-amber-500/20 dark:text-amber-300"
        :data-waiting="item.group"
        @click="openGroup(item.group)"
      >
        <component :is="item.icon" :size="16" :stroke-width="2.25" class="shrink-0" />
        <span class="min-w-0 flex-1">{{ item.label }}</span>
        <ChevronRight :size="16" class="shrink-0 opacity-60" />
      </button>
    </div>

    <div class="max-h-[min(26rem,65vh)] overflow-y-auto overscroll-contain border-t border-line">
      <ul v-if="loading && !notifications.recent.length" class="space-y-1 p-2" aria-hidden="true" data-loading>
        <li v-for="i in 3" :key="i" class="flex animate-pulse gap-3 px-2 py-2">
          <div class="h-9 w-9 shrink-0 rounded-full bg-surface-muted"></div>
          <div class="flex-1 space-y-2 py-1">
            <div class="h-3 w-4/5 rounded bg-surface-muted"></div>
            <div class="h-3 w-1/4 rounded bg-surface-muted"></div>
          </div>
        </li>
      </ul>

      <div v-else-if="!notifications.recent.length" class="flex flex-col items-center px-6 py-10 text-center">
        <div class="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-surface-muted text-gray-400">
          <Bell :size="22" :stroke-width="2" />
        </div>
        <p class="text-sm font-medium text-gray-800">{{ $t('notifications.emptyTitle') }}</p>
        <p class="mt-1 text-sm text-gray-500">{{ $t('notifications.empty') }}</p>
      </div>

      <section v-for="section in sections" v-else :key="section.id" :aria-label="section.label">
        <h3
          class="sticky top-0 z-10 bg-surface px-4 pb-1 pt-3 text-[11px] font-semibold uppercase tracking-wider text-gray-500"
        >
          {{ section.label }}
        </h3>
        <ul class="px-2 pb-1">
          <li v-for="notification in section.items" :key="notification.id">
            <button
              type="button"
              class="flex w-full items-start gap-3 rounded-lg px-2 py-2.5 text-left transition-colors hover:bg-hover"
              :data-unread="!notification.read_at || undefined"
              @click="open(notification)"
            >
              <span
                class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full"
                :class="kind(notification).toneClass"
              >
                <component :is="kind(notification).icon" :size="17" :stroke-width="2.25" />
              </span>
              <span class="min-w-0 flex-1">
                <span
                  class="line-clamp-2 text-sm"
                  :class="notification.read_at ? 'text-gray-600' : 'font-medium text-gray-900'"
                >
                  {{ notificationText(notification) }}
                </span>
                <time
                  class="mt-0.5 block text-xs"
                  :class="notification.read_at ? 'text-gray-400' : 'text-blue-600 dark:text-blue-400'"
                  :datetime="notification.created_at"
                  :title="formatDateTime(notification.created_at)"
                >
                  {{ formatTimeAgo(notification.created_at, now) }}
                </time>
              </span>
              <span
                v-if="!notification.read_at"
                class="mt-3 h-2 w-2 shrink-0 rounded-full bg-blue-600 dark:bg-blue-400"
              ></span>
            </button>
          </li>
        </ul>
      </section>
    </div>

    <button
      type="button"
      class="flex items-center justify-center gap-1.5 border-t border-line px-4 py-2.5 text-sm font-medium text-blue-600 transition-colors hover:bg-hover dark:text-blue-400"
      @click="showAll"
    >
      {{ $t('notifications.viewAll') }}
      <ArrowRight :size="15" :stroke-width="2.25" />
    </button>
  </div>
</template>
