<script setup lang="ts">
import { onMounted, watchEffect } from 'vue'
import AppNavbar from './components/AppNavbar.vue'
import CalendarSidebar from './components/CalendarSidebar.vue'
import DialogHost from './components/DialogHost.vue'
import ToastHost from './components/ToastHost.vue'
import { useAuthStore } from './stores/auth'
import { useSettingsStore } from './stores/settings'

const auth = useAuthStore()
const settings = useSettingsStore()

onMounted(settings.load)

watchEffect(() => {
  document.title = settings.appName
})

watchEffect(() => {
  const url = settings.faviconUrl
  if (!url) return
  // The page comes with ours in two formats; browsers would keep using the SVG one.
  const [link, ...others] = document.querySelectorAll<HTMLLinkElement>('link[rel="icon"]')
  others.forEach((other) => other.remove())
  const icon = link ?? document.head.appendChild(Object.assign(document.createElement('link'), { rel: 'icon' }))
  icon.removeAttribute('type')
  icon.removeAttribute('sizes')
  icon.href = url
})
</script>

<template>
  <!-- Added to the home screen, iOS runs the app edge to edge (viewport-fit=cover): keep clear of the
       status bar, the notch, the rounded corners and the home indicator. -->
  <div
    class="flex h-full flex-col pl-[env(safe-area-inset-left)] pr-[env(safe-area-inset-right)]"
    :class="{ 'pt-[var(--safe-top)]': !auth.isLoggedIn }"
  >
    <AppNavbar v-if="auth.isLoggedIn" />
    <div class="relative flex flex-1 overflow-hidden">
      <CalendarSidebar v-if="auth.isLoggedIn" />
      <main
        class="min-w-0 flex-1 overflow-auto bg-surface-muted p-1 pb-[max(0.25rem,env(safe-area-inset-bottom))] sm:p-4 sm:pb-[max(1rem,env(safe-area-inset-bottom))]"
      >
        <router-view />
      </main>
    </div>
    <DialogHost />
    <ToastHost />
  </div>
</template>
