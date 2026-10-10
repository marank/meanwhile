<script setup lang="ts">
import { onMounted, watch, computed } from 'vue'
import AppNavbar from './components/AppNavbar.vue'
import CalendarSidebar from './components/CalendarSidebar.vue'
import DialogHost from './components/DialogHost.vue'
import ToastHost from './components/ToastHost.vue'
import { useAuthStore } from './stores/auth'
import { useSettingsStore } from './stores/settings'

const auth = useAuthStore()
const settings = useSettingsStore()

onMounted(async () => {
  await Promise.all([auth.fetchMe(), settings.load()])
})

watch(
  () => settings.faviconUrl,
  (url) => {
    if (!url) return
    let link = document.querySelector('link[rel="icon"]') as HTMLLinkElement | null
    if (!link) {
      link = document.createElement('link')
      link.rel = 'icon'
      document.head.appendChild(link)
    }
    link.href = url
  },
  { immediate: true },
)

const pageTitle = computed(() => (settings.appName ? `${settings.appName}` : 'Calendar'))
watch(
  pageTitle,
  (title) => {
    document.title = title
  },
  { immediate: true },
)
</script>

<template>
  <div class="flex flex-col h-full">
    <AppNavbar v-if="auth.isLoggedIn" />
    <div class="flex flex-1 overflow-hidden">
      <CalendarSidebar v-if="auth.isLoggedIn" />
      <main class="flex-1 overflow-auto bg-gray-50 p-4">
        <router-view />
      </main>
    </div>
    <DialogHost />
    <ToastHost />
  </div>
</template>
