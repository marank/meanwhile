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

10. **Per-occurrence editing** of recurring events using `RECURRENCE-ID` ("this event", "this and following", "entire series"); also enables drag & drop for recurring events.
11. **Event reminders** — multiple reminders per event, in-app first, then email; per-user/calendar defaults.
12. **Event attachments** — documents or links, with storage limits and file validation.
13. **Event templates** — presets for duration, category, resource and recurrence.
14. **Duplicate / copy event** — copy an event to another date or calendar.

### Collaboration

15. **Invite/accept flow** — added members accept or decline membership, with expiration and resend.
16. **Email notifications** via SMTP for invitations, approval requests, decisions, comments and reminders, with per-user preferences.
17. **Free/busy view** — compare members, calendars or resources without exposing private details.

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

## Known v1 limitations

- No automatically created personal calendar (by design).
- Avatars are initials-based; no image upload.
- Approval decisions are in-app only, no emails.
- No separate admin role; calendar owners manage their calendars.
- Recurring events are edited as a whole series; per-occurrence editing is future work. Recurring events cannot be moved or resized by drag & drop.
- Event activity history is not recorded for changes made through CalDAV clients.
- Outlook does not support native CalDAV; use iCal subscription or the Outlook CalDav Synchronizer plugin on classic Outlook.
- Resource/approval metadata is not exposed to generic CalDAV clients; it remains a web-app concept.
