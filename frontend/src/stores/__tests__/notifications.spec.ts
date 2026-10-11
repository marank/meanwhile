import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import * as api from '@/api'
import { toast } from '@/services/toast'
import { useNotificationsStore } from '../notifications'
import { deferred } from './deferred'

vi.mock('@/api', async (original) => ({
  ...(await original<typeof import('@/api')>()),
  listNotifications: vi.fn(),
  getOpenNotificationCounts: vi.fn(),
  getUnreadCount: vi.fn(),
}))

const notification = (id: string) => ({ id }) as api.AppNotification

describe('notifications store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.getOpenNotificationCounts).mockResolvedValue({ approvals: 0, invitations: 0 })
    vi.mocked(api.getUnreadCount).mockResolvedValue({ count: 0, reminders: [] })
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

  it('pops up reminders that came due', async () => {
    const info = vi.spyOn(toast, 'info').mockImplementation(() => {})
    vi.mocked(api.getUnreadCount).mockResolvedValue({
      count: 1,
      reminders: [
        { event_id: 'e', title: 'Standup', start: '2030-01-07T09:00:00Z', all_day: false, minutes_before: 15 },
      ],
    })
    const store = useNotificationsStore()
    await store.refreshCount()
    expect(store.unreadCount).toBe(1)
    expect(info).toHaveBeenCalledOnce()
    expect(info.mock.calls[0]![0]).toContain('Standup')
  })
})
