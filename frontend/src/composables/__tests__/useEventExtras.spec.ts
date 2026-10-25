import { afterEach, describe, expect, it, vi } from 'vitest'
import { fakeBackend, reply } from '@/__tests__/fakeBackend'
import { participant } from '@/components/event/__tests__/helpers'
import { useEventParticipants, useEventReminders } from '../useEventExtras'

afterEach(() => vi.unstubAllGlobals())

describe('useEventReminders', () => {
  it('saves the reminders only when they changed', async () => {
    const backend = fakeBackend({
      'GET /api/events/ev1/reminders': { minutes: [15, 60] },
      'PUT /api/events/ev1/reminders': {},
    })
    const reminders = useEventReminders()
    await reminders.load('ev1')
    expect(reminders.minutes.value).toEqual([15, 60])
    expect(reminders.changed.value).toBe(false)
    await reminders.save('ev1')
    expect(backend.calls('PUT /api/events/ev1/reminders')).toHaveLength(0)
    reminders.minutes.value = [15]
    expect(reminders.changed.value).toBe(true)
    await reminders.save('ev1')
    expect(backend.calls('PUT /api/events/ev1/reminders')[0]!.body).toEqual({ minutes: [15] })
  })

  it('starts without reminders when they cannot be loaded', async () => {
    fakeBackend({ 'GET /api/events/ev1/reminders': reply(500) })
    const reminders = useEventReminders()
    await reminders.load('ev1')
    expect(reminders.minutes.value).toEqual([])
  })
})

describe('useEventParticipants', () => {
  const pending = (email: string, user_id?: string) => ({
    tempId: email,
    user_id,
    email,
    display_name: '',
    status: 'needs_action' as const,
  })

  it('shows the saved participants without those removed, and those added', async () => {
    fakeBackend({ 'GET /api/events/ev1/participants': [participant({ id: 'p1' }), participant({ id: 'p2' })] })
    const participants = useEventParticipants()
    await participants.load('ev1')
    participants.removedIds.value = ['p1']
    participants.pending.value = [pending('new@example.com')]
    expect(participants.current.value.map((p) => ('id' in p ? p.id : p.email))).toEqual(['p2', 'new@example.com'])
  })

  it('starts without participants when they cannot be loaded', async () => {
    fakeBackend({ 'GET /api/events/ev1/participants': reply(500) })
    const participants = useEventParticipants()
    await participants.load('ev1')
    expect(participants.saved.value).toEqual([])
  })

  it('sends the changes one by one, keeping what failed for the next try', async () => {
    const backend = fakeBackend({
      'DELETE /api/events/ev1/participants/*': undefined,
      'POST /api/events/ev1/participants': (request) =>
        (request.body as { email?: string }).email === 'b@example.com' ? reply(500) : {},
    })
    const participants = useEventParticipants()
    participants.removedIds.value = ['p1']
    participants.pending.value = [pending('a@example.com', 'u1'), pending('b@example.com')]
    await expect(participants.save('ev1')).rejects.toThrow()
    expect(participants.removedIds.value).toEqual([])
    expect(participants.pending.value.map((p) => p.email)).toEqual(['b@example.com'])
    expect(backend.calls('POST /api/events/ev1/participants').map((r) => r.body)).toEqual([
      { user_id: 'u1', status: 'needs_action' },
      { email: 'b@example.com', status: 'needs_action' },
    ])
  })
})
