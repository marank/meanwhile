export type CalendarRole = 'owner' | 'editor' | 'contributor' | 'viewer'
/** Roles that can be granted to members, groups and the public; ownership isn't transferable here. */
export type GrantableRole = Exclude<CalendarRole, 'owner'>
export type EventStatus = 'confirmed' | 'pending' | 'approved' | 'rejected' | 'cancelled'
export type ParticipantStatus = 'needs_action' | 'accepted' | 'declined' | 'tentative'
export type NotificationType =
  | 'approval_requested'
  | 'booking_approved'
  | 'booking_rejected'
  | 'booking_cancelled'
  | 'participant_added'
  | 'member_added'
  | 'member_role_changed'
  | 'comment_added'

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
  member_ids?: string[]
}

export interface UserGroupUpdate {
  name?: string
  description?: string | null
  /** Replaces the member list. */
  member_ids?: string[]
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
  role: CalendarRole
  folder_id: string | null
  position: number
}

export interface Calendar {
  id: string
  name: string
  description: string | null
  force_all_day: boolean
  first_weekday: number
  show_weekends: boolean
  weekend_days: number[]
  show_week_numbers: boolean
  /** Colors per role and theme; text colors are derived for contrast. */
  base_color: string
  weekend_color: string
  today_color: string
  event_color: string
  border_color: string
  outer_border_color: string
  dark_base_color: string
  dark_weekend_color: string
  dark_today_color: string
  dark_event_color: string
  dark_border_color: string
  dark_outer_border_color: string
  owner_id: string
  is_public: boolean
  public_role: GrantableRole
  created_at: string
  updated_at: string
  my_membership: CalendarMember | null
}

/** A user's settings for the views that combine calendars: "All calendars" and folders. */
export interface OverviewSettings {
  first_weekday: number
  show_weekends: boolean
  weekend_days: number[]
  show_week_numbers: boolean
  /** Show each event in its calendar's event color instead of the overview's own. */
  use_calendar_colors: boolean
  base_color: string
  weekend_color: string
  today_color: string
  event_color: string
  border_color: string
  outer_border_color: string
  dark_base_color: string
  dark_weekend_color: string
  dark_today_color: string
  dark_event_color: string
  dark_border_color: string
  dark_outer_border_color: string
}

export interface CalendarGroupLink {
  id: string
  group: { id: string; name: string }
  role: GrantableRole
}

export interface CalendarGroupLinkCreate {
  group_id: string
  role: GrantableRole
}

export interface CalendarGroupLinkUpdate {
  role: GrantableRole
}

/** The calendar settings an owner can change. */
export type CalendarUpdate = Partial<
  Pick<
    Calendar,
    | 'name'
    | 'description'
    | 'force_all_day'
    | 'first_weekday'
    | 'show_weekends'
    | 'weekend_days'
    | 'show_week_numbers'
    | 'base_color'
    | 'weekend_color'
    | 'today_color'
    | 'event_color'
    | 'border_color'
    | 'outer_border_color'
    | 'dark_base_color'
    | 'dark_weekend_color'
    | 'dark_today_color'
    | 'dark_event_color'
    | 'dark_border_color'
    | 'dark_outer_border_color'
    | 'is_public'
    | 'public_role'
  >
>

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

export interface SidebarReorderItem {
  type: 'folder' | 'calendar'
  id: string
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

export interface ResourceInput {
  name: string
  description: string | null
  color: string
  requires_approval: boolean
  is_active: boolean
  /** The resource's own approvers; empty means the calendar's default approvers decide. */
  approver_ids: string[]
}

export interface CategoryInput {
  name: string
  description: string | null
  color: string
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
  /** IANA zone the event was planned in; recurrences repeat in its local time. */
  timezone: string
  show_recurrence_count: boolean
  rrule: string | null
  uid: string
  category_id: string | null
  category_name: string | null
  category_color: string | null
  resource_id: string | null
  resource_name: string | null
  status: EventStatus
  decided_by: string | null
  decided_at: string | null
  decision_note: string | null
  created_at: string
  updated_at: string
  can_decide?: boolean
}

export interface Occurrence {
  event_id: string
  /** The event colors come from this calendar. */
  calendar_id: string
  title: string
  description: string | null
  start: string
  end: string
  all_day: boolean
  recurrence_count: number | null
  status: EventStatus
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
  status: ParticipantStatus
  created_at: string
  updated_at: string
}

export interface EventParticipantCreate {
  user_id?: string
  email?: string
  status?: ParticipantStatus
}

export interface EventParticipantUpdate {
  status: ParticipantStatus
}

export interface EventInput {
  title: string
  description?: string | null
  start: string
  end: string
  all_day: boolean
  /** The planner's zone; the server keeps it only along with a changed schedule. */
  timezone?: string
  show_recurrence_count?: boolean
  rrule?: string | null
  category_id?: string | null
  resource_id?: string | null
  /** Only on creation: participants to invite right away. */
  participants?: EventParticipantCreate[]
}

export type ProfileUpdate = Partial<Pick<User, 'display_name' | 'time_format' | 'date_format'>>

export type SearchEntity = 'users' | 'members' | 'groups' | 'resources' | 'categories'

export interface SearchResult {
  id: string
  type: string
  label: string
  subtitle: string | null
  meta: Record<string, unknown> | null
}

export interface AppNotification {
  id: string
  type: NotificationType
  actor_id: string | null
  actor_name: string | null
  calendar_id: string | null
  event_id: string | null
  title: string
  data: { note?: string; role?: string } | null
  read_at: string | null
  created_at: string
  event_status: EventStatus | null
  response_status: ParticipantStatus | null
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
