import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { RealtimeClient, type RealtimeMessage } from '../realtime'

/** A stand-in for the browser's WebSocket that the test drives. */
class FakeSocket {
  readyState = 0
  sent: RealtimeMessage[] = []
  closedWith: number | null = null
  onopen: (() => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  onclose: ((event: { code: number }) => void) | null = null
  onerror: (() => void) | null = null

  send(data: string) {
    this.sent.push(JSON.parse(data))
  }

  close(code: number) {
    this.closedWith = code
    this.readyState = 3
  }

  // Driven by the test:
  open() {
    this.readyState = 1
    this.onopen?.()
    this.receive({ type: 'hello', protocol: 1 })
  }

  receive(message: RealtimeMessage) {
    this.onmessage?.({ data: JSON.stringify(message) })
  }

  serverClose(code: number) {
    this.readyState = 3
    this.onclose?.({ code })
  }
}

let sockets: FakeSocket[]
let client: RealtimeClient

function latest(): FakeSocket {
  return sockets[sockets.length - 1]!
}

beforeEach(() => {
  vi.useFakeTimers()
  vi.spyOn(Math, 'random').mockReturnValue(1)
  sockets = []
  client = new RealtimeClient({
    url: () => 'ws://test/ws/',
    heartbeatMs: 1000,
    pongTimeoutMs: 500,
    initialRetryMs: 100,
    maxRetryMs: 1000,
    createSocket: () => {
      const socket = new FakeSocket()
      sockets.push(socket)
      return socket as unknown as WebSocket
    },
  })
})

afterEach(() => {
  client.stop()
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('RealtimeClient', () => {
  it('follows the calendars shown', () => {
    client.setCalendars(['b', 'a', 'a'])
    client.start()
    latest().open()
    expect(latest().sent).toEqual([{ type: 'subscribe', calendars: ['a', 'b'] }])
    client.setCalendars(['c'])
    client.setCalendars(['c'])
    expect(latest().sent.at(-1)).toEqual({ type: 'subscribe', calendars: ['c'] })
    expect(latest().sent).toHaveLength(2)
    expect(client.status.value).toBe('open')
  })

  it('passes messages on to their listeners', () => {
    const changed = vi.fn()
    const off = client.on('events.changed', changed)
    client.start()
    latest().open()
    latest().receive({ type: 'events.changed', calendar_id: 'a' })
    expect(changed).toHaveBeenCalledWith({ type: 'events.changed', calendar_id: 'a' })
    off()
    latest().receive({ type: 'events.changed', calendar_id: 'a' })
    expect(changed).toHaveBeenCalledOnce()
  })

  it('reconnects with growing delays and then catches up', () => {
    const reconnected = vi.fn()
    client.on('reconnected', reconnected)
    client.setCalendars(['a'])
    client.start()
    latest().open()

    latest().serverClose(1006)
    expect(client.status.value).toBe('closed')
    vi.advanceTimersByTime(99)
    expect(sockets).toHaveLength(1)
    vi.advanceTimersByTime(1)
    expect(sockets).toHaveLength(2)

    // A failed attempt waits longer before the next.
    latest().serverClose(1006)
    vi.advanceTimersByTime(199)
    expect(sockets).toHaveLength(2)
    vi.advanceTimersByTime(1)
    expect(sockets).toHaveLength(3)

    latest().open()
    expect(latest().sent).toEqual([{ type: 'subscribe', calendars: ['a'] }])
    expect(reconnected).toHaveBeenCalledOnce()
  })

  it('caps the delay between attempts', () => {
    client.start()
    for (let i = 0; i < 10; i++) {
      latest().serverClose(1006)
      vi.advanceTimersByTime(1000)
    }
    expect(sockets).toHaveLength(11)
  })

  it('replaces a connection that stops answering', () => {
    client.start()
    latest().open()
    const first = latest()

    vi.advanceTimersByTime(1000)
    expect(first.sent.at(-1)).toEqual({ type: 'ping' })
    first.receive({ type: 'pong' })
    vi.advanceTimersByTime(500)
    expect(first.closedWith).toBeNull()

    vi.advanceTimersByTime(500)
    vi.advanceTimersByTime(500)
    expect(first.closedWith).toBe(4000)
    vi.advanceTimersByTime(100)
    expect(sockets).toHaveLength(2)
  })

  it('stops when the session has ended', () => {
    const unauthenticated = vi.fn()
    client.on('unauthenticated', unauthenticated)
    client.start()
    latest().open()
    latest().serverClose(4401)
    vi.advanceTimersByTime(60_000)
    expect(sockets).toHaveLength(1)
    expect(unauthenticated).toHaveBeenCalledOnce()
  })

  it('disconnects for good on stop', () => {
    client.start()
    latest().open()
    client.stop()
    expect(latest().closedWith).toBe(1000)
    vi.advanceTimersByTime(60_000)
    expect(sockets).toHaveLength(1)
    expect(client.status.value).toBe('idle')
  })

  it('reconnects at once when the network returns', () => {
    client.start()
    latest().open()
    latest().serverClose(1006)
    window.dispatchEvent(new Event('online'))
    expect(sockets).toHaveLength(2)
  })
})
