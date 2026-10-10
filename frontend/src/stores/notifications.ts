import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '@/api'

const POLL_INTERVAL_MS = 60_000

export const useNotificationsStore = defineStore('notifications', () => {
  const items = ref<api.AppNotification[]>([])
  const unreadCount = ref(0)
  const group = ref<api.NotificationGroup | null>(null)
  const openCounts = ref({ approvals: 0, invitations: 0 })
  let loadVersion = 0
  let timer: number | undefined

  /** Loads the current tab; when loads overlap (fast tab switches), only the latest one is applied. */
  async function load() {
    const version = ++loadVersion
    const [list, counts, unread] = await Promise.all([
      api.listNotifications(group.value ?? undefined),
      api.getOpenNotificationCounts(),
      api.getUnreadCount(),
    ])
    if (version !== loadVersion) return
    items.value = list
    openCounts.value = counts
    unreadCount.value = unread.count
  }

  async function setGroup(value: api.NotificationGroup | null) {
    group.value = value
    await load()
  }

  async function refreshCount() {
    try {
      unreadCount.value = (await api.getUnreadCount()).count
    } catch {
      // ignore transient errors
    }
  }

  async function markRead(id: string) {
    const updated = await api.markNotificationRead(id)
    const item = items.value.find((n) => n.id === id)
    if (item) item.read_at = updated.read_at
    await refreshCount()
  }

  async function markAllRead() {
    await api.markAllNotificationsRead()
    const now = new Date().toISOString()
    items.value = items.value.map((n) => ({ ...n, read_at: n.read_at ?? now }))
    unreadCount.value = 0
  }

  async function remove(id: string) {
    await api.deleteNotification(id)
    items.value = items.value.filter((n) => n.id !== id)
    await refreshCount()
  }

  // Polling pauses while the tab is hidden and catches up as soon as it's visible again.
  function onVisibilityChange() {
    if (document.hidden) {
      window.clearInterval(timer)
      timer = undefined
    } else if (timer === undefined) {
      void refreshCount()
      timer = window.setInterval(refreshCount, POLL_INTERVAL_MS)
    }
  }

  function startPolling() {
    stopPolling()
    document.addEventListener('visibilitychange', onVisibilityChange)
    onVisibilityChange()
  }

  function stopPolling() {
    document.removeEventListener('visibilitychange', onVisibilityChange)
    window.clearInterval(timer)
    timer = undefined
  }

  function reset() {
    stopPolling()
    loadVersion++
    items.value = []
    unreadCount.value = 0
    group.value = null
    openCounts.value = { approvals: 0, invitations: 0 }
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
    reset,
  }
})
