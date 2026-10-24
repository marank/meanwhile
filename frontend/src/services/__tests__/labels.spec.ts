import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { AppNotification } from '@/api'
import { i18n } from '@/i18n'
import { notificationText, participantStatusLabel, participantStatuses } from '../labels'

function notification(overrides: Partial<AppNotification> = {}): AppNotification {
  return {
    id: 'n1',
    type: 'participant_added',
    actor_id: 'u2',
    actor_name: 'Alice',
    calendar_id: null,
    event_id: 'e1',
    title: 'Standup',
    data: null,
    read_at: null,
    created_at: '2026-01-01T09:00:00Z',
    event_status: null,
    response_status: null,
    deletable: true,
    ...overrides,
  }
}

beforeEach(() => {
  i18n.global.locale.value = 'en'
  setActivePinia(createPinia())
})

describe('participantStatusLabel', () => {
  it('names every answer a participant can give', () => {
    expect(participantStatuses.map(participantStatusLabel)).toEqual([
      'Needs action',
      'Accepted',
      'Declined',
      'Tentative',
    ])
  })
})

describe('notificationText', () => {
  it('says who did what to which event', () => {
    expect(notificationText(notification())).toBe('Alice invited you to "Standup"')
    expect(notificationText(notification({ type: 'booking_approved' }))).toBe('Alice approved "Standup"')
  })

  it('names someone when the actor is unknown', () => {
    expect(notificationText(notification({ type: 'comment_added', actor_name: null }))).toBe(
      'Someone commented on "Standup"',
    )
  })

  it('shows the raw title for types the client does not know yet', () => {
    const unknown = notification({ type: 'something_new' as AppNotification['type'], title: 'Raw text' })
    expect(notificationText(unknown)).toBe('Raw text')
  })

  it('words a reminder with the event start', () => {
    const reminder = notification({ type: 'event_reminder', data: { start: '2026-03-04T10:00:00', all_day: true } })
    expect(notificationText(reminder)).toMatch(/^Reminder: “Standup” starts .*2026/)
  })

  it('words a reminder without a start like any other notification', () => {
    const reminder = notification({ type: 'event_reminder', data: {} })
    expect(notificationText(reminder)).toBe('Reminder: “Standup” starts ')
  })

  it('names participants without an account by name or address', () => {
    const byName = notification({
      type: 'participant_replied',
      actor_name: null,
      data: { status: 'accepted', name: 'Bob' },
    })
    expect(notificationText(byName)).toBe('Bob accepted your invitation to "Standup"')
    const byEmail = notification({
      type: 'participant_replied',
      actor_name: null,
      data: { status: 'declined', email: 'bob@example.com' },
    })
    expect(notificationText(byEmail)).toBe('bob@example.com declined your invitation to "Standup"')
  })

  it('words each answer to an invitation', () => {
    const reply = (status?: AppNotification['response_status']) =>
      notificationText(notification({ type: 'participant_replied', data: status ? { status } : {} }))
    expect(reply('tentative')).toBe('Alice tentatively accepted your invitation to "Standup"')
    expect(reply('needs_action')).toBe('Alice answered your invitation to "Standup"')
    expect(reply()).toBe('Alice answered your invitation to "Standup"')
  })
})
