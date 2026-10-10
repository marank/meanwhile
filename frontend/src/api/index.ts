import { api } from './client'

export * from './client'

export interface User {
  id: string
  email: string
  display_name: string
  is_admin: boolean
  is_staff: boolean
  is_superuser: boolean
  is_active: boolean
  time_format: 'auto' | '24h' | '12h'
  date_format: 'auto' | 'dmy' | 'mdy' | 'ymd'
  created_at: string
}

export interface UserGroup {
  id: string
  name: string
  description: string | null
  member_count?: number
}

export interface UserGroupMember {
  id: string
  email: string
  display_name: string
}

export interface UserGroupDetail extends UserGroup {
  members: UserGroupMember[]
}

export interface UserGroupCreate {
  name: string
  description?: string | null
}

export interface UserGroupUpdate {
  name?: string
  description?: string | null
}

export interface AdminUser {
  id: string
  email: string
  display_name: string
  is_admin: boolean
  is_staff: boolean
  is_superuser: boolean
  is_active: boolean
  groups: UserGroup[]
  created_at: string
  updated_at: string
}

export interface AdminUserCreate {
  email: string
  display_name: string
  password: string
  is_admin?: boolean
  is_staff?: boolean
  is_superuser?: boolean
  is_active?: boolean
  group_ids?: string[]
}

export interface AdminUserUpdate {
  email?: string
  display_name?: string
  password?: string
  is_admin?: boolean
  is_staff?: boolean
  is_superuser?: boolean
  is_active?: boolean
  group_ids?: string[]
}

export interface AppSettings {
  id: number
  app_name: string
  logo_url: string | null
  favicon_url: string | null
  default_first_weekday: number
  default_show_weekends: boolean
  default_weekend_days: number[]
  default_show_week_numbers: boolean
}

export interface AppSettingsUpdate {
  app_name?: string
  logo_url?: string | null
  favicon_url?: string | null
  default_first_weekday?: number
  default_show_weekends?: boolean
  default_weekend_days?: number[]
  default_show_week_numbers?: boolean
}

export interface CalendarMember {
  id: string
  calendar_id: string
  user_id: string
  email: string
  display_name: string
  role: 'owner' | 'editor' | 'contributor' | 'viewer'
  folder_id: string | null
  position: number
}

export interface Calendar {
  id: string
  name: string
  description: string | null
  color: string
  dark_color: string
  force_all_day: boolean
  first_weekday: number
  show_weekends: boolean
  weekend_days: number[]
  show_week_numbers: boolean
  today_color: string
  dark_today_color: string
  weekend_color: string
  dark_weekend_color: string
  owner_id: string
  is_public: boolean
  public_role: 'viewer' | 'contributor' | 'editor'
  created_at: string
  updated_at: string
  my_membership: CalendarMember | null
}

export interface CalendarGroupLink {
  id: string
  group: { id: string; name: string }
  role: 'viewer' | 'contributor' | 'editor'
}

export interface CalendarGroupLinkCreate {
  group_id: string
  role: string
}

export interface CalendarGroupLinkUpdate {
  role: string
}

export interface CalendarListItem {
  calendar: Calendar
  membership: CalendarMember
}

export interface Folder {
  id: string
  name: string
  parent_id: string | null
  position: number
}

export interface Category {
  id: string
  calendar_id: string
  name: string
  description: string | null
  color: string
  created_at: string
  updated_at: string
}

export interface Resource {
  id: string
  calendar_id: string
  name: string
  description: string | null
  color: string
  requires_approval: boolean
  is_active: boolean
  approvers: Approver[]
}

export interface Approver {
  user_id: string
  email: string
  display_name: string
}

export interface Event {
  id: string
  calendar_id: string
  creator_id: string
  creator_name: string | null
  creator_email: string | null
  title: string
  description: string | null
  start: string
  end: string
  all_day: boolean
  show_recurrence_count: boolean
  rrule: string | null
  uid: string
  category_id: string | null
  category_name: string | null
  category_color: string | null
  resource_id: string | null
  resource_name: string | null
  status: string
  decided_by: string | null
  decided_at: string | null
  decision_note: string | null
  created_at: string
  updated_at: string
  can_decide?: boolean
}

export interface Occurrence {
  event_id: string
  title: string
  description: string | null
  start: string
  end: string
  all_day: boolean
  recurrence_count: number | null
  status: string
  color: string
  dark_color: string
  category_id: string | null
  category_name: string | null
  category_color: string | null
  resource_id: string | null
  resource_name: string | null
  creator_id: string
  can_edit: boolean
  is_recurring: boolean
}

export interface EventComment {
  id: string
  event_id: string
  author_id: string
  author_name: string
  body: string
  created_at: string
}

export interface EventActivity {
  id: string
  event_id: string
  actor_id: string | null
  actor_name: string | null
  action: string
  details: { fields?: string[]; status?: string; note?: string } | null
  created_at: string
}

export interface EventParticipant {
  id: string
  event_id: string
  user_id: string | null
  email: string
  display_name: string | null
  status: 'needs_action' | 'accepted' | 'declined' | 'tentative'
  created_at: string
  updated_at: string
}

export interface EventParticipantCreate {
  user_id?: string
  email?: string
  status?: EventParticipant['status']
}

export interface SearchResult {
  id: string
  type: string
  label: string
  subtitle: string | null
  meta: Record<string, unknown> | null
}

export interface EventParticipantUpdate {
  status: EventParticipant['status']
}

export interface AppNotification {
  id: string
  type: string
  actor_id: string | null
  actor_name: string | null
  calendar_id: string | null
  event_id: string | null
  title: string
  data: { note?: string; role?: string } | null
  read_at: string | null
  created_at: string
  event_status: string | null
  response_status: EventParticipant['status'] | null
  deletable: boolean
}

export type NotificationGroup = 'approvals' | 'invitations'

export interface AppPassword {
  id: string
  label: string
  password?: string
  last_used_at: string | null
  created_at: string
}

// Auth (django-allauth headless browser client, mounted at /api/auth/v1)
interface AllauthResponse<T = unknown> {
  status: number
  data: T
  errors?: { message: string; code?: string; param?: string }[]
}

function extractDetail(err: any): string {
  const detail = err?.detail
  if (typeof detail === 'string') return detail
  if (detail?.detail) return detail.detail
  if (Array.isArray(detail?.errors)) {
    return detail.errors.map((e: any) => e.message || e.code).filter(Boolean).join(', ')
  }
  return err?.message || 'Request failed'
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

export async function register(data: {
  email: string
  display_name: string
  password: string
}): Promise<User> {
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
  entity: 'users' | 'groups' | 'resources' | 'categories' | string,
  q: string,
  options: { limit?: number; calendarId?: string } = {},
) => {
  const params = new URLSearchParams({ entity, q })
  if (options.limit !== undefined) params.set('limit', String(options.limit))
  if (options.calendarId) params.set('calendar_id', options.calendarId)
  return api<SearchResult[]>(`/api/search?${params.toString()}`)
}

// Users / app passwords
export const listAppPasswords = () =>
  api<AppPassword[]>('/api/users/me/app-passwords')

export const createAppPassword = (label: string) =>
  api<AppPassword>('/api/users/me/app-passwords', { method: 'POST', body: { label } })

export const deleteAppPassword = (id: string) =>
  api<void>(`/api/users/me/app-passwords/${id}`, { method: 'DELETE' })

export const updateProfile = (
  data: {
    display_name?: string
    time_format?: 'auto' | '24h' | '12h'
    date_format?: 'auto' | 'dmy' | 'mdy' | 'ymd'
  },
) => api<User>('/api/users/me', { method: 'PATCH', body: data })

// Calendars
export const listCalendars = () =>
  api<CalendarListItem[]>('/api/calendars')

export const getCalendar = (id: string) =>
  api<Calendar>(`/api/calendars/${id}`)

export const createCalendar = (name: string, description?: string, color?: string) =>
  api<Calendar>('/api/calendars', { method: 'POST', body: { name, description, color } })

export const updateCalendar = (id: string, data: Partial<Calendar>) =>
  api<Calendar>(`/api/calendars/${id}`, { method: 'PATCH', body: data })

export const deleteCalendar = (id: string) =>
  api<void>(`/api/calendars/${id}`, { method: 'DELETE' })

// Members
export const listMembers = (calendarId: string) =>
  api<CalendarMember[]>(`/api/calendars/${calendarId}/members`)

export const addMember = (calendarId: string, userId: string, role: string) =>
  api<CalendarMember>(`/api/calendars/${calendarId}/members`, {
    method: 'POST',
    body: { user_id: userId, role },
  })

export const updateMember = (calendarId: string, userId: string, role: string) =>
  api<CalendarMember>(`/api/calendars/${calendarId}/members/${userId}`, {
    method: 'PATCH',
    body: { role },
  })

export const removeMember = (calendarId: string, userId: string) =>
  api<void>(`/api/calendars/${calendarId}/members/${userId}`, { method: 'DELETE' })

// Calendar group access
export const listCalendarGroups = (calendarId: string) =>
  api<CalendarGroupLink[]>(`/api/calendars/${calendarId}/groups`)

export const addCalendarGroup = (
  calendarId: string,
  data: CalendarGroupLinkCreate,
) => api<CalendarGroupLink>(`/api/calendars/${calendarId}/groups`, { method: 'POST', body: data })

export const updateCalendarGroup = (
  calendarId: string,
  linkId: string,
  data: CalendarGroupLinkUpdate,
) =>
  api<CalendarGroupLink>(`/api/calendars/${calendarId}/groups/${linkId}`, {
    method: 'PATCH',
    body: data,
  })

export const removeCalendarGroup = (calendarId: string, linkId: string) =>
  api<void>(`/api/calendars/${calendarId}/groups/${linkId}`, { method: 'DELETE' })

export const updateMyMembership = (
  calendarId: string,
  data: { folder_id?: string | null; position?: number },
) =>
  api<CalendarMember>(`/api/calendars/${calendarId}/members/me`, { method: 'PATCH', body: data })

export const reorderSidebar = (
  items: { type: 'folder' | 'calendar'; id: string; parent_id?: string | null; position: number }[],
) => api<void>('/api/sidebar/reorder', { method: 'POST', body: { items } })

// Folders
export const listFolders = () => api<Folder[]>('/api/folders')

export const createFolder = (name: string, parent_id?: string | null) =>
  api<Folder>('/api/folders', { method: 'POST', body: { name, parent_id } })

export const updateFolder = (id: string, data: Partial<Folder>) =>
  api<Folder>(`/api/folders/${id}`, { method: 'PATCH', body: data })

export const deleteFolder = (id: string) =>
  api<void>(`/api/folders/${id}`, { method: 'DELETE' })

// Categories
export const listCategories = (calendarId: string) =>
  api<Category[]>(`/api/calendars/${calendarId}/categories`)

export const createCategory = (calendarId: string, data: Partial<Category>) =>
  api<Category>(`/api/calendars/${calendarId}/categories`, { method: 'POST', body: data })

export const updateCategory = (calendarId: string, id: string, data: Partial<Category>) =>
  api<Category>(`/api/calendars/${calendarId}/categories/${id}`, { method: 'PATCH', body: data })

export const deleteCategory = (calendarId: string, id: string) =>
  api<void>(`/api/calendars/${calendarId}/categories/${id}`, { method: 'DELETE' })

// Resources
export const listResources = (calendarId: string) =>
  api<Resource[]>(`/api/calendars/${calendarId}/resources`)

export const createResource = (calendarId: string, data: Partial<Resource>) =>
  api<Resource>(`/api/calendars/${calendarId}/resources`, { method: 'POST', body: data })

export const updateResource = (calendarId: string, id: string, data: Partial<Resource>) =>
  api<Resource>(`/api/calendars/${calendarId}/resources/${id}`, { method: 'PATCH', body: data })

export const deleteResource = (calendarId: string, id: string) =>
  api<void>(`/api/calendars/${calendarId}/resources/${id}`, { method: 'DELETE' })

export const listResourceApprovers = (calendarId: string, resourceId: string) =>
  api<Approver[]>(`/api/calendars/${calendarId}/resources/${resourceId}/approvers`)

export const addResourceApprover = (calendarId: string, resourceId: string, userId: string) =>
  api<Approver>(`/api/calendars/${calendarId}/resources/${resourceId}/approvers`, {
    method: 'POST',
    body: { user_id: userId },
  })

export const removeResourceApprover = (calendarId: string, resourceId: string, userId: string) =>
  api<void>(`/api/calendars/${calendarId}/resources/${resourceId}/approvers/${userId}`, { method: 'DELETE' })

// Calendar approvers
export const listCalendarApprovers = (calendarId: string) =>
  api<Approver[]>(`/api/calendars/${calendarId}/approvers`)

export const addCalendarApprover = (calendarId: string, userId: string) =>
  api<Approver>(`/api/calendars/${calendarId}/approvers`, {
    method: 'POST',
    body: { user_id: userId },
  })

export const removeCalendarApprover = (calendarId: string, userId: string) =>
  api<void>(`/api/calendars/${calendarId}/approvers/${userId}`, { method: 'DELETE' })

// Events
export const listEvents = (calendarId: string, start: string, end: string) =>
  api<Occurrence[]>(`/api/calendars/${calendarId}/events?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`)

export const getEvent = (eventId: string) =>
  api<Event>(`/api/events/${eventId}`)

export const createEvent = (calendarId: string, data: Partial<Event>) =>
  api<Event>(`/api/calendars/${calendarId}/events`, { method: 'POST', body: data })

export const updateEvent = (eventId: string, data: Partial<Event>) =>
  api<Event>(`/api/events/${eventId}`, { method: 'PATCH', body: data })

export const deleteEvent = (eventId: string) =>
  api<void>(`/api/events/${eventId}`, { method: 'DELETE' })

// Comments & activity
export const listComments = (eventId: string) =>
  api<EventComment[]>(`/api/events/${eventId}/comments`)

export const addComment = (eventId: string, body: string) =>
  api<EventComment>(`/api/events/${eventId}/comments`, {
    method: 'POST',
    body: { body },
  })

export const deleteComment = (commentId: string) =>
  api<void>(`/api/events/comments/${commentId}`, { method: 'DELETE' })

export const listActivity = (eventId: string) =>
  api<EventActivity[]>(`/api/events/${eventId}/activity`)

// Event participants
export const listEventParticipants = (eventId: string) =>
  api<EventParticipant[]>(`/api/events/${eventId}/participants`)

export const addEventParticipant = (eventId: string, data: EventParticipantCreate) =>
  api<EventParticipant>(`/api/events/${eventId}/participants`, {
    method: 'POST',
    body: data,
  })

export const updateEventParticipant = (
  eventId: string,
  participantId: string,
  data: EventParticipantUpdate,
) => api<EventParticipant>(`/api/events/${eventId}/participants/${participantId}`, {
  method: 'PATCH',
  body: data,
})

export const removeEventParticipant = (eventId: string, participantId: string) =>
  api<void>(`/api/events/${eventId}/participants/${participantId}`, {
    method: 'DELETE',
  })

// Notifications
export const listNotifications = (group?: NotificationGroup, limit = 50) =>
  api<AppNotification[]>(`/api/notifications?limit=${limit}${group ? `&group=${group}` : ''}`)

export const getOpenNotificationCounts = () =>
  api<{ approvals: number; invitations: number }>('/api/notifications/open-counts')

export const getUnreadCount = () =>
  api<{ count: number }>('/api/notifications/unread-count')

export const markNotificationRead = (id: string) =>
  api<AppNotification>(`/api/notifications/${id}/read`, { method: 'POST' })

export const markAllNotificationsRead = () =>
  api<{ ok: boolean }>('/api/notifications/read-all', { method: 'POST' })

export const deleteNotification = (id: string) =>
  api<void>(`/api/notifications/${id}`, { method: 'DELETE' })

// Approvals
export const listPendingApprovals = () =>
  api<Event[]>('/api/approvals')

export const approveEvent = (eventId: string, note?: string) =>
  api<Event>(`/api/events/${eventId}/approve`, { method: 'POST', body: { note } })

export const rejectEvent = (eventId: string, note?: string) =>
  api<Event>(`/api/events/${eventId}/reject`, { method: 'POST', body: { note } })

export const cancelEvent = (eventId: string) =>
  api<Event>(`/api/events/${eventId}/cancel`, { method: 'POST' })

// Feed
export const getFeedUrl = (calendarId: string) =>
  api<{ feed_url: string }>(`/api/calendars/${calendarId}/feed-url`)

export const rotateFeedToken = (calendarId: string) =>
  api<{ feed_url: string }>(`/api/calendars/${calendarId}/feed-token/rotate`, { method: 'POST' })

// App settings (public: app name, logo, favicon, calendar defaults)
export const getAppSettings = () => api<AppSettings>('/api/settings')

// Admin
export const updateAppSettings = (data: AppSettingsUpdate) =>
  api<AppSettings>('/api/admin/settings', { method: 'PATCH', body: data })

export const listAdminUsers = () =>
  api<AdminUser[]>('/api/admin/users')

export const createAdminUser = (data: AdminUserCreate) =>
  api<AdminUser>('/api/admin/users', { method: 'POST', body: data })

export const updateAdminUser = (userId: string, data: AdminUserUpdate) =>
  api<AdminUser>(`/api/admin/users/${userId}`, { method: 'PATCH', body: data })

export const deleteAdminUser = (userId: string) =>
  api<void>(`/api/admin/users/${userId}`, { method: 'DELETE' })

export const resetAdminUserPassword = (userId: string) =>
  api<{ password: string }>(`/api/admin/users/${userId}/reset-password`, { method: 'POST' })

// Admin user groups
export const listUserGroups = () =>
  api<UserGroup[]>('/api/groups')

export const createUserGroup = (data: UserGroupCreate) =>
  api<UserGroupDetail>('/api/groups', { method: 'POST', body: data })

export const getUserGroup = (groupId: string) =>
  api<UserGroupDetail>(`/api/groups/${groupId}`)

export const updateUserGroup = (groupId: string, data: UserGroupUpdate) =>
  api<UserGroupDetail>(`/api/groups/${groupId}`, { method: 'PATCH', body: data })

export const deleteUserGroup = (groupId: string) =>
  api<void>(`/api/groups/${groupId}`, { method: 'DELETE' })

export const addUserGroupMember = (groupId: string, userId: string) =>
  api<void>(`/api/groups/${groupId}/members/${userId}`, { method: 'POST' })

export const removeUserGroupMember = (groupId: string, userId: string) =>
  api<void>(`/api/groups/${groupId}/members/${userId}`, { method: 'DELETE' })
