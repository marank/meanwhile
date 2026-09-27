import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '@/api'
import type { AppNotification } from '@/api'
import { useAuthStore } from './auth'

export const useNotificationsStore = defineStore('notifications', () => {
  const auth = useAuthStore()

  const items = ref<AppNotification[]>([])
  const unreadCount = ref(0)
  let timer: number | undefined

  async function load() {
    if (!auth.token) return
    items.value = await api.listNotifications(auth.token)
    await refreshCount()
  }

  async function refreshCount() {
    if (!auth.token) return
    try {
      unreadCount.value = (await api.getUnreadCount(auth.token)).count
    } catch {
      // ignore transient errors
    }
  }

  async function markRead(id: string) {
    if (!auth.token) return
    const updated = await api.markNotificationRead(auth.token, id)
    const item = items.value.find((n) => n.id === id)
    if (item) item.read_at = updated.read_at
    await refreshCount()
  }

  async function markAllRead() {
    if (!auth.token) return
    await api.markAllNotificationsRead(auth.token)
    items.value = items.value.map((n) => ({ ...n, read_at: n.read_at ?? new Date().toISOString() }))
    unreadCount.value = 0
  }

  function startPolling() {
    stopPolling()
    void refreshCount()
    timer = window.setInterval(refreshCount, 60_000)
  }

  function stopPolling() {
    if (timer !== undefined) {
      window.clearInterval(timer)
      timer = undefined
    }
  }

  return {
    items,
    unreadCount,
    load,
    refreshCount,
    markRead,
    markAllRead,
    startPolling,
    stopPolling,
  }
})
