import { defineStore } from 'pinia'
import { onScopeDispose, ref } from 'vue'
import * as api from '@/api'
import type { DueReminder } from '@/api'
import { realtime, type RealtimeMessage } from '@/services/realtime'
import { dueReminderText } from '@/services/reminders'
import { toast } from '@/services/toast'

// Only while there is no live connection (e.g. a proxy that doesn't pass WebSockets): then the count
// is fetched now and then.
const FALLBACK_POLL_INTERVAL_MS = 60_000

export const useNotificationsStore = defineStore('notifications', () => {
  /** The notifications page's list, of the selected tab. */
  const items = ref<api.AppNotification[]>([])
  /** The navbar dropdown's list: the latest ones, whatever the page's tab. */
  const recent = ref<api.AppNotification[]>([])
  const unreadCount = ref(0)
  const group = ref<api.NotificationGroup | null>(null)
  const openCounts = ref({ approvals: 0, invitations: 0 })
  let loadVersion = 0
  let recentVersion = 0
  let timer: number | undefined
  // Whether the page's list and the dropdown are shown; live updates then reload them, too.
  let listShown = false
  let recentShown = false

  /** Loads the current tab; when loads overlap (fast tab switches), only the latest one is applied. */
  async function load() {
    const version = ++loadVersion
    const [list, counts] = await Promise.all([
      api.listNotifications(group.value ?? undefined),
      api.getNotificationCounts(),
    ])
    if (version !== loadVersion) return
    items.value = list
    applyCounts(counts)
  }

  /** Loads the dropdown's list: all tabs, regardless of the one selected on the page. */
  async function loadRecent() {
    const version = ++recentVersion
    const [list, counts] = await Promise.all([api.listNotifications(), api.getNotificationCounts()])
    if (version !== recentVersion) return
    recent.value = list
    applyCounts(counts)
  }

  /** The notifications page tells while it is shown, so that live updates reload its list. */
  function setListShown(shown: boolean) {
    listShown = shown
  }

  /** Likewise the navbar dropdown. */
  function setRecentShown(shown: boolean) {
    recentShown = shown
  }

  function applyCounts(counts: { unread: number; approvals: number; invitations: number }) {
    unreadCount.value = counts.unread
    openCounts.value = { approvals: counts.approvals, invitations: counts.invitations }
  }

  async function setGroup(value: api.NotificationGroup | null) {
    group.value = value
    await load()
  }

  async function refreshCount() {
    try {
      applyCounts(await api.getNotificationCounts())
    } catch {
      // ignore transient errors
    }
  }

  async function markRead(id: string) {
    const updated = await api.markNotificationRead(id)
    for (const item of [...items.value, ...recent.value]) if (item.id === id) item.read_at = updated.read_at
    await refreshCount()
  }

  async function markAllRead() {
    await api.markAllNotificationsRead()
    const now = new Date().toISOString()
    items.value = items.value.map((n) => ({ ...n, read_at: n.read_at ?? now }))
    recent.value = recent.value.map((n) => ({ ...n, read_at: n.read_at ?? now }))
    unreadCount.value = 0
  }

  async function remove(id: string) {
    await api.deleteNotification(id)
    items.value = items.value.filter((n) => n.id !== id)
    recent.value = recent.value.filter((n) => n.id !== id)
    await refreshCount()
  }

  // The fallback poll pauses while the tab is hidden and catches up as soon as it's visible again.
  function pollIfOffline() {
    if (realtime.status.value !== 'open') void refreshCount()
  }

  function onVisibilityChange() {
    if (document.hidden) {
      window.clearInterval(timer)
      timer = undefined
    } else if (timer === undefined) {
      pollIfOffline()
      timer = window.setInterval(pollIfOffline, FALLBACK_POLL_INTERVAL_MS)
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

  // Live updates: new notifications and ones read in another tab show at once.
  function onLiveUpdate() {
    if (listShown) void load().catch(() => {})
    if (recentShown) void loadRecent().catch(() => {})
    if (!listShown && !recentShown) void refreshCount()
  }

  // The server pushes reminders that came due; they pop up wherever one is in the app.
  function onRemindersDue(message: RealtimeMessage) {
    for (const reminder of (message.reminders ?? []) as DueReminder[]) toast.info(dueReminderText(reminder))
  }

  const stopListening = [
    realtime.on('notifications.changed', onLiveUpdate),
    realtime.on('reconnected', onLiveUpdate),
    realtime.on('reminders.due', onRemindersDue),
  ]
  onScopeDispose(() => stopListening.forEach((stop) => stop()))

  function reset() {
    stopPolling()
    listShown = recentShown = false
    loadVersion++
    recentVersion++
    items.value = []
    recent.value = []
    unreadCount.value = 0
    group.value = null
    openCounts.value = { approvals: 0, invitations: 0 }
  }

  return {
    items,
    recent,
    unreadCount,
    group,
    openCounts,
    load,
    loadRecent,
    setListShown,
    setRecentShown,
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
