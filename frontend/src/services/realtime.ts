import { ref } from 'vue'

/**
 * Live updates over a WebSocket. The server only says *that* something changed (a calendar's
 * events, the user's notifications); the stores then load it again through the API.
 *
 * Made to stay connected: it reconnects with growing, jittered delays; a heartbeat finds
 * connections that died silently (sleep, network change, a proxy dropping idle ones); it
 * reconnects at once when the network returns or the tab is shown again; and after every
 * reconnect it follows the same calendars again and reports `reconnected`, so that whatever
 * was missed meanwhile is loaded.
 */

export type RealtimeStatus = 'idle' | 'connecting' | 'open' | 'closed'

export interface RealtimeMessage {
  type: string
  [key: string]: unknown
}

type Handler = (message: RealtimeMessage) => void

function isMessage(value: unknown): value is RealtimeMessage {
  return typeof value === 'object' && value !== null && typeof (value as { type?: unknown }).type === 'string'
}

/** Close codes after which reconnecting can't help until the user signs in again. */
const CLOSE_UNAUTHENTICATED = 4401
const CLOSE_FORBIDDEN_ORIGIN = 4403
/** Our own code for giving up on a connection that stopped answering. */
const CLOSE_NO_HEARTBEAT = 4000

export interface RealtimeOptions {
  url?: () => string
  /** Time between pings; below common proxy idle timeouts (e.g. nginx: 60 s). */
  heartbeatMs?: number
  /** How long a ping may go unanswered before the connection counts as dead. */
  pongTimeoutMs?: number
  initialRetryMs?: number
  maxRetryMs?: number
  createSocket?: (url: string) => WebSocket
}

function defaultUrl(): string {
  // Same origin as the page: in development the Vite server passes it on, deployed the reverse
  // proxy, which also turns wss:// (HTTPS) into a plain connection to the backend.
  const scheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${scheme}//${window.location.host}/ws/`
}

export class RealtimeClient {
  readonly status = ref<RealtimeStatus>('idle')

  private readonly options: Required<RealtimeOptions>
  private socket: WebSocket | null = null
  private running = false
  private calendars: string[] = []
  private readonly handlers = new Map<string, Set<Handler>>()
  private retries = 0
  private everConnected = false
  private retryTimer: ReturnType<typeof setTimeout> | undefined
  private heartbeatTimer: ReturnType<typeof setInterval> | undefined
  private pongTimer: ReturnType<typeof setTimeout> | undefined

  constructor(options: RealtimeOptions = {}) {
    this.options = {
      url: options.url ?? defaultUrl,
      heartbeatMs: options.heartbeatMs ?? 25_000,
      pongTimeoutMs: options.pongTimeoutMs ?? 10_000,
      initialRetryMs: options.initialRetryMs ?? 1_000,
      maxRetryMs: options.maxRetryMs ?? 30_000,
      createSocket: options.createSocket ?? ((url) => new WebSocket(url)),
    }
  }

  /** Connects and stays connected until stop(); call it once signed in. */
  start() {
    if (this.running) return
    this.running = true
    this.retries = 0
    this.everConnected = false
    window.addEventListener('online', this.onWake)
    document.addEventListener('visibilitychange', this.onWake)
    this.connect()
  }

  /** Disconnects for good, e.g. on sign-out. */
  stop() {
    this.running = false
    window.removeEventListener('online', this.onWake)
    document.removeEventListener('visibilitychange', this.onWake)
    clearTimeout(this.retryTimer)
    this.drop(1000)
    this.status.value = 'idle'
  }

  /** The calendars shown now; their changes are reported as `events.changed`. */
  setCalendars(ids: string[]) {
    const next = [...new Set(ids)].sort()
    if (next.join(',') === this.calendars.join(',')) return
    this.calendars = next
    this.sendSubscription()
  }

  /** Listens for a message type (or `reconnected`); returns a function that stops listening. */
  on(type: string, handler: Handler): () => void {
    let set = this.handlers.get(type)
    if (!set) this.handlers.set(type, (set = new Set()))
    set.add(handler)
    return () => set.delete(handler)
  }

  private emit(message: RealtimeMessage) {
    for (const handler of this.handlers.get(message.type) ?? []) {
      try {
        handler(message)
      } catch (error) {
        console.error('Live update handler failed', error)
      }
    }
  }

  private connect() {
    if (!this.running || this.socket) return
    clearTimeout(this.retryTimer)
    this.status.value = 'connecting'
    let socket: WebSocket
    try {
      socket = this.options.createSocket(this.options.url())
    } catch {
      this.scheduleReconnect()
      return
    }
    this.socket = socket
    socket.onopen = () => this.onOpen(socket)
    socket.onmessage = (event) => this.onMessage(socket, event)
    socket.onclose = (event) => this.onClose(socket, event.code)
    // An error is always followed by close, which handles it.
    socket.onerror = () => {}
  }

  private onOpen(socket: WebSocket) {
    if (socket !== this.socket) return
    this.status.value = 'open'
    this.sendSubscription()
    this.startHeartbeat()
  }

  private onMessage(socket: WebSocket, event: MessageEvent) {
    if (socket !== this.socket || typeof event.data !== 'string') return
    let message: unknown
    try {
      message = JSON.parse(event.data)
    } catch {
      return
    }
    if (!isMessage(message)) return
    // Any message shows the connection is alive.
    clearTimeout(this.pongTimer)
    if (message.type === 'hello') {
      this.retries = 0
      // Changes made while disconnected weren't reported: let the app load what it shows again.
      if (this.everConnected) this.emit({ type: 'reconnected' })
      this.everConnected = true
      return
    }
    if (message.type === 'pong') return
    this.emit(message)
  }

  private onClose(socket: WebSocket, code: number) {
    if (socket !== this.socket) return
    this.detach()
    this.status.value = 'closed'
    if (code === CLOSE_UNAUTHENTICATED || code === CLOSE_FORBIDDEN_ORIGIN) {
      // Retrying can't help; start() again after the next sign-in.
      this.running = false
      this.emit({ type: code === CLOSE_UNAUTHENTICATED ? 'unauthenticated' : 'forbidden' })
      return
    }
    this.scheduleReconnect()
  }

  private scheduleReconnect() {
    if (!this.running) return
    clearTimeout(this.retryTimer)
    const base = Math.min(this.options.maxRetryMs, this.options.initialRetryMs * 2 ** this.retries)
    this.retries += 1
    // Jitter, so that clients don't all come back at the same moment after a server restart.
    const delay = base / 2 + Math.random() * (base / 2)
    this.retryTimer = setTimeout(() => this.connect(), delay)
  }

  private startHeartbeat() {
    clearInterval(this.heartbeatTimer)
    this.heartbeatTimer = setInterval(() => this.ping(), this.options.heartbeatMs)
  }

  private ping() {
    if (!this.send({ type: 'ping' })) return
    clearTimeout(this.pongTimer)
    this.pongTimer = setTimeout(() => {
      // No answer: the connection is gone even if the browser hasn't noticed. Replace it.
      this.drop(CLOSE_NO_HEARTBEAT)
      this.status.value = 'closed'
      this.scheduleReconnect()
    }, this.options.pongTimeoutMs)
  }

  // The network came back, or the tab is shown again after a while (the computer may have slept).
  private readonly onWake = () => {
    if (!this.running || document.visibilityState === 'hidden') return
    if (this.socket && this.status.value === 'open') {
      this.ping()
    } else if (!this.socket) {
      this.retries = 0
      this.connect()
    }
  }

  private sendSubscription() {
    this.send({ type: 'subscribe', calendars: this.calendars })
  }

  private send(message: RealtimeMessage): boolean {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) return false
    try {
      this.socket.send(JSON.stringify(message))
      return true
    } catch {
      return false
    }
  }

  /** Forgets the current connection, closing it without waiting for its close event. */
  private drop(code: number) {
    const socket = this.socket
    this.detach()
    if (socket) {
      socket.onopen = socket.onmessage = socket.onclose = socket.onerror = null
      try {
        socket.close(code)
      } catch {
        // already closed
      }
    }
  }

  private detach() {
    this.socket = null
    clearInterval(this.heartbeatTimer)
    clearTimeout(this.pongTimer)
  }
}

export const realtime = new RealtimeClient()
