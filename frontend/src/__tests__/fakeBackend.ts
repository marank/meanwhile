import { vi } from 'vitest'

/** A request as the fake backend saw it. */
export interface FakeRequest {
  method: string
  /** Without the query string. */
  path: string
  query: URLSearchParams
  headers: Record<string, string>
  body: unknown
}

/** What a route answers: a value (sent as JSON), a Response, or a function of the request giving either. */
type Answer = ((request: FakeRequest) => unknown) | object | string | number | boolean | null | undefined

/** Answers with an error status; the detail is sent as JSON. */
export function reply(status: number, detail: unknown = null): Response {
  return new Response(detail === undefined ? null : JSON.stringify(detail), {
    status,
    statusText: `Status ${status}`,
    headers: { 'Content-Type': 'application/json' },
  })
}

/**
 * Replaces `fetch` with a backend that answers from `routes`, keyed by "METHOD /path" where a `*` stands for one
 * path segment (e.g. "GET /api/calendars/*\/members"). A route given `undefined` answers 204. Requests without a
 * route are answered 404 and kept in `unhandled`, so tests can check that nothing unexpected was asked for.
 */
export function fakeBackend(routes: Record<string, Answer> = {}) {
  const table = new Map(Object.entries(routes))
  const requests: FakeRequest[] = []
  const unhandled: FakeRequest[] = []

  const matches = (pattern: string, method: string, path: string) => {
    const [patternMethod, patternPath] = pattern.split(' ', 2)
    if (patternMethod !== method) return false
    const want = patternPath!.split('/')
    const have = path.split('/')
    return want.length === have.length && want.every((part, i) => part === '*' || part === have[i])
  }

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = new URL(input instanceof Request ? input.url : String(input), 'http://localhost')
    const request: FakeRequest = {
      method: init.method ?? 'GET',
      path: decodeURIComponent(url.pathname),
      query: url.searchParams,
      headers: (init.headers ?? {}) as Record<string, string>,
      // JSON as the value it encodes; FormData (uploads) as it is.
      body: typeof init.body === 'string' ? JSON.parse(init.body) : (init.body ?? undefined),
    }
    requests.push(request)
    // The latest route wins, so a test can override what beforeEach set up.
    const key = [...table.keys()].reverse().find((pattern) => matches(pattern, request.method, request.path))
    if (key === undefined) {
      unhandled.push(request)
      return reply(404, { detail: `No route for ${request.method} ${request.path}` })
    }
    const route = table.get(key)
    const answer = typeof route === 'function' ? await route(request) : route
    // A clone, as a body can be read only once and a route may be asked more than once.
    if (answer instanceof Response) return answer.clone()
    if (answer === undefined) return new Response(null, { status: 204 })
    return new Response(JSON.stringify(answer), { status: 200, headers: { 'Content-Type': 'application/json' } })
  })
  vi.stubGlobal('fetch', fetchMock)

  return {
    requests,
    unhandled,
    /** Adds or replaces a route. */
    on(pattern: string, answer: Answer) {
      table.delete(pattern)
      table.set(pattern, answer)
    },
    /** The requests made to one route, e.g. "POST /api/calendars". */
    calls(pattern: string) {
      const [method, path] = pattern.split(' ', 2)
      return requests.filter((r) => matches(`${method} ${path}`, r.method, r.path))
    },
  }
}

export type FakeBackend = ReturnType<typeof fakeBackend>
