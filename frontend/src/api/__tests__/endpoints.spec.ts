import { describe, expect, it } from 'vitest'
import { fakeBackend, reply } from '@/__tests__/fakeBackend'
import * as api from '..'

type Case = [name: string, call: () => Promise<unknown>, method: string, path: string, body?: unknown]

// The requests each function makes: the contract with the backend.
const cases: Case[] = [
  ['getCsrf', () => api.getCsrf(), 'GET', '/api/auth/csrf'],
  [
    'changePassword',
    () => api.changePassword('old', 'new'),
    'POST',
    '/api/auth/v1/account/password/change',
    {
      current_password: 'old',
      new_password: 'new',
    },
  ],
  [
    'requestPasswordReset',
    () => api.requestPasswordReset('a@b.c'),
    'POST',
    '/api/auth/v1/auth/password/request',
    {
      email: 'a@b.c',
    },
  ],
  ['logout', () => api.logout(), 'DELETE', '/api/auth/v1/auth/session'],
  ['me', () => api.me(), 'GET', '/api/users/me'],
  ['listAppPasswords', () => api.listAppPasswords(), 'GET', '/api/users/me/app-passwords'],
  [
    'createAppPassword',
    () => api.createAppPassword('Phone'),
    'POST',
    '/api/users/me/app-passwords',
    { label: 'Phone' },
  ],
  ['deleteAppPassword', () => api.deleteAppPassword('p1'), 'DELETE', '/api/users/me/app-passwords/p1'],
  ['updateProfile', () => api.updateProfile({ language: 'de' }), 'PATCH', '/api/users/me', { language: 'de' }],
  ['getInvitation', () => api.getInvitation('a/b'), 'GET', '/api/rsvp/a/b'],
  ['answerInvitation', () => api.answerInvitation('t', 'accepted'), 'POST', '/api/rsvp/t', { status: 'accepted' }],
  ['getOverviewSettings', () => api.getOverviewSettings(), 'GET', '/api/users/me/settings'],
  [
    'updateOverviewSettings',
    () => api.updateOverviewSettings({ week_start: 1 } as never),
    'PATCH',
    '/api/users/me/settings',
    { week_start: 1 },
  ],
  ['getCalendar', () => api.getCalendar('c'), 'GET', '/api/calendars/c'],
  [
    'createCalendar',
    () => api.createCalendar({ name: 'Team', description: 'Desc' }),
    'POST',
    '/api/calendars',
    { name: 'Team', description: 'Desc' },
  ],
  ['updateCalendar', () => api.updateCalendar('c', { name: 'X' }), 'PATCH', '/api/calendars/c', { name: 'X' }],
  ['deleteCalendar', () => api.deleteCalendar('c'), 'DELETE', '/api/calendars/c'],
  ['listPublicCalendars', () => api.listPublicCalendars(), 'GET', '/api/calendars/public'],
  ['addPublicCalendar', () => api.addPublicCalendar('c'), 'PUT', '/api/calendars/c/subscription'],
  ['removePublicCalendar', () => api.removePublicCalendar('c'), 'DELETE', '/api/calendars/c/subscription'],
  ['listMembers', () => api.listMembers('c'), 'GET', '/api/calendars/c/members'],
  [
    'addMember',
    () => api.addMember('c', 'u', 'read'),
    'POST',
    '/api/calendars/c/members',
    {
      user_id: 'u',
      role: 'read',
    },
  ],
  [
    'updateMember',
    () => api.updateMember('c', 'u', 'manage'),
    'PATCH',
    '/api/calendars/c/members/u',
    { role: 'manage' },
  ],
  ['removeMember', () => api.removeMember('c', 'u'), 'DELETE', '/api/calendars/c/members/u'],
  ['listCalendarGroups', () => api.listCalendarGroups('c'), 'GET', '/api/calendars/c/groups'],
  [
    'addCalendarGroup',
    () => api.addCalendarGroup('c', { group_id: 'g', role: 'read' }),
    'POST',
    '/api/calendars/c/groups',
    { group_id: 'g', role: 'read' },
  ],
  [
    'updateCalendarGroup',
    () => api.updateCalendarGroup('c', 'l', { role: 'manage' }),
    'PATCH',
    '/api/calendars/c/groups/l',
    { role: 'manage' },
  ],
  ['removeCalendarGroup', () => api.removeCalendarGroup('c', 'l'), 'DELETE', '/api/calendars/c/groups/l'],
  ['getLayout', () => api.getLayout(), 'GET', '/api/layout'],
  ['updateLayoutItems', () => api.updateLayoutItems([]), 'PATCH', '/api/layout/items', { items: [] }],
  ['createFolder', () => api.createFolder('F', 'p'), 'POST', '/api/layout/folders', { name: 'F', parent_id: 'p' }],
  ['updateFolder', () => api.updateFolder('f', { name: 'G' }), 'PATCH', '/api/layout/folders/f', { name: 'G' }],
  ['deleteFolder', () => api.deleteFolder('f'), 'DELETE', '/api/layout/folders/f'],
  ['listCategories', () => api.listCategories('c'), 'GET', '/api/calendars/c/categories'],
  [
    'createCategory',
    () => api.createCategory('c', { name: 'A' } as never),
    'POST',
    '/api/calendars/c/categories',
    {
      name: 'A',
    },
  ],
  [
    'updateCategory',
    () => api.updateCategory('c', 'k', { name: 'B' } as never),
    'PATCH',
    '/api/calendars/c/categories/k',
    { name: 'B' },
  ],
  ['deleteCategory', () => api.deleteCategory('c', 'k'), 'DELETE', '/api/calendars/c/categories/k'],
  ['listResources', () => api.listResources('c'), 'GET', '/api/calendars/c/resources'],
  [
    'createResource',
    () => api.createResource('c', { name: 'R' } as never),
    'POST',
    '/api/calendars/c/resources',
    {
      name: 'R',
    },
  ],
  [
    'updateResource',
    () => api.updateResource('c', 'r', { name: 'S' }),
    'PATCH',
    '/api/calendars/c/resources/r',
    {
      name: 'S',
    },
  ],
  ['deleteResource', () => api.deleteResource('c', 'r'), 'DELETE', '/api/calendars/c/resources/r'],
  ['listCalendarApprovers', () => api.listCalendarApprovers('c'), 'GET', '/api/calendars/c/approvers'],
  [
    'setCalendarApprovers',
    () => api.setCalendarApprovers('c', ['u']),
    'PUT',
    '/api/calendars/c/approvers',
    {
      user_ids: ['u'],
    },
  ],
  [
    'setResourceApprovers',
    () => api.setResourceApprovers('c', 'r', []),
    'PUT',
    '/api/calendars/c/resources/r/approvers',
    { user_ids: [] },
  ],
  ['getEvent', () => api.getEvent('e'), 'GET', '/api/events/e'],
  [
    'createEvent',
    () => api.createEvent('c', { title: 'T' } as never),
    'POST',
    '/api/calendars/c/events',
    {
      title: 'T',
    },
  ],
  ['updateEvent', () => api.updateEvent('e', { title: 'U' }), 'PATCH', '/api/events/e', { title: 'U' }],
  ['deleteEvent', () => api.deleteEvent('e'), 'DELETE', '/api/events/e'],
  [
    'updateOccurrence',
    () => api.updateOccurrence('s', '2026-01-01T10:00:00Z', 'this', { title: 'O' }),
    'PATCH',
    '/api/events/s/occurrences/2026-01-01T10:00:00Z',
    { title: 'O' },
  ],
  ['deleteOccurrence', () => api.deleteOccurrence('s', 'r', 'all'), 'DELETE', '/api/events/s/occurrences/r'],
  [
    'getAvailability',
    () => api.getAvailability('a', 'b', ['u'], ['r']),
    'POST',
    '/api/availability',
    {
      start: 'a',
      end: 'b',
      user_ids: ['u'],
      resource_ids: ['r'],
      exclude_event_id: null,
    },
  ],
  ['getReminders', () => api.getReminders('e'), 'GET', '/api/events/e/reminders'],
  ['setReminders', () => api.setReminders('e', [10]), 'PUT', '/api/events/e/reminders', { minutes: [10] }],
  ['listComments', () => api.listComments('e'), 'GET', '/api/events/e/comments'],
  ['addComment', () => api.addComment('e', 'Hi'), 'POST', '/api/events/e/comments', { body: 'Hi' }],
  ['deleteComment', () => api.deleteComment('e', 'k'), 'DELETE', '/api/events/e/comments/k'],
  ['listActivity', () => api.listActivity('e'), 'GET', '/api/events/e/activity'],
  ['listEventParticipants', () => api.listEventParticipants('e'), 'GET', '/api/events/e/participants'],
  [
    'addEventParticipant',
    () => api.addEventParticipant('e', { user_id: 'u' } as never),
    'POST',
    '/api/events/e/participants',
    { user_id: 'u' },
  ],
  [
    'updateMyParticipation',
    () => api.updateMyParticipation('e', { status: 'declined' } as never),
    'PATCH',
    '/api/events/e/participants/me',
    { status: 'declined' },
  ],
  ['removeEventParticipant', () => api.removeEventParticipant('e', 'p'), 'DELETE', '/api/events/e/participants/p'],
  ['getNotificationCounts', () => api.getNotificationCounts(), 'GET', '/api/notifications/counts'],
  ['markNotificationRead', () => api.markNotificationRead('n'), 'POST', '/api/notifications/n/read'],
  ['markAllNotificationsRead', () => api.markAllNotificationsRead(), 'POST', '/api/notifications/read-all'],
  ['deleteNotification', () => api.deleteNotification('n'), 'DELETE', '/api/notifications/n'],
  ['approveEvent', () => api.approveEvent('e', 'ok'), 'POST', '/api/events/e/approve', { note: 'ok' }],
  ['rejectEvent', () => api.rejectEvent('e'), 'POST', '/api/events/e/reject', {}],
  ['getFeedUrl', () => api.getFeedUrl('c'), 'GET', '/api/calendars/c/feed-url'],
  ['rotateFeedToken', () => api.rotateFeedToken('c'), 'POST', '/api/calendars/c/feed-token/rotate'],
  ['getAppSettings', () => api.getAppSettings(), 'GET', '/api/settings'],
  [
    'updateAppSettings',
    () => api.updateAppSettings({ app_name: 'M' } as never),
    'PATCH',
    '/api/admin/settings',
    {
      app_name: 'M',
    },
  ],
  ['listAdminUsers', () => api.listAdminUsers(), 'GET', '/api/admin/users'],
  [
    'createAdminUser',
    () => api.createAdminUser({ email: 'a@b.c' } as never),
    'POST',
    '/api/admin/users',
    {
      email: 'a@b.c',
    },
  ],
  [
    'updateAdminUser',
    () => api.updateAdminUser('u', { is_admin: true } as never),
    'PATCH',
    '/api/admin/users/u',
    {
      is_admin: true,
    },
  ],
  ['deleteAdminUser', () => api.deleteAdminUser('u'), 'DELETE', '/api/admin/users/u'],
  ['resetAdminUserPassword', () => api.resetAdminUserPassword('u'), 'POST', '/api/admin/users/u/reset-password'],
  ['listUserGroups', () => api.listUserGroups(), 'GET', '/api/groups'],
  ['createUserGroup', () => api.createUserGroup({ name: 'G' } as never), 'POST', '/api/groups', { name: 'G' }],
  ['getUserGroup', () => api.getUserGroup('g'), 'GET', '/api/groups/g'],
  [
    'updateUserGroup',
    () => api.updateUserGroup('g', { name: 'H' } as never),
    'PATCH',
    '/api/groups/g',
    {
      name: 'H',
    },
  ],
  ['deleteUserGroup', () => api.deleteUserGroup('g'), 'DELETE', '/api/groups/g'],
]

describe('api endpoints', () => {
  it.each(cases)('%s', async (_name, call, method, path, body) => {
    const backend = fakeBackend({ [`${method} ${path}`]: method === 'DELETE' ? undefined : {} })
    await call()
    expect(backend.unhandled).toEqual([])
    expect(backend.requests).toHaveLength(1)
    expect(backend.requests[0]!.body).toEqual(body)
  })

  it('passes the occurrence scope in the query', async () => {
    const backend = fakeBackend({ 'DELETE /api/events/s/occurrences/r': undefined })
    await api.deleteOccurrence('s', 'r', 'following')
    expect(backend.requests[0]!.query.get('scope')).toBe('following')
  })

  it('signs in and up with allauth, answering the user', async () => {
    const user = { id: 'u1' }
    const backend = fakeBackend({
      'POST /api/auth/v1/auth/login': { status: 200, data: { user } },
      'POST /api/auth/v1/auth/signup': { status: 200, data: { user } },
    })
    await expect(api.login({ email: 'a@b.c', password: 'pw' })).resolves.toEqual(user)
    await expect(api.register({ email: 'a@b.c', display_name: 'A', password: 'pw' })).resolves.toEqual(user)
    expect(backend.requests.map((r) => r.body)).toEqual([
      { email: 'a@b.c', password: 'pw' },
      { email: 'a@b.c', password: 'pw', display_name: 'A' },
    ])
  })

  it('takes the 401 after resetting a password as success, but not other errors', async () => {
    const backend = fakeBackend({ 'POST /api/auth/v1/auth/password/reset': reply(401) })
    await expect(api.resetPassword('key', 'pw')).resolves.toBeUndefined()
    expect(backend.requests[0]!.body).toEqual({ key: 'key', password: 'pw' })
    backend.on('POST /api/auth/v1/auth/password/reset', reply(400, { errors: [] }))
    await expect(api.resetPassword('key', 'pw')).rejects.toMatchObject({ status: 400 })
  })

  it('searches with the optional limit and calendar', async () => {
    const backend = fakeBackend({ 'GET /api/search': [] })
    await api.searchEntities('users', 'kim')
    await api.searchEntities('resources', 'room', { limit: 5, calendarId: 'c' })
    expect(Object.fromEntries(backend.requests[0]!.query)).toEqual({ entity: 'users', q: 'kim' })
    expect(Object.fromEntries(backend.requests[1]!.query)).toEqual({
      entity: 'resources',
      q: 'room',
      limit: '5',
      calendar_id: 'c',
    })
  })

  it('lists the events of several calendars in a range', async () => {
    const backend = fakeBackend({ 'GET /api/events': [] })
    await api.listEvents(['a', 'b'], 'S', 'E')
    const { query } = backend.requests[0]!
    expect(query.getAll('calendar_ids')).toEqual(['a', 'b'])
    expect([query.get('start'), query.get('end')]).toEqual(['S', 'E'])
  })

  it('lists notifications of a group, or all', async () => {
    const backend = fakeBackend({ 'GET /api/notifications': [] })
    await api.listNotifications()
    await api.listNotifications('approvals' as api.NotificationGroup, 10)
    expect(Object.fromEntries(backend.requests[0]!.query)).toEqual({ limit: '50' })
    expect(Object.fromEntries(backend.requests[1]!.query)).toEqual({ limit: '10', group: 'approvals' })
  })
})
