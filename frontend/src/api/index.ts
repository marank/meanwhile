import { api } from './client'

export * from './client'

export interface TokenResponse {
  access_token: string
  token_type: string
}

export interface User {
  id: string
  email: string
  display_name: string
  is_admin: boolean
  is_active: boolean
  created_at: string
}

export interface AdminUser {
  id: string
  email: string
  display_name: string
  is_admin: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface AdminUserCreate {
  email: string
  display_name: string
  password: string
  is_admin?: boolean
  is_active?: boolean
}

export interface AdminUserUpdate {
  email?: string
  display_name?: string
  password?: string
  is_admin?: boolean
  is_active?: boolean
}

export interface AppSettings {
  id: number
  app_name: string
  logo_url: string | null
  favicon_url: string | null
  default_first_weekday: number
  default_show_weekends: boolean
  default_weekend_days: number[]
}

export interface AppSettingsUpdate {
  app_name?: string
  logo_url?: string | null
  favicon_url?: string | null
  default_first_weekday?: number
  default_show_weekends?: boolean
  default_weekend_days?: number[]
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
  today_color: string
  dark_today_color: string
  weekend_color: string
  dark_weekend_color: string
  owner_id: string
  created_at: string
  updated_at: string
  my_membership: CalendarMember | null
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
}

export interface AppPassword {
  id: string
  label: string
  password?: string
  last_used_at: string | null
  created_at: string
}

// Auth
export const register = (data: { email: string; display_name: string; password: string }) =>
  api<TokenResponse>('/api/auth/register', { method: 'POST', body: data })

export const login = (data: { email: string; password: string }) =>
  api<TokenResponse>('/api/auth/login', { method: 'POST', body: data })

export const me = (token: string) => api<User>('/api/users/me', { token })

export const searchUsers = (token: string, q: string) =>
  api<User[]>(`/api/users/search?q=${encodeURIComponent(q)}`, { token })

// Users / app passwords
export const listAppPasswords = (token: string) =>
  api<AppPassword[]>('/api/users/me/app-passwords', { token })

export const createAppPassword = (token: string, label: string) =>
  api<AppPassword>('/api/users/me/app-passwords', { method: 'POST', body: { label }, token })

export const deleteAppPassword = (token: string, id: string) =>
  api<void>(`/api/users/me/app-passwords/${id}`, { method: 'DELETE', token })

export const updateProfile = (token: string, display_name: string) =>
  api<User>('/api/users/me', { method: 'PATCH', body: { display_name }, token })

// Calendars
export const listCalendars = (token: string) =>
  api<CalendarListItem[]>('/api/calendars', { token })

export const getCalendar = (token: string, id: string) =>
  api<Calendar>(`/api/calendars/${id}`, { token })

export const createCalendar = (token: string, name: string, description?: string, color?: string) =>
  api<Calendar>('/api/calendars', { method: 'POST', body: { name, description, color }, token })

export const updateCalendar = (token: string, id: string, data: Partial<Calendar>) =>
  api<Calendar>(`/api/calendars/${id}`, { method: 'PATCH', body: data, token })

export const deleteCalendar = (token: string, id: string) =>
  api<void>(`/api/calendars/${id}`, { method: 'DELETE', token })

// Members
export const listMembers = (token: string, calendarId: string) =>
  api<CalendarMember[]>(`/api/calendars/${calendarId}/members`, { token })

export const addMember = (token: string, calendarId: string, userId: string, role: string) =>
  api<CalendarMember>(`/api/calendars/${calendarId}/members`, {
    method: 'POST',
    body: { user_id: userId, role },
    token,
  })

export const updateMember = (token: string, calendarId: string, userId: string, role: string) =>
  api<CalendarMember>(`/api/calendars/${calendarId}/members/${userId}`, {
    method: 'PATCH',
    body: { role },
    token,
  })

export const removeMember = (token: string, calendarId: string, userId: string) =>
  api<void>(`/api/calendars/${calendarId}/members/${userId}`, { method: 'DELETE', token })

export const updateMyMembership = (
  token: string,
  calendarId: string,
  data: { folder_id?: string | null; position?: number },
) =>
  api<CalendarMember>(`/api/calendars/${calendarId}/members/me`, { method: 'PATCH', body: data, token })

export const reorderSidebar = (
  token: string,
  items: { type: 'folder' | 'calendar'; id: string; parent_id?: string | null; position: number }[],
) => api<void>('/api/sidebar/reorder', { method: 'POST', body: { items }, token })

// Folders
export const listFolders = (token: string) => api<Folder[]>('/api/folders', { token })

export const createFolder = (token: string, name: string, parent_id?: string | null) =>
  api<Folder>('/api/folders', { method: 'POST', body: { name, parent_id }, token })

export const updateFolder = (token: string, id: string, data: Partial<Folder>) =>
  api<Folder>(`/api/folders/${id}`, { method: 'PATCH', body: data, token })

export const deleteFolder = (token: string, id: string) =>
  api<void>(`/api/folders/${id}`, { method: 'DELETE', token })

// Categories
export const listCategories = (token: string, calendarId: string) =>
  api<Category[]>(`/api/calendars/${calendarId}/categories`, { token })

export const createCategory = (token: string, calendarId: string, data: Partial<Category>) =>
  api<Category>(`/api/calendars/${calendarId}/categories`, { method: 'POST', body: data, token })

export const updateCategory = (token: string, id: string, data: Partial<Category>) =>
  api<Category>(`/api/categories/${id}`, { method: 'PATCH', body: data, token })

export const deleteCategory = (token: string, id: string) =>
  api<void>(`/api/categories/${id}`, { method: 'DELETE', token })

// Resources
export const listResources = (token: string, calendarId: string) =>
  api<Resource[]>(`/api/calendars/${calendarId}/resources`, { token })

export const createResource = (token: string, calendarId: string, data: Partial<Resource>) =>
  api<Resource>(`/api/calendars/${calendarId}/resources`, { method: 'POST', body: data, token })

export const updateResource = (token: string, id: string, data: Partial<Resource>) =>
  api<Resource>(`/api/resources/${id}`, { method: 'PATCH', body: data, token })

export const deleteResource = (token: string, id: string) =>
  api<void>(`/api/resources/${id}`, { method: 'DELETE', token })

export const listResourceApprovers = (token: string, resourceId: string) =>
  api<Approver[]>(`/api/resources/${resourceId}/approvers`, { token })

export const addResourceApprover = (token: string, resourceId: string, userId: string) =>
  api<Approver>(`/api/resources/${resourceId}/approvers`, {
    method: 'POST',
    body: { user_id: userId },
    token,
  })

export const removeResourceApprover = (token: string, resourceId: string, userId: string) =>
  api<void>(`/api/resources/${resourceId}/approvers/${userId}`, { method: 'DELETE', token })

// Calendar approvers
export const listCalendarApprovers = (token: string, calendarId: string) =>
  api<Approver[]>(`/api/calendars/${calendarId}/approvers`, { token })

export const addCalendarApprover = (token: string, calendarId: string, userId: string) =>
  api<Approver>(`/api/calendars/${calendarId}/approvers`, {
    method: 'POST',
    body: { user_id: userId },
    token,
  })

export const removeCalendarApprover = (token: string, calendarId: string, userId: string) =>
  api<void>(`/api/calendars/${calendarId}/approvers/${userId}`, { method: 'DELETE', token })

// Events
export const listEvents = (token: string, calendarId: string, start: string, end: string) =>
  api<Occurrence[]>(`/api/calendars/${calendarId}/events?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`, { token })

export const getEvent = (token: string, eventId: string) =>
  api<Event>(`/api/calendars/events/${eventId}`, { token })

export const createEvent = (token: string, calendarId: string, data: Partial<Event>) =>
  api<Event>(`/api/calendars/${calendarId}/events`, { method: 'POST', body: data, token })

export const updateEvent = (token: string, eventId: string, data: Partial<Event>) =>
  api<Event>(`/api/calendars/events/${eventId}`, { method: 'PATCH', body: data, token })

export const deleteEvent = (token: string, eventId: string) =>
  api<void>(`/api/calendars/events/${eventId}`, { method: 'DELETE', token })

// Approvals
export const listPendingApprovals = (token: string) =>
  api<Event[]>('/api/approvals', { token })

export const approveEvent = (token: string, eventId: string, note?: string) =>
  api<Event>(`/api/events/${eventId}/approve`, { method: 'POST', body: { note }, token })

export const rejectEvent = (token: string, eventId: string, note?: string) =>
  api<Event>(`/api/events/${eventId}/reject`, { method: 'POST', body: { note }, token })

export const cancelEvent = (token: string, eventId: string) =>
  api<Event>(`/api/events/${eventId}/cancel`, { method: 'POST', token })

// Feed
export const getFeedUrl = (token: string, calendarId: string) =>
  api<{ feed_url: string }>(`/api/calendars/${calendarId}/feed-url`, { token })

export const rotateFeedToken = (token: string, calendarId: string) =>
  api<{ feed_url: string }>(`/api/calendars/${calendarId}/feed-token/rotate`, { method: 'POST', token })

// Admin
export const getAppSettings = (token: string) =>
  api<AppSettings>('/api/admin/settings', { token })

export const updateAppSettings = (token: string, data: AppSettingsUpdate) =>
  api<AppSettings>('/api/admin/settings', { method: 'PATCH', body: data, token })

export const listAdminUsers = (token: string) =>
  api<AdminUser[]>('/api/admin/users', { token })

export const createAdminUser = (token: string, data: AdminUserCreate) =>
  api<AdminUser>('/api/admin/users', { method: 'POST', body: data, token })

export const updateAdminUser = (token: string, userId: string, data: AdminUserUpdate) =>
  api<AdminUser>(`/api/admin/users/${userId}`, { method: 'PATCH', body: data, token })

export const deleteAdminUser = (token: string, userId: string) =>
  api<void>(`/api/admin/users/${userId}`, { method: 'DELETE', token })

export const resetAdminUserPassword = (token: string, userId: string) =>
  api<{ password: string }>(`/api/admin/users/${userId}/reset-password`, { method: 'POST', token })
