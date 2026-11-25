import type { RouteLocationRaw } from 'vue-router'

const START = '/calendar'

/** A path of this app (not another site: "//host" or "/\host" would leave it), else null. */
function ownPath(value: unknown): string | null {
  if (typeof value !== 'string' || !value.startsWith('/') || /^\/[/\\]/.test(value)) return null
  return value
}

/** The login page, going on to `path` once signed in, e.g. the request an email's link opened. */
export function loginRoute(path: string): RouteLocationRaw {
  const target = ownPath(path)
  if (!target || target === '/' || target === START || target.startsWith('/login')) return '/login'
  return { path: '/login', query: { redirect: target } }
}

/** Where to go after signing in: the page the login was asked for, else the calendar. */
export function afterLogin(redirect: unknown): string {
  return ownPath(redirect) ?? START
}
