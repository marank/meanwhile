# Frontend

Vue 3 single-page app of Meanwhile. See the [project README](../README.md) for setup and the backend.

## Scripts

| Command           | Purpose                                  |
| ----------------- | ---------------------------------------- |
| `pnpm dev`        | Dev server with hot reload               |
| `pnpm build`      | Type-check and build for production      |
| `pnpm test:unit`  | Unit tests (Vitest, in `__tests__` dirs) |
| `pnpm lint`       | ESLint, fixing what it can               |
| `pnpm format`     | Prettier                                 |
| `pnpm type-check` | vue-tsc                                  |

## Layout

- `api/` – typed API client (`types.ts` for the payloads, `index.ts` for the endpoints)
- `stores/` – Pinia stores for shared state (session, calendars, events, notifications, settings, theme)
- `composables/` – reusable component logic (`useAction`, `useLoader`, `useQueryTab`, …)
- `services/` – framework-free helpers (dates, colors, recurrence rules, error messages, dialogs, toasts)
- `components/` – shared components; feature folders for the event dialog, calendar settings and admin pages
- `views/` – one component per route
- `i18n/locales/` – translations; `de.ts` is typed against `en.ts`, so missing keys fail the type check
