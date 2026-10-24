/**
 * The API's types, by the names the app uses. They come from the backend's OpenAPI schema
 * (`pnpm api:types` turns openapi.json into schema.d.ts); only what the schema can't say is written here.
 */
import type { components, paths } from './schema'

type Schemas = components['schemas']

export type CalendarRole = Schemas['Role']
/** Roles that can be granted to members, groups and the public; ownership isn't transferable here. */
export type GrantableRole = Schemas['CalendarGroupLinkOut']['role']
/** What everyone gets in a public calendar: never managing it. */
export type PublicRole = Schemas['CalendarOut']['public_role']
export type EventStatus = Schemas['EventStatus']

/** Which occurrences of a series a change applies to. */
export type OccurrenceScope = NonNullable<
  NonNullable<paths['/api/events/{event_id}/occurrences/{recurrence_id}']['patch']['parameters']['query']>['scope']
>
export type ParticipantStatus = Schemas['ParticipantStatus']
export type NotificationType = Schemas['NotificationOut']['type']

/** The signed-in user, with their settings. */
export type User = Schemas['ProfileOut']
/** Which kinds of notifications also come by email. */
export type EmailNotifications = Schemas['EmailNotifications']
export type ProfileUpdate = Schemas['UserUpdate']

export type UserGroup = Schemas['GroupOut']
export type UserGroupMember = Schemas['GroupMemberOut']
export type UserGroupDetail = Schemas['GroupDetailOut']
export type UserGroupCreate = Schemas['GroupCreate']
export type UserGroupUpdate = Schemas['GroupUpdate']

export type AdminUser = Schemas['AdminUserOut']
export type AdminUserCreate = Schemas['AdminUserCreate']
export type AdminUserUpdate = Schemas['AdminUserUpdate']
export type AdminPasswordReset = Schemas['AdminPasswordResetOut']

export type AppSettings = Schemas['AppSettingsOut']
export type AppSettingsUpdate = Schemas['AppSettingsUpdate']

export type CalendarMember = Schemas['CalendarMemberOut']
export type Calendar = Schemas['CalendarOut']
export type CalendarCreate = Schemas['CalendarCreate']
/** The calendar settings an owner can change. */
export type CalendarUpdate = Schemas['CalendarUpdate']
/** A user's settings for the views that combine calendars: "All calendars" and folders. */
export type OverviewSettings = Schemas['OverviewSettingsOut']
export type OverviewSettingsUpdate = Schemas['OverviewSettingsUpdate']

export type CalendarGroupLink = Schemas['CalendarGroupLinkOut']
export type CalendarGroupLinkCreate = Schemas['CalendarGroupLinkCreate']
export type CalendarGroupLinkUpdate = Schemas['CalendarGroupLinkUpdate']

export type CalendarListItem = Schemas['CalendarListOut']
/** A public calendar that can be added to the sidebar. */
export type PublicCalendar = Schemas['PublicCalendarOut']

export type Folder = Schemas['FolderOut']
export type FolderUpdate = Schemas['FolderUpdate']
export type LayoutItem = Schemas['LayoutItem']
/** What the sidebar shows: the user's folders, and the calendars with the place each has in the tree. */
export type Layout = Schemas['LayoutOut']

export type Category = Schemas['CategoryOut']
export type CategoryInput = Schemas['CategoryCreate']
export type CategoryUpdate = Schemas['CategoryUpdate']

export type Resource = Schemas['ResourceOut']
export type ResourceInput = Schemas['ResourceCreate']
export type ResourceUpdate = Schemas['ResourceUpdate']
export type Approver = Schemas['ApproverOut']

export type Event = Schemas['EventOut']
export type Occurrence = Schemas['OccurrenceOut']
/** A new event; participants are invited right away. */
export type EventInput = Schemas['EventCreate']
export type EventUpdate = Schemas['EventUpdate']
export type EventReminders = Schemas['EventRemindersOut']

export type EventComment = Schemas['CommentOut']

/** What an activity entry records besides its action; the schema only knows it as an object. */
interface ActivityDetails {
  fields?: string[]
  status?: string
  note?: string
  occurrence?: string
}

export type EventActivity = Omit<Schemas['ActivityOut'], 'details'> & { details: ActivityDetails | null }

export type EventParticipant = Schemas['EventParticipantOut']
export type EventParticipantCreate = Schemas['EventParticipantCreate']
export type EventParticipantUpdate = Schemas['EventParticipantUpdate']

/** An invitation as its participant sees it from the link in the invitation email. */
export type Invitation = Schemas['RsvpOut']
export type InvitationAnswer = Schemas['RsvpAnswer']['status']

export type SearchEntity = paths['/api/search']['get']['parameters']['query']['entity']
export type NotificationGroup = NonNullable<
  NonNullable<paths['/api/notifications']['get']['parameters']['query']>['group']
>

export type SearchResult = Schemas['SearchResult']

/** What a notification carries besides its title; the schema only knows it as an object. */
interface NotificationData {
  note?: string
  role?: string
  start?: string
  all_day?: boolean
  minutes_before?: number
  /** comment_added: the comment */
  comment?: string
  /** participant_replied: the answer, and who gave it (name only for participants with an account) */
  status?: ParticipantStatus
  email?: string
  name?: string | null
}

export type AppNotification = Omit<Schemas['NotificationOut'], 'data'> & { data: NotificationData | null }
export type NotificationCounts = Schemas['NotificationCountsOut']

export type BusyPeriod = Schemas['BusyPeriod']
/** When users and resources are taken; no titles or details. */
export type Availability = Schemas['AvailabilityOut']

export type FeedUrl = Schemas['FeedUrlOut']
export type Ok = Schemas['OkOut']

export type AppPassword = Schemas['AppPasswordOut']
/** A new app password: the only time its password is shown. */
export type AppPasswordCreated = Schemas['AppPasswordCreated']

/** A reminder that has just come due (pushed over the WebSocket, so not in the API schema); also stored as a notification. */
export interface DueReminder {
  event_id: string
  title: string
  /** The occurrence's start; for all-day events midnight in the user's zone. */
  start: string
  all_day: boolean
  minutes_before: number
}
