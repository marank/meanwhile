# Backlog

Features and improvements proposed for future releases.

## Nice-to-have enhancements

1. **In-app notification bell** — badges for pending approvals and booking decisions.
2. **Drag & drop / resize on the month grid** — move events between days and resize durations.
3. **Mini month calendar in sidebar** — quick navigation, like Google Calendar.
4. **Event search** — search titles and descriptions across visible calendars.
5. **iCal import** — upload `.ics` files to populate calendars.
6. **Per-membership color override** — let users choose how each shared calendar appears for them.
7. **Invite/accept flow** — added members accept or decline membership instead of being added directly.
8. **Agenda / list view** — week list or "who's off" view, useful for vacation calendars.
9. **Multi-approver rule choice** — any one approver vs. all approvers must approve.
10. **Resource booking limits** — max duration, max days ahead, prevent past bookings.
11. **Per-occurrence editing** of recurring events using `RECURRENCE-ID`.
12. **Email notifications** via SMTP for invitations and approval requests.
13. **Dark mode and appearance settings**.

## Known v1 limitations

- No automatically created personal calendar (by design).
- Avatars are initials-based; no image upload.
- Approval decisions are in-app only, no emails.
- No separate admin role; calendar owners manage their calendars.
- Recurring events are edited as a whole series; per-occurrence editing is future work.
- Outlook does not support native CalDAV; use iCal subscription or the Outlook CalDav Synchronizer plugin on classic Outlook.
- Resource/approval metadata is not exposed to generic CalDAV clients; it remains a web-app concept.
