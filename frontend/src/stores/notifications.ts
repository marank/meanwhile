import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '@/api'
import type { AppNotification, NotificationGroup } from '@/api'
import { useAuthStore } from './auth'

export const useNotificationsStore = defineStore('notifications', () => {
  const auth = useAuthStore()

  const items = ref<AppNotification[]>([])
  const unreadCount = ref(0)
  const group = ref<NotificationGroup | null>(null)
  const openCounts = ref({ approvals: 0, invitations: 0 })
  let timer: number | undefined

  async function load() {
    if (!auth.isLoggedIn) return
    const [list, counts] = await Promise.all([
      api.listNotifications(group.value ?? undefined),
      api.getOpenNotificationCounts(),
    ])
    items.value = list
    openCounts.value = counts
    await refreshCount()
  }

  async function setGroup(value: NotificationGroup | null) {
    group.value = value
    await load()
  }

  async function refreshCount() {
    if (!auth.isLoggedIn) return
    try {
      unreadCount.value = (await api.getUnreadCount()).count
    } catch {
      // ignore transient errors
    }
  }

  async function markRead(id: string) {
    if (!auth.isLoggedIn) return
    const updated = await api.markNotificationRead(id)
    const item = items.value.find((n) => n.id === id)
    if (item) item.read_at = updated.read_at
    await refreshCount()
  }

  async function markAllRead() {
    if (!auth.isLoggedIn) return
    await api.markAllNotificationsRead()
    items.value = items.value.map((n) => ({ ...n, read_at: n.read_at ?? new Date().toISOString() }))
    unreadCount.value = 0
  }

  async function remove(id: string) {
    if (!auth.isLoggedIn) return
    await api.deleteNotification(id)
    items.value = items.value.filter((n) => n.id !== id)
    await refreshCount()
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
    group,
    openCounts,
    load,
    setGroup,
    refreshCount,
    markRead,
    markAllRead,
    remove,
    startPolling,
    stopPolling,
  }
})
