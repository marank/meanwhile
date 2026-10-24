import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import * as api from '@/api'
import { realtime } from '@/services/realtime'
import { toast } from '@/services/toast'
import { useNotificationsStore } from '../notifications'
import { deferred } from './deferred'

vi.mock('@/api', async (original) => ({
  ...(await original<typeof import('@/api')>()),
  listNotifications: vi.fn(),
  getNotificationCounts: vi.fn(),
}))

/** Delivers a message to the listeners of the shared realtime client, as the socket would. */
function receive(type: string, extra: Record<string, unknown> = {}) {
  const emit = (realtime as unknown as { emit(message: Record<string, unknown>): void }).emit.bind(realtime)
  emit({ type, ...extra })
}

const notification = (id: string) => ({ id }) as api.AppNotification

describe('notifications store', () => {
  // The stores listen on the shared realtime client; one test's store must not hear the next one's messages.
  afterEach(() => useNotificationsStore().$dispose())

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.getNotificationCounts).mockResolvedValue({ unread: 0, approvals: 0, invitations: 0 })
  })

  it('shows the tab selected last, even if an earlier tab answers later', async () => {
    const store = useNotificationsStore()
    const approvals = deferred<api.AppNotification[]>()
    const invitations = deferred<api.AppNotification[]>()
    vi.mocked(api.listNotifications).mockReturnValueOnce(approvals.promise).mockReturnValueOnce(invitations.promise)

    const first = store.setGroup('approvals')
    const second = store.setGroup('invitations')
    invitations.resolve([notification('invitation')])
    await second
    approvals.resolve([notification('approval')])
    await first

    expect(store.group).toBe('invitations')
    expect(store.items.map((n) => n.id)).toEqual(['invitation'])
  })

  it('forgets everything on reset', async () => {
    const store = useNotificationsStore()
    vi.mocked(api.listNotifications).mockResolvedValue([notification('n')])
    await store.load()
    store.reset()
    expect(store.items).toEqual([])
    expect(store.group).toBeNull()
  })

  it('pops up reminders the server pushes', () => {
    const info = vi.spyOn(toast, 'info').mockImplementation(() => {})
    useNotificationsStore()
    receive('reminders.due', {
      reminders: [
        { event_id: 'e', title: 'Standup', start: '2030-01-07T09:00:00Z', all_day: false, minutes_before: 15 },
      ],
    })
    expect(info).toHaveBeenCalledOnce()
    expect(info.mock.calls[0]![0]).toContain('Standup')
  })

  it('loads the count when notifications change elsewhere', async () => {
    const store = useNotificationsStore()
    vi.mocked(api.getNotificationCounts).mockResolvedValue({ unread: 3, approvals: 0, invitations: 0 })
    receive('notifications.changed')
    await vi.waitFor(() => expect(store.unreadCount).toBe(3))
  })

  it("reloads the page's list on live updates only while the page is shown", async () => {
    const store = useNotificationsStore()
    vi.mocked(api.listNotifications).mockResolvedValue([notification('n')])
    store.setListShown(true)
    await store.load()
    receive('notifications.changed')
    await vi.waitFor(() => expect(api.listNotifications).toHaveBeenCalledTimes(2))

    store.setListShown(false)
    vi.mocked(api.listNotifications).mockClear()
    receive('notifications.changed')
    receive('reconnected')
    await vi.waitFor(() => expect(api.getNotificationCounts).toHaveBeenCalledTimes(4))
    expect(api.listNotifications).not.toHaveBeenCalled()
  })

  it("loads the dropdown's list unfiltered, apart from the page's tab", async () => {
    const store = useNotificationsStore()
    vi.mocked(api.listNotifications)
      .mockResolvedValueOnce([notification('approval')])
      .mockResolvedValueOnce([notification('approval'), notification('other')])
    await store.setGroup('approvals')
    await store.loadRecent()
    expect(api.listNotifications).toHaveBeenLastCalledWith()
    expect(store.items.map((n) => n.id)).toEqual(['approval'])
    expect(store.recent.map((n) => n.id)).toEqual(['approval', 'other'])
  })

  describe('fallback polling', () => {
    beforeEach(() => {
      vi.useFakeTimers()
    })
    afterEach(() => {
      vi.useRealTimers()
      realtime.status.value = 'idle'
    })

    it('asks for the count while there is no live connection, and not while there is', async () => {
      const store = useNotificationsStore()
      realtime.status.value = 'closed'
      store.startPolling()
      expect(api.getNotificationCounts).toHaveBeenCalledTimes(1)
      await vi.advanceTimersByTimeAsync(60_000)
      expect(api.getNotificationCounts).toHaveBeenCalledTimes(2)

      realtime.status.value = 'open'
      await vi.advanceTimersByTimeAsync(180_000)
      expect(api.getNotificationCounts).toHaveBeenCalledTimes(2)
      store.stopPolling()
    })
  })
})
