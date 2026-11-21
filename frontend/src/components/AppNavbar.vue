<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Bell, EllipsisVertical, Menu, Moon, Sun } from '@lucide/vue'
import AppLogo from '@/components/AppLogo.vue'
import IconButton from '@/components/IconButton.vue'
import NotificationsMenu from '@/components/NotificationsMenu.vue'
import { useEscapeToClose } from '@/composables/useEscapeToClose'
import { sidebarDrawerOpen } from '@/services/sidebarState'
import { nonEmpty } from '@/services/text'
import { useAuthStore } from '@/stores/auth'
import { useNotificationsStore } from '@/stores/notifications'
import { useSettingsStore } from '@/stores/settings'
import { useThemeStore } from '@/stores/theme'

const auth = useAuthStore()
const theme = useThemeStore()
const settings = useSettingsStore()
const notifications = useNotificationsStore()
const router = useRouter()

const menuOpen = ref(false)
const menuRef = ref<HTMLElement | null>(null)
const notificationsOpen = ref(false)
const notificationsRef = ref<HTMLElement | null>(null)
const header = ref<HTMLElement | null>(null)

// Dialogs shown as a page on phones start below the navbar (AppModal's fullscreenOnPhone).
const headerResize = new ResizeObserver(([entry]) => {
  document.documentElement.style.setProperty('--navbar-height', `${entry!.borderBoxSize[0]!.blockSize}px`)
})

function closeOnOutsideClick(event: PointerEvent) {
  const target = event.target as Node
  if (menuOpen.value && !menuRef.value?.contains(target)) menuOpen.value = false
  if (notificationsOpen.value && !notificationsRef.value?.contains(target)) notificationsOpen.value = false
}

useEscapeToClose(
  () => menuOpen.value,
  () => (menuOpen.value = false),
)
useEscapeToClose(
  () => notificationsOpen.value,
  () => (notificationsOpen.value = false),
)

onMounted(() => {
  headerResize.observe(header.value!)
  document.addEventListener('pointerdown', closeOnOutsideClick)
  notifications.startPolling()
})

onBeforeUnmount(() => {
  headerResize.disconnect()
  document.documentElement.style.removeProperty('--navbar-height')
  document.removeEventListener('pointerdown', closeOnOutsideClick)
  notifications.stopPolling()
})

const unreadBadge = computed(() => (notifications.unreadCount > 9 ? '9+' : String(notifications.unreadCount)))

const initials = computed(() =>
  (nonEmpty(auth.user?.display_name) ?? auth.user?.email ?? '')
    .split(' ')
    .map((part) => part[0])
    .join('')
    .toUpperCase()
    .slice(0, 2),
)

function navigate(path: string) {
  menuOpen.value = false
  notificationsOpen.value = false
  void router.push(path)
}

async function logout() {
  await auth.logout()
  navigate('/login')
}
</script>

<template>
  <header
    ref="header"
    class="app-navbar flex items-center justify-between gap-2 border-b border-line bg-surface px-3 py-2 shadow-sm pt-[calc(0.5rem+var(--safe-top))] sm:px-6 sm:py-3 sm:pt-[calc(0.75rem+var(--safe-top))]"
  >
    <div class="flex min-w-0 items-center gap-2 sm:gap-3">
      <IconButton
        class="lg:hidden"
        :label="$t('app.toggleSidebar')"
        :aria-expanded="sidebarDrawerOpen"
        aria-controls="calendar-sidebar"
        @click="sidebarDrawerOpen = !sidebarDrawerOpen"
      >
        <Menu :size="22" :stroke-width="2.25" />
      </IconButton>
      <AppLogo />
      <span class="truncate text-lg font-semibold text-gray-800">{{ settings.appName }}</span>
    </div>

    <div class="flex shrink-0 items-center gap-1.5 sm:gap-3">
      <div ref="notificationsRef" class="relative">
        <IconButton
          :label="$t('notifications.title')"
          :aria-expanded="notificationsOpen"
          aria-haspopup="dialog"
          @click="notificationsOpen = !notificationsOpen"
        >
          <Bell :size="20" :stroke-width="2.25" />
        </IconButton>
        <span
          v-if="notifications.unreadCount > 0"
          class="pointer-events-none absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-semibold text-white"
        >
          {{ unreadBadge }}
        </span>
        <Transition
          enter-from-class="opacity-0 scale-95 -translate-y-1"
          enter-active-class="transition duration-150 ease-out motion-reduce:transition-none"
          leave-active-class="transition duration-100 ease-in motion-reduce:transition-none"
          leave-to-class="opacity-0 scale-95"
        >
          <NotificationsMenu
            v-if="notificationsOpen"
            class="fixed inset-x-2 top-[calc(var(--navbar-height,3.25rem)+0.25rem)] z-50 origin-top sm:absolute sm:inset-x-auto sm:right-0 sm:top-10 sm:w-96 sm:origin-top-right"
            @navigate="navigate"
          />
        </Transition>
      </div>

      <IconButton :label="$t('app.toggleTheme')" @click="theme.toggle">
        <Sun v-if="theme.isDark" :size="20" :stroke-width="2.25" />
        <Moon v-else :size="20" :stroke-width="2.25" />
      </IconButton>

      <div class="hidden text-right leading-tight sm:block">
        <div class="text-sm font-medium text-gray-900">{{ auth.user?.display_name }}</div>
        <div class="text-xs text-gray-500">{{ auth.user?.email }}</div>
      </div>
      <div
        class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs sm:h-10 sm:w-10 sm:text-sm bg-gradient-to-br from-blue-500 to-indigo-600 font-semibold text-white"
      >
        {{ initials }}
      </div>

      <div ref="menuRef" class="relative">
        <IconButton
          :label="$t('app.menu')"
          :aria-expanded="menuOpen"
          aria-haspopup="menu"
          @click="menuOpen = !menuOpen"
        >
          <EllipsisVertical :size="20" :stroke-width="2.25" />
        </IconButton>
        <div
          v-if="menuOpen"
          role="menu"
          class="absolute right-0 top-10 z-50 w-56 rounded-lg border border-line bg-surface py-1 shadow-lg"
        >
          <button
            type="button"
            role="menuitem"
            class="block w-full px-4 py-2 text-left text-sm hover:bg-hover"
            @click="navigate('/account')"
          >
            {{ $t('app.account') }}
          </button>
          <button
            v-if="auth.isAdmin"
            type="button"
            role="menuitem"
            class="block w-full px-4 py-2 text-left text-sm hover:bg-hover"
            @click="navigate('/admin')"
          >
            {{ $t('app.administration') }}
          </button>
          <div class="my-1 border-t border-line"></div>
          <button
            type="button"
            role="menuitem"
            class="block w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-hover"
            @click="logout"
          >
            {{ $t('app.logout') }}
          </button>
        </div>
      </div>
    </div>
  </header>
</template>
