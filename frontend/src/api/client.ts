const API_BASE = ''

function getCookie(name: string): string | null {
  const value = `; ${document.cookie}`
  const parts = value.split(`; ${name}=`)
  if (parts.length === 2) {
    return parts.pop()?.split(';').shift() || null
  }
  return null
}

export type FetchOptions = {
  method?: string
  body?: unknown
}

export async function api<T = unknown>(
  path: string,
  options: FetchOptions = {},
): Promise<T> {
  const url = `${API_BASE}${path}`
  const headers: Record<string, string> = {
    Accept: 'application/json',
    'Content-Type': 'application/json',
  }
  const method = options.method || 'GET'
  if (method !== 'GET' && method !== 'HEAD') {
    const csrf = getCookie('csrftoken')
    if (csrf) {
      headers['X-CSRFToken'] = csrf
    }
  }
  const resp = await fetch(url, {
    method,
    headers,
    credentials: 'include',
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  })
  if (!resp.ok) {
    let detail: any = await resp.text()
    try {
      detail = JSON.parse(detail)
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

export class ApiError extends Error {
  status: number
  detail: unknown
  constructor(status: number, detail: unknown, statusText: string) {
    super(`API error ${status}: ${statusText}`)
    this.status = status
    this.detail = detail
  }
}
