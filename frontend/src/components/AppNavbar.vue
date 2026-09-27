<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Bell, Moon, Sun } from 'lucide-vue-next'
import IconButton from '@/components/IconButton.vue'
import type { AppNotification } from '@/api'
import { formatDateTime } from '@/services/datetime'
import { useAuthStore } from '@/stores/auth'
import { useNotificationsStore } from '@/stores/notifications'
import { useSettingsStore } from '@/stores/settings'
import { useThemeStore } from '@/stores/theme'
import { useI18n } from 'vue-i18n'

const auth = useAuthStore()
const theme = useThemeStore()
const settings = useSettingsStore()
const notifications = useNotificationsStore()
const router = useRouter()
const { t } = useI18n()
const open = ref(false)
const menuRef = ref<HTMLElement | null>(null)
const notifOpen = ref(false)
const notifRef = ref<HTMLElement | null>(null)

function closeOnOutsideClick(event: PointerEvent) {
  if (open.value && !menuRef.value?.contains(event.target as Node)) open.value = false
  if (notifOpen.value && !notifRef.value?.contains(event.target as Node)) notifOpen.value = false
}

onMounted(() => {
  document.addEventListener('pointerdown', closeOnOutsideClick)
  if (auth.token) notifications.startPolling()
})
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', closeOnOutsideClick)
  notifications.stopPolling()
})

watch(
  () => auth.token,
  (token) => (token ? notifications.startPolling() : notifications.stopPolling()),
)

const unreadBadge = computed(() =>
  notifications.unreadCount > 9 ? '9+' : String(notifications.unreadCount),
)

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

async function toggleNotifications() {
  notifOpen.value = !notifOpen.value
  if (notifOpen.value) await notifications.load()
}

async function openNotification(n: AppNotification) {
  await notifications.markRead(n.id)
  notifOpen.value = false
  router.push(n.type === 'approval_requested' ? '/approvals' : '/calendar')
}

async function markAllRead() {
  await notifications.markAllRead()
}

function logout() {
  auth.logout()
  router.push('/login')
}

const initials = computed(() => {
  const name = auth.user?.display_name || auth.user?.email || ''
  return name
    .split(' ')
    .map((p) => p[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
})

function gotoAccount() {
  router.push('/account')
  open.value = false
}

function gotoProfile() {
  gotoAccount()
}

function gotoAdmin() {
  router.push('/admin')
  open.value = false
}
</script>

<template>
  <header class="flex items-center justify-between px-6 py-3 bg-white border-b border-gray-200 shadow-sm">
    <div class="flex items-center gap-3">
      <div
        v-if="settings.logoUrl"
        class="w-8 h-8 rounded-lg bg-white flex items-center justify-center overflow-hidden"
      >
        <img :src="settings.logoUrl" alt="App logo" class="max-w-full max-h-full object-contain" />
      </div>
      <div
        v-else
        class="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold"
      >
        C
      </div>
      <span class="text-lg font-semibold text-gray-800">{{ settings.appName || $t('app.name') }}</span>
    </div>

    <div ref="menuRef" class="relative flex items-center gap-3">
      <div ref="notifRef" class="relative">
        <IconButton @click="toggleNotifications" :label="$t('notifications.title')">
          <Bell :size="20" :stroke-width="2.25" />
        </IconButton>
        <span
          v-if="notifications.unreadCount > 0"
          class="absolute -top-0.5 -right-0.5 min-w-4 h-4 px-1 rounded-full bg-red-600 text-white text-[10px] font-semibold flex items-center justify-center pointer-events-none"
        >
          {{ unreadBadge }}
        </span>
        <div
          v-if="notifOpen"
          class="absolute right-0 top-10 w-80 bg-white border border-gray-200 rounded-lg shadow-lg z-50"
        >
          <div class="flex items-center justify-between px-4 py-2 border-b border-gray-100">
            <span class="text-sm font-semibold text-gray-800">{{ $t('notifications.title') }}</span>
            <button
              v-if="notifications.unreadCount > 0"
              @click="markAllRead"
              class="text-xs text-blue-600 hover:underline"
            >
              {{ $t('notifications.markAllRead') }}
            </button>
          </div>
          <div v-if="!notifications.items.length" class="px-4 py-6 text-center text-sm text-gray-500">
            {{ $t('notifications.empty') }}
          </div>
          <ul v-else class="max-h-96 overflow-y-auto divide-y divide-gray-100">
            <li v-for="n in notifications.items" :key="n.id">
              <button
                @click="openNotification(n)"
                class="block w-full text-left px-4 py-3 text-sm hover:bg-gray-50"
                :class="{ 'bg-blue-50/60': !n.read_at }"
              >
                <span class="block text-gray-800">{{ notificationText(n) }}</span>
                <span class="block text-xs text-gray-400 mt-0.5">{{ formatDateTime(n.created_at) }}</span>
              </button>
            </li>
          </ul>
        </div>
      </div>
      <IconButton @click="theme.toggle" :label="$t('app.toggleTheme')">
        <Sun v-if="theme.resolved === 'dark'" :size="20" :stroke-width="2.25" />
        <Moon v-else :size="20" :stroke-width="2.25" />
      </IconButton>
      <div class="text-right hidden sm:block leading-tight">
        <div class="text-sm font-medium text-gray-900">{{ auth.user?.display_name }}</div>
        <div class="text-xs text-gray-500">{{ auth.user?.email }}</div>
      </div>
      <div
        class="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 text-white flex items-center justify-center font-semibold text-sm"
      >
        {{ initials }}
      </div>
      <button
        @click="open = !open"
        class="p-2 rounded-full hover:bg-gray-100 focus:outline-none"
        aria-label="Menu"
      >
        <svg class="w-5 h-5 text-gray-600" fill="currentColor" viewBox="0 0 20 20">
          <path d="M10 6a2 2 0 110-4 2 2 0 010 4zM10 12a2 2 0 110-4 2 2 0 010 4zM10 18a2 2 0 110-4 2 2 0 010 4z" />
        </svg>
      </button>

      <div
        v-if="open"
        class="absolute right-0 top-12 w-56 bg-white border border-gray-200 rounded-lg shadow-lg py-1 z-50"
      >
        <button @click="gotoProfile" class="block w-full text-left px-4 py-2 text-sm hover:bg-gray-50">
          {{ $t('app.profile') }}
        </button>
        <button @click="gotoAccount" class="block w-full text-left px-4 py-2 text-sm hover:bg-gray-50">
          {{ $t('app.account') }}
        </button>
        <button
          v-if="auth.isAdmin"
          @click="gotoAdmin"
          class="block w-full text-left px-4 py-2 text-sm hover:bg-gray-50"
        >
          {{ $t('app.administration') }}
        </button>
        <div class="border-t border-gray-100 my-1"></div>
        <button @click="logout" class="block w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-gray-50">
          {{ $t('app.logout') }}
        </button>
      </div>
    </div>
  </header>
</template>
