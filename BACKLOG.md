# Backlog

Features and improvements proposed for future releases.

## Nice-to-have enhancements

### Calendar usability

1. **Event search** — search title, description, category, resource and calendar, with date-range and calendar filters.
2. **Agenda / list view** — upcoming events grouped by day or week; "who's off today" and "upcoming bookings" views.
3. **iCal import** — upload `.ics` files with a preview, destination calendar selection and duplicate handling.
4. **Mini month calendar in sidebar** — quick navigation, highlighting days with events.
5. **Saved calendar views** — remember active calendars, view type, filters and date; optionally named views.
6. **Per-membership color override** — let users choose how each shared calendar appears for them.
7. **Working-hours settings** — workday start/end, dimmed non-working hours, warnings for events outside them.
8. **User timezone selection** — display and edit events in a chosen timezone instead of the browser's.
9. **Additional appearance settings**.

### Events and recurrence

10. **Reminder defaults and email reminders** — per-user and per-calendar default reminders for new events; reminders by email once SMTP is set up (in-app reminders and CalDAV alarms exist).
11. **Event attachments** — documents or links, with storage limits and file validation.
12. **Event templates** — presets for duration, category, resource and recurrence.
13. **Duplicate / copy event** — copy an event to another date or calendar.

### Collaboration

14. **Invite/accept flow** — added members accept or decline membership, with expiration and resend.
15. **Email notifications** via SMTP for invitations, approval requests, decisions, comments and reminders, with per-user preferences.
16. **Invitations by email (iMIP)** — send participants an invitation with the event as `.ics` attachment (METHOD:REQUEST), so they can accept or decline from any mail program; read the replies (METHOD:REPLY) back into their participation status, and send updates and cancellations when the event changes. Participants without an account are reached this way, too.
17. **Free/busy across days** — a week view of the availability of members and resources, and suggestions of free times (the event dialog shows one day).

### Resource booking

18. **Resource booking limits** — max duration, minimum notice, max days ahead, prevent past bookings.
19. **Resource availability schedules** — weekday availability, maintenance periods, capacity for concurrent bookings.
20. **Flexible approval policies** — any one approver vs. all approvers; conditional or automatic approval.
21. **Resource utilization reports** — usage, peak periods, rejected requests; CSV export.

### Administration and reliability

22. **Audit log** — administrative, membership, calendar and approval changes, filterable by actor, calendar, action and date.
23. **Data export and backup** — user/calendar export, admin backup and restore workflow.
24. **Admin dashboard** — users, active calendars, pending approvals, resource usage, recent activity.
25. **Soft deletion and trash** — recover deleted events and calendars for a configurable period.
26. **Rate-limit failed CalDAV logins** — Radicale waits about a second after every failed login. Since the move to ASGI, CalDAV requests run in their own thread pool (20 threads per process), so they no longer hold up the app and API, but a flood of wrong logins can still occupy that pool. Rate-limit `/caldav` in the reverse proxy (e.g. nginx `limit_req`, or fail2ban on 401 answers).

## Known v1 limitations

- No automatically created personal calendar (by design).
- Avatars are initials-based; no image upload.
- Approval decisions are in-app only, no emails.
- No separate admin role; calendar owners manage their calendars.
- Outlook does not support native CalDAV; use iCal subscription or the Outlook CalDav Synchronizer plugin on classic Outlook.
- Bookings are made, rescheduled and decided in the app; CalDAV clients see the booked resource as location and pending bookings not at all.
