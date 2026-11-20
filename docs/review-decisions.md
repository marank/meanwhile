# Review decisions

Points a code review raised and that were deliberately left as they are. A later review doesn't raise
them again unless the reason no longer holds.

- 2026-11-20 `useGoBack`, `api.listNotifications(limit)`, `SearchableSelect` (`defaultLimit`, `debounceMs`) – Optional parameters nobody sets. Reason: a few lines, nothing gained for the reader. Revisit when: they get in the way of a change.
- 2026-11-20 `apps/core/realtime/broadcast.py` – `None` checks on ids. Reason: small and harmless. Revisit when: the module is reworked.
- 2026-11-20 Login, password reset and sign-out views – No shared card component for their repeated frame. Reason: about nine lines of repetition, cheaper than the abstraction. Revisit when: a fourth such view appears.
- 2026-11-20 `except Exception` in mail fetching, Redis and iTIP – Kept. Reason: each is a deliberate boundary with a comment saying why. Revisit when: one of them hides a real error.
- 2026-11-20 `services/sidebarDrag.ts:descendantFolderIds` – Not merged with the calendar store's tree walk. Reason: it works on the drag tree's own shape and keeps the service free of the store. Revisit when: both trees become one.
- 2026-11-20 `services/datetime.ts:toDateInputValue` beside `services/days.ts:dayKey` – Same three lines. Reason: datetime.ts pulls in i18n and the auth store, which the pure day helpers and their tests shouldn't. Revisit when: datetime.ts loses those imports.
- 2026-11-20 `views/approvals.py:_approval_recipients` – Not merged with `services/events.py:_notify_approval_requested`. Reason: it notifies the approvers of all booked resources, the other only those still awaiting a decision.
