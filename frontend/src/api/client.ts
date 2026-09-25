const API_BASE = ''

export type FetchOptions = {
  method?: string
  body?: unknown
  token?: string | null
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
  if (options.token) {
    headers.Authorization = `Bearer ${options.token}`
  }
  const resp = await fetch(url, {
    method: options.method || 'GET',
    headers,
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
