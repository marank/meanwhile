import { i18n } from '@/i18n'

function getCookie(name: string): string | null {
  const value = `; ${document.cookie}`
  const parts = value.split(`; ${name}=`)
  if (parts.length === 2) {
    return parts.pop()?.split(';').shift() ?? null
  }
  return null
}

export type FetchOptions = {
  method?: string
  /** Sent as JSON; FormData (file uploads) as multipart, as the browser encodes it. */
  body?: unknown
}

export class ApiError extends Error {
  status: number
  detail: unknown
  constructor(status: number, detail: unknown, statusText: string) {
    super(`API error ${status}: ${statusText}`)
    this.status = status
    this.detail = detail
  }
}

let onUnauthorized: (() => void) | null = null

/** Called when a request fails because the session is gone (expired or logged out elsewhere). */
export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler
}

/** The body as sent, and its type: JSON, or FormData as multipart, whose type (with the boundary it
 * chose) the browser sets itself. */
function encodeBody(body: unknown): { body?: BodyInit; contentType?: string } {
  if (body === undefined) return {}
  if (body instanceof FormData) return { body }
  return { body: JSON.stringify(body), contentType: 'application/json' }
}

export async function api<T = unknown>(path: string, options: FetchOptions = {}): Promise<T> {
  const method = options.method ?? 'GET'
  // The server answers in the interface's language (its errors, password rules), not the browser's.
  const headers: Record<string, string> = { Accept: 'application/json', 'X-Language': i18n.global.locale.value }
  const { body, contentType } = encodeBody(options.body)
  if (contentType) headers['Content-Type'] = contentType
  if (method !== 'GET' && method !== 'HEAD') {
    const csrf = getCookie('csrftoken')
    if (csrf) headers['X-CSRFToken'] = csrf
  }
  const resp = await fetch(path, {
    method,
    headers,
    credentials: 'include',
    body,
  })
  if (!resp.ok) {
    // The auth endpoints answer 401 as part of their normal flow (anonymous session, logout).
    if (resp.status === 401 && !path.startsWith('/api/auth/')) onUnauthorized?.()
    const text = await resp.text()
    let detail: unknown = text
    try {
      detail = JSON.parse(text)
    } catch {
      // keep text
    }
    throw new ApiError(resp.status, detail, resp.statusText)
  }
  if (resp.status === 204) {
    return undefined as T
  }
  return (await resp.json()) as T
}
