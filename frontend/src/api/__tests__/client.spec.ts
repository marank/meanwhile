import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fakeBackend, reply } from '@/__tests__/fakeBackend'
import { api, ApiError, setUnauthorizedHandler } from '../client'

describe('api client', () => {
  beforeEach(() => {
    document.cookie = 'csrftoken=token-123'
  })

  afterEach(() => {
    document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT'
    setUnauthorizedHandler(() => {})
  })

  it('sends JSON with the session cookie and parses the answer', async () => {
    const backend = fakeBackend({ 'POST /api/things': (r) => ({ echoed: r.body }) })
    await expect(api('/api/things', { method: 'POST', body: { a: 1 } })).resolves.toEqual({ echoed: { a: 1 } })
    const [request] = backend.requests
    expect(request!.headers['Content-Type']).toBe('application/json')
    expect(vi.mocked(fetch).mock.calls[0]![1]!.credentials).toBe('include')
  })

  it('sends the CSRF token with changing requests only', async () => {
    const backend = fakeBackend({ 'GET /api/x': {}, 'DELETE /api/x': undefined })
    await api('/api/x')
    await api('/api/x', { method: 'DELETE' })
    expect(backend.requests[0]!.headers['X-CSRFToken']).toBeUndefined()
    expect(backend.requests[0]!.headers['Content-Type']).toBeUndefined()
    expect(backend.requests[1]!.headers['X-CSRFToken']).toBe('token-123')
  })

  it('sends no CSRF header without the cookie', async () => {
    document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT'
    const backend = fakeBackend({ 'POST /api/x': {} })
    await api('/api/x', { method: 'POST' })
    expect(backend.requests[0]!.headers['X-CSRFToken']).toBeUndefined()
  })

  it('answers nothing for 204', async () => {
    fakeBackend({ 'DELETE /api/x': undefined })
    await expect(api('/api/x', { method: 'DELETE' })).resolves.toBeUndefined()
  })

  it('throws the status and the parsed detail of an error', async () => {
    fakeBackend({ 'GET /api/x': reply(422, { detail: [{ msg: 'bad' }] }) })
    const error = await api('/api/x').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(422)
    expect((error as ApiError).detail).toEqual({ detail: [{ msg: 'bad' }] })
  })

  it('keeps an error body that is not JSON as text', async () => {
    fakeBackend({ 'GET /api/x': new Response('Bad gateway', { status: 502 }) })
    const error = (await api('/api/x').catch((e: unknown) => e)) as ApiError
    expect(error.status).toBe(502)
    expect(error.detail).toBe('Bad gateway')
  })

  it('reports a lost session, except from the auth endpoints whose flow includes 401', async () => {
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    fakeBackend({ 'GET /api/x': reply(401), 'GET /api/auth/v1/auth/session': reply(401) })
    await expect(api('/api/auth/v1/auth/session')).rejects.toBeInstanceOf(ApiError)
    expect(handler).not.toHaveBeenCalled()
    await expect(api('/api/x')).rejects.toBeInstanceOf(ApiError)
    expect(handler).toHaveBeenCalledTimes(1)
  })
})
