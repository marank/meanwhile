# Backlog

Features and improvements proposed for future releases.

## Nice-to-have enhancements

### Calendar usability

1. **Event search** — search title, description, category, resource and calendar, with date-range and calendar filters.
2. **Agenda / list view** — upcoming events grouped by day or week; "who's off today" and "upcoming bookings" views.
3. **iCal import** — upload `.ics` files with a preview, destination calendar selection and duplicate handling.
4. **Mini month calendar in sidebar** — quick navigation, highlighting days with events.
5. **Saved calendar views** — remember active calendars, view type, filters and date; optionally named views. (A calendar can already be opened on a month, week or view through URL parameters, which a saved view could build on.)
6. **Per-membership color override** — let users choose how each shared calendar appears for them.
7. **Working-hours settings** — workday start/end, dimmed non-working hours, warnings for events outside them.
8. **User timezone selection** — a setting in the account to display and edit events in a chosen timezone instead of the browser's (users have a timezone field already, but nothing sets it; events keep their own timezone).

### Events and recurrence

9. **Reminder defaults** — per-user and per-calendar default reminders for new events (in-app and email reminders and CalDAV alarms exist).
10. **Event attachments** — documents or links, with storage limits and file validation.
11. **Event templates** — presets for duration, category, resource and recurrence.
12. **Duplicate / copy event** — copy an event to another date or calendar.
13. **Show as: free / busy / tentative / out of office** — a field on the event (like Outlook's "Show as"). Read and write `TRANSP` and `X-MICROSOFT-CDO-BUSYSTATUS` over CalDAV and in the feed, so a "free" event set in Thunderbird, Apple Calendar or Outlook is no longer lost. Availability then ignores free events (and "working elsewhere"), counts tentative ones as tentative, and could show out of office distinctly; resources always block. Start with the organizer's own status; a status per participant (their own answer on the event) and the Outlook-only values "out of office" and "working elsewhere" can follow.

### Collaboration

14. **Invite/accept flow** — added members accept or decline membership, with expiration and resend.
15. **Free/busy across days** — a week view of the availability of members and resources, and suggestions of free times (the event dialog shows one day).

### Resource booking

16. **Resource booking limits** — max duration, minimum notice, max days ahead, prevent past bookings.
17. **Resource availability schedules** — weekday availability, maintenance periods, capacity for concurrent bookings.
18. **Flexible approval policies** — any one approver vs. all approvers; conditional or automatic approval.
19. **Resource utilization reports** — usage, peak periods, rejected requests; CSV export.

### Administration and reliability

20. **Audit log** — administrative, membership, calendar and approval changes, filterable by actor, calendar, action and date.
21. **Data export and backup** — user/calendar export, admin backup and restore workflow.
22. **Admin dashboard** — users, active calendars, pending approvals, resource usage, recent activity.
23. **Soft deletion and trash** — recover deleted events and calendars for a configurable period.
24. **Rate-limit failed CalDAV logins** — Radicale waits about a second after every failed login. Since the move to ASGI, CalDAV requests run in their own thread pool (20 threads per process), so they no longer hold up the app and API, but a flood of wrong logins can still occupy that pool. Rate-limit `/caldav` in the reverse proxy (e.g. nginx `limit_req`, or fail2ban on 401 answers).
25. **Approvers who lose access through a group** — removing a member removes them as an approver unless they keep access some other way. Losing access *through a group* (the group link removed, or the user taken out of the group) doesn't: the user stays listed as approver of the calendar and its resources, although they can no longer decide on bookings, and are notified of requests. Clean up the approver entries when a group link or a group membership ends, for those who then have no access left.

### Code quality

26. **oxlint warnings fail CI** — `pnpm lint` passes with warnings, so they pile up unnoticed in the CI log. Run oxlint with `--deny-warnings` in `frontend/package.json` (the `lint` script, which CI and the VS Code check task run). Two warnings are there today: `unicorn(no-useless-spread)` in `saveParticipants` (`frontend/src/components/event/EventModal.vue`). The copies are deliberate (the loops go over a snapshot while the lists shrink), so silence the rule there with a comment rather than removing them.

## Known v1 limitations

- No automatically created personal calendar (by design).
- Avatars are initials-based; no image upload.
- Only changes made in the app are sent to participants by email (iMIP). CalDAV clients that change events send their own invitations (Thunderbird does), so the server doesn't schedule for them.
- An answer by email or link counts for the whole series; answers for single occurrences are only taken from mail programs for occurrences that were changed. Taking someone off a single occurrence sends nothing.
- No separate admin role; calendar owners manage their calendars.
- Outlook does not support native CalDAV; use iCal subscription or the Outlook CalDav Synchronizer plugin on classic Outlook.
- Bookings are made, rescheduled and decided in the app; CalDAV clients see the booked resource as location and pending bookings not at all.
