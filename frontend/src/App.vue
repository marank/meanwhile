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
  <div class="flex h-full flex-col">
    <AppNavbar v-if="auth.isLoggedIn" />
    <div class="relative flex flex-1 overflow-hidden">
      <CalendarSidebar v-if="auth.isLoggedIn" />
      <main class="min-w-0 flex-1 overflow-auto bg-surface-muted p-1 sm:p-4">
        <router-view />
      </main>
    </div>
    <DialogHost />
    <ToastHost />
  </div>
</template>
