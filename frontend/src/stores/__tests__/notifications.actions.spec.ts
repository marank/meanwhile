import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { fakeBackend, reply, type FakeBackend } from '@/__tests__/fakeBackend'
import { useNotificationsStore } from '../notifications'

const notification = (id: string, read_at: string | null = null) => ({ id, read_at })

describe('notifications store actions', () => {
  let backend: FakeBackend
  let unread: number

  beforeEach(async () => {
    setActivePinia(createPinia())
    unread = 2
    backend = fakeBackend({
      'GET /api/notifications': [notification('n1'), notification('n2'), notification('n3', '2026-01-01')],
      'GET /api/notifications/counts': () => ({ unread, approvals: 1, invitations: 4 }),
      'POST /api/notifications/*/read': (r) => notification(r.path.split('/')[3]!, '2026-02-02'),
      'POST /api/notifications/read-all': { ok: true },
      'DELETE /api/notifications/*': undefined,
    })
    const store = useNotificationsStore()
    await Promise.all([store.load(), store.loadRecent()])
  })

  afterEach(() => useNotificationsStore().$dispose())

  it('loads the list and the open requests', () => {
    const store = useNotificationsStore()
    expect(store.items).toHaveLength(3)
    expect(store.recent).toHaveLength(3)
    expect(store.unreadCount).toBe(2)
    expect(store.openCounts).toEqual({ approvals: 1, invitations: 4 })
  })

  it('marks one read in both lists and updates the count', async () => {
    const store = useNotificationsStore()
    unread = 1
    await store.markRead('n1')
    expect(store.items[0]!.read_at).toBe('2026-02-02')
    expect(store.recent[0]!.read_at).toBe('2026-02-02')
    expect(store.unreadCount).toBe(1)
  })

  it('marks all read, keeping when the read ones were read', async () => {
    const store = useNotificationsStore()
    await store.markAllRead()
    expect(store.items.every((n) => n.read_at)).toBe(true)
    expect(store.recent[2]!.read_at).toBe('2026-01-01')
    expect(store.unreadCount).toBe(0)
  })

  it('removes one from both lists', async () => {
    const store = useNotificationsStore()
    unread = 1
    await store.remove('n2')
    expect(store.items.map((n) => n.id)).toEqual(['n1', 'n3'])
    expect(store.recent.map((n) => n.id)).toEqual(['n1', 'n3'])
    expect(store.unreadCount).toBe(1)
  })

  it('keeps the count it has when asking for it fails', async () => {
    const store = useNotificationsStore()
    backend.on('GET /api/notifications/counts', reply(503))
    await store.refreshCount()
    expect(store.unreadCount).toBe(2)
  })
})
