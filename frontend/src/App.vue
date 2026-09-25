<script setup lang="ts">
import { onMounted } from 'vue'
import AppNavbar from './components/AppNavbar.vue'
import CalendarSidebar from './components/CalendarSidebar.vue'
import DialogHost from './components/DialogHost.vue'
import { useAuthStore } from './stores/auth'

const auth = useAuthStore()

onMounted(() => {
  auth.fetchMe()
})
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
  </div>
</template>
