import { api } from './client'

export * from './client'
export * from './types'

import type {
  AdminUser,
  AdminUserCreate,
  AdminUserUpdate,
  AppNotification,
  AppPassword,
  AppSettings,
  AppSettingsUpdate,
  Approver,
  Calendar,
  CalendarGroupLink,
  CalendarGroupLinkCreate,
  CalendarGroupLinkUpdate,
  CalendarMember,
  CalendarUpdate,
  Category,
  CategoryInput,
  Event,
  EventActivity,
  EventComment,
  EventInput,
  EventParticipant,
  EventParticipantCreate,
  EventParticipantUpdate,
  Folder,
  GrantableRole,
  Invitation,
  NotificationGroup,
  Availability,
  Occurrence,
  OccurrenceScope,
  OverviewSettings,
  ParticipantStatus,
  ProfileUpdate,
  Resource,
  PublicCalendar,
  ResourceInput,
  SearchEntity,
  SearchResult,
  Layout,
  LayoutItem,
  User,
  UserGroup,
  UserGroupCreate,
  UserGroupDetail,
  UserGroupUpdate,
} from './types'

// Auth (django-allauth headless browser client, mounted at /api/auth/v1)
interface AllauthResponse<T = unknown> {
  status: number
  data: T
  errors?: { message: string; code?: string; param?: string }[]
}

export async function getCsrf() {
  return api<{ ok: boolean }>('/api/auth/csrf/')
}

export async function login(data: { email: string; password: string }): Promise<User> {
  const resp = await api<AllauthResponse<{ user: User }>>('/api/auth/v1/auth/login', {
    method: 'POST',
    body: data,
  })
  return resp.data.user
}

export async function register(data: { email: string; display_name: string; password: string }): Promise<User> {
  const resp = await api<AllauthResponse<{ user: User }>>('/api/auth/v1/auth/signup', {
    method: 'POST',
    body: { email: data.email, password: data.password, display_name: data.display_name },
  })
  return resp.data.user
}

export async function logout() {
  await api('/api/auth/v1/auth/session', { method: 'DELETE' })
}

export const me = () => api<User>('/api/users/me')

// Search
export const searchEntities = (
  entity: SearchEntity,
  q: string,
  options: { limit?: number; calendarId?: string } = {},
) => {
  const params = new URLSearchParams({ entity, q })
  if (options.limit !== undefined) params.set('limit', String(options.limit))
  if (options.calendarId) params.set('calendar_id', options.calendarId)
  return api<SearchResult[]>(`/api/search?${params}`)
}

// Users / app passwords
export const listAppPasswords = () => api<AppPassword[]>('/api/users/me/app-passwords')

export const createAppPassword = (label: string) =>
  api<AppPassword>('/api/users/me/app-passwords', { method: 'POST', body: { label } })

export const deleteAppPassword = (id: string) => api<void>(`/api/users/me/app-passwords/${id}`, { method: 'DELETE' })

export const updateProfile = (data: ProfileUpdate) => api<User>('/api/users/me', { method: 'PATCH', body: data })

// Answering an invitation from the link in its email; the token is the key, no session needed.
export const getInvitation = (token: string) => api<Invitation>(`/api/rsvp/${encodeURIComponent(token)}`)
export const answerInvitation = (token: string, status: Exclude<ParticipantStatus, 'needs_action'>) =>
  api<Invitation>(`/api/rsvp/${encodeURIComponent(token)}`, { method: 'POST', body: { status } })

export const getOverviewSettings = () => api<OverviewSettings>('/api/users/me/settings')

export const updateOverviewSettings = (data: Partial<OverviewSettings>) =>
  api<OverviewSettings>('/api/users/me/settings', { method: 'PATCH', body: data })

// Calendars

export const getCalendar = (id: string) => api<Calendar>(`/api/calendars/${id}`)

export const createCalendar = (name: string, description?: string, color?: string) =>
  api<Calendar>('/api/calendars', { method: 'POST', body: { name, description, color } })

export const updateCalendar = (id: string, data: CalendarUpdate) =>
  api<Calendar>(`/api/calendars/${id}`, { method: 'PATCH', body: data })

export const deleteCalendar = (id: string) => api<void>(`/api/calendars/${id}`, { method: 'DELETE' })

/** Public calendars one isn't a member of; they show up in the sidebar once added. */
export const listPublicCalendars = () => api<PublicCalendar[]>('/api/calendars/public')

export const addPublicCalendar = (id: string) => api<void>(`/api/calendars/${id}/subscription`, { method: 'PUT' })

export const removePublicCalendar = (id: string) => api<void>(`/api/calendars/${id}/subscription`, { method: 'DELETE' })

// Members
export const listMembers = (calendarId: string) => api<CalendarMember[]>(`/api/calendars/${calendarId}/members`)

export const addMember = (calendarId: string, userId: string, role: GrantableRole) =>
  api<CalendarMember>(`/api/calendars/${calendarId}/members`, {
    method: 'POST',
    body: { user_id: userId, role },
  })

export const updateMember = (calendarId: string, userId: string, role: GrantableRole) =>
  api<CalendarMember>(`/api/calendars/${calendarId}/members/${userId}`, {
    method: 'PATCH',
    body: { role },
  })

export const removeMember = (calendarId: string, userId: string) =>
  api<void>(`/api/calendars/${calendarId}/members/${userId}`, { method: 'DELETE' })

// Calendar group access
export const listCalendarGroups = (calendarId: string) =>
  api<CalendarGroupLink[]>(`/api/calendars/${calendarId}/groups`)

export const addCalendarGroup = (calendarId: string, data: CalendarGroupLinkCreate) =>
  api<CalendarGroupLink>(`/api/calendars/${calendarId}/groups`, { method: 'POST', body: data })

export const updateCalendarGroup = (calendarId: string, linkId: string, data: CalendarGroupLinkUpdate) =>
  api<CalendarGroupLink>(`/api/calendars/${calendarId}/groups/${linkId}`, {
    method: 'PATCH',
    body: data,
  })

export const removeCalendarGroup = (calendarId: string, linkId: string) =>
  api<void>(`/api/calendars/${calendarId}/groups/${linkId}`, { method: 'DELETE' })

// Layout: the user's folders, and where the calendars sit in them (the sidebar)
export const getLayout = () => api<Layout>('/api/layout')

/** Places folders and calendars (parent folder and position) in one request. */
export const updateLayoutItems = (items: LayoutItem[]) =>
  api<void>('/api/layout/items', { method: 'PATCH', body: { items } })

export const createFolder = (name: string, parent_id?: string | null) =>
  api<Folder>('/api/layout/folders', { method: 'POST', body: { name, parent_id } })

export const updateFolder = (id: string, data: Partial<Folder>) =>
  api<Folder>(`/api/layout/folders/${id}`, { method: 'PATCH', body: data })

export const deleteFolder = (id: string) => api<void>(`/api/layout/folders/${id}`, { method: 'DELETE' })

// Categories
export const listCategories = (calendarId: string) => api<Category[]>(`/api/calendars/${calendarId}/categories`)

export const createCategory = (calendarId: string, data: CategoryInput) =>
  api<Category>(`/api/calendars/${calendarId}/categories`, { method: 'POST', body: data })

export const updateCategory = (calendarId: string, id: string, data: CategoryInput) =>
  api<Category>(`/api/calendars/${calendarId}/categories/${id}`, { method: 'PATCH', body: data })

export const deleteCategory = (calendarId: string, id: string) =>
  api<void>(`/api/calendars/${calendarId}/categories/${id}`, { method: 'DELETE' })

// Resources
export const listResources = (calendarId: string) => api<Resource[]>(`/api/calendars/${calendarId}/resources`)

export const createResource = (calendarId: string, data: ResourceInput) =>
  api<Resource>(`/api/calendars/${calendarId}/resources`, { method: 'POST', body: data })

export const updateResource = (calendarId: string, id: string, data: Partial<ResourceInput>) =>
  api<Resource>(`/api/calendars/${calendarId}/resources/${id}`, { method: 'PATCH', body: data })

export const deleteResource = (calendarId: string, id: string) =>
  api<void>(`/api/calendars/${calendarId}/resources/${id}`, { method: 'DELETE' })

// Calendar approvers
export const listCalendarApprovers = (calendarId: string) => api<Approver[]>(`/api/calendars/${calendarId}/approvers`)

/** Sets the default approvers: whoever is not in the list is no approver any more. */
export const setCalendarApprovers = (calendarId: string, userIds: string[]) =>
  api<Approver[]>(`/api/calendars/${calendarId}/approvers`, { method: 'PUT', body: { user_ids: userIds } })

/** Sets a resource's own approvers; with none, the calendar's default approvers decide. */
export const setResourceApprovers = (calendarId: string, resourceId: string, userIds: string[]) =>
  api<Approver[]>(`/api/calendars/${calendarId}/resources/${resourceId}/approvers`, {
    method: 'PUT',
    body: { user_ids: userIds },
  })

export const removeCalendarApprover = (calendarId: string, userId: string) =>
  api<void>(`/api/calendars/${calendarId}/approvers/${userId}`, { method: 'DELETE' })

// Events
export const listEvents = (calendarIds: string[], start: string, end: string) => {
  const params = new URLSearchParams({ start, end })
  for (const id of calendarIds) params.append('calendar_ids', id)
  return api<Occurrence[]>(`/api/events?${params}`)
}

export const getEvent = (eventId: string) => api<Event>(`/api/events/${eventId}`)

export const createEvent = (calendarId: string, data: EventInput) =>
  api<Event>(`/api/calendars/${calendarId}/events`, { method: 'POST', body: data })

export const updateEvent = (eventId: string, data: Partial<EventInput>) =>
  api<Event>(`/api/events/${eventId}`, { method: 'PATCH', body: data })

export const deleteEvent = (eventId: string) => api<void>(`/api/events/${eventId}`, { method: 'DELETE' })

const occurrencePath = (seriesId: string, recurrenceId: string, scope: OccurrenceScope) =>
  `/api/events/${seriesId}/occurrences/${encodeURIComponent(recurrenceId)}?scope=${scope}`

/** Changes one occurrence of a series, it and the later ones, or all; start and end are the occurrence's. */
export const updateOccurrence = (
  seriesId: string,
  recurrenceId: string,
  scope: OccurrenceScope,
  data: Partial<EventInput>,
) => api<Event>(occurrencePath(seriesId, recurrenceId, scope), { method: 'PATCH', body: data })

/**
 * When the users and resources are taken in [start, end); `excludeEventId` doesn't count.
 * A POST, though it changes nothing: the lists of ids go in the body instead of a long URL.
 */
export const getAvailability = (
  start: string,
  end: string,
  userIds: string[],
  resourceIds: string[],
  excludeEventId?: string | null,
) =>
  api<Availability>('/api/availability', {
    method: 'POST',
    body: { start, end, user_ids: userIds, resource_ids: resourceIds, exclude_event_id: excludeEventId ?? null },
  })

/** The current user's own reminders, in minutes before each occurrence. */
export const getReminders = (eventId: string) => api<{ minutes: number[] }>(`/api/events/${eventId}/reminders`)

export const setReminders = (eventId: string, minutes: number[]) =>
  api<{ minutes: number[] }>(`/api/events/${eventId}/reminders`, { method: 'PUT', body: { minutes } })

export const deleteOccurrence = (seriesId: string, recurrenceId: string, scope: OccurrenceScope) =>
  api<void>(occurrencePath(seriesId, recurrenceId, scope), { method: 'DELETE' })

// Comments & activity
export const listComments = (eventId: string) => api<EventComment[]>(`/api/events/${eventId}/comments`)

export const addComment = (eventId: string, body: string) =>
  api<EventComment>(`/api/events/${eventId}/comments`, {
    method: 'POST',
    body: { body },
  })

export const deleteComment = (eventId: string, commentId: string) =>
  api<void>(`/api/events/${eventId}/comments/${commentId}`, { method: 'DELETE' })

export const listActivity = (eventId: string) => api<EventActivity[]>(`/api/events/${eventId}/activity`)

// Event participants
export const listEventParticipants = (eventId: string) => api<EventParticipant[]>(`/api/events/${eventId}/participants`)

export const addEventParticipant = (eventId: string, data: EventParticipantCreate) =>
  api<EventParticipant>(`/api/events/${eventId}/participants`, {
    method: 'POST',
    body: data,
  })

/** Answers an invitation for the current user. */
export const updateMyParticipation = (eventId: string, data: EventParticipantUpdate) =>
  api<EventParticipant>(`/api/events/${eventId}/participants/me`, { method: 'PATCH', body: data })

export const removeEventParticipant = (eventId: string, participantId: string) =>
  api<void>(`/api/events/${eventId}/participants/${participantId}`, {
    method: 'DELETE',
  })

// Notifications
export const listNotifications = (group?: NotificationGroup, limit = 50) => {
  const params = new URLSearchParams({ limit: String(limit) })
  if (group) params.set('group', group)
  return api<AppNotification[]>(`/api/notifications?${params}`)
}

/** The numbers shown as badges: unread notifications, and requests still waiting for the user. */
export const getNotificationCounts = () =>
  api<{ unread: number; approvals: number; invitations: number }>('/api/notifications/counts')

export const markNotificationRead = (id: string) =>
  api<AppNotification>(`/api/notifications/${id}/read`, { method: 'POST' })

export const markAllNotificationsRead = () => api<{ ok: boolean }>('/api/notifications/read-all', { method: 'POST' })

export const deleteNotification = (id: string) => api<void>(`/api/notifications/${id}`, { method: 'DELETE' })

// Approvals
export const approveEvent = (eventId: string, note?: string) =>
  api<Event>(`/api/events/${eventId}/approve`, { method: 'POST', body: { note } })

export const rejectEvent = (eventId: string, note?: string) =>
  api<Event>(`/api/events/${eventId}/reject`, { method: 'POST', body: { note } })

// Feed
export const getFeedUrl = (calendarId: string) => api<{ feed_url: string }>(`/api/calendars/${calendarId}/feed-url`)

export const rotateFeedToken = (calendarId: string) =>
  api<{ feed_url: string }>(`/api/calendars/${calendarId}/feed-token/rotate`, { method: 'POST' })

// App settings (public: app name, logo, favicon, calendar defaults)
export const getAppSettings = () => api<AppSettings>('/api/settings')

// Admin
export const updateAppSettings = (data: AppSettingsUpdate) =>
  api<AppSettings>('/api/admin/settings', { method: 'PATCH', body: data })

export const listAdminUsers = () => api<AdminUser[]>('/api/admin/users')

export const createAdminUser = (data: AdminUserCreate) =>
  api<AdminUser>('/api/admin/users', { method: 'POST', body: data })

export const updateAdminUser = (userId: string, data: AdminUserUpdate) =>
  api<AdminUser>(`/api/admin/users/${userId}`, { method: 'PATCH', body: data })

export const deleteAdminUser = (userId: string) => api<void>(`/api/admin/users/${userId}`, { method: 'DELETE' })

export const resetAdminUserPassword = (userId: string) =>
  api<{ password: string }>(`/api/admin/users/${userId}/reset-password`, { method: 'POST' })

// Admin user groups
export const listUserGroups = () => api<UserGroup[]>('/api/groups')

export const createUserGroup = (data: UserGroupCreate) => api<UserGroup>('/api/groups', { method: 'POST', body: data })

export const getUserGroup = (groupId: string) => api<UserGroupDetail>(`/api/groups/${groupId}`)

export const updateUserGroup = (groupId: string, data: UserGroupUpdate) =>
  api<UserGroup>(`/api/groups/${groupId}`, { method: 'PATCH', body: data })

export const deleteUserGroup = (groupId: string) => api<void>(`/api/groups/${groupId}`, { method: 'DELETE' })
