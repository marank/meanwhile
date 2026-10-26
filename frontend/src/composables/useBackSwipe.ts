import { nextTick, onBeforeUnmount, ref, type Ref } from 'vue'
import { useRouter } from 'vue-router'

/** A swipe has to start this close (px) to the left edge to go back. */
export const BACK_SWIPE_EDGE = 24
/** Let go past this share of the width, or flicked faster than this (px/ms), the page goes back. */
const COMMIT_SHARE = 0.35
const COMMIT_SPEED = 0.4
const DECIDE_AFTER = 10
const SETTLE_MS = 250
/** Where the page below starts, as share of the width to the left, and how dimmed. */
const BELOW_SHIFT = 0.25
const BELOW_DIM = 0.15

interface Options {
  /** The scrolling area the pages are shown in (App.vue's <main>). */
  scroller: Ref<HTMLElement | null>
  /** On phones in the home-screen app, which has no back gesture of its own. */
  enabled: () => boolean
}

/**
 * Going back by swiping from the left edge, as in iOS: the page follows the finger to the right and
 * uncovers the one below it. Letting go far enough goes back, otherwise the page returns.
 *
 * The page below has to be shown while the finger still moves, and only the current route's page can be:
 * so the swipe goes back at once, and a copy of the page (`cover`) is what follows the finger. The page
 * itself is kept alive meanwhile (`kept`, for App.vue's KeepAlive), so a swipe taken back returns to it
 * as it was.
 */
export function useBackSwipe(options: Options) {
  const router = useRouter()
  const kept = ref<string[]>([])
  const swiping = ref(false)

  let start = { x: 0, y: 0 }
  let last = { x: 0, time: 0 }
  let speed = 0
  let decided: 'back' | 'other' | null = null
  let pointerId: number | null = null
  let cover: HTMLElement | null = null
  let width = 1
  let returnTo = ''
  let settling = 0

  function canGoBack() {
    const route = router.currentRoute.value
    return (route.meta.layer ?? 0) > 0 && Boolean(router.options.history.state.back)
  }

  function onPointerDown(event: PointerEvent) {
    if (event.pointerType !== 'touch' || swiping.value || !options.enabled()) return
    if (event.clientX > BACK_SWIPE_EDGE || !canGoBack()) return
    pointerId = event.pointerId
    decided = null
    start = { x: event.clientX, y: event.clientY }
    last = { x: event.clientX, time: event.timeStamp }
    speed = 0
  }

  /** Copies the page, as it is on the screen, over it; then goes back underneath. */
  function begin(pointer: number) {
    const scroller = options.scroller.value!
    // The element the finger is on goes away with the page; the rest of the swipe comes to the scroller.
    scroller.setPointerCapture?.(pointer)
    const rect = scroller.getBoundingClientRect()
    width = rect.width || 1
    cover = scroller.cloneNode(true) as HTMLElement
    // What has been typed isn't part of the copy.
    const fields = scroller.querySelectorAll<HTMLInputElement>('input, textarea, select')
    cover.querySelectorAll<HTMLInputElement>('input, textarea, select').forEach((field, i) => {
      field.value = fields[i]?.value ?? field.value
    })
    cover.inert = true
    cover.setAttribute('aria-hidden', 'true')
    cover.dataset.backSwipeCover = ''
    Object.assign(cover.style, {
      position: 'fixed',
      top: `${rect.top}px`,
      left: `${rect.left}px`,
      width: `${rect.width}px`,
      height: `${rect.height}px`,
      margin: '0',
      zIndex: '30',
      boxShadow: '-0.5rem 0 1.5rem rgb(0 0 0 / 0.2)',
    })
    document.body.appendChild(cover)
    cover.scrollTop = scroller.scrollTop

    const component = router.currentRoute.value.matched.at(-1)?.components?.default as { __name?: string } | undefined
    kept.value = component?.__name ? [component.__name] : []
    returnTo = router.currentRoute.value.fullPath
    swiping.value = true
    router.back()
  }

  /** Puts the copy `share` of the width to the right, and the page below where it is by then. */
  function place(share: number, animate = false) {
    const scroller = options.scroller.value
    const transition = animate ? `translate ${SETTLE_MS}ms ease-out, filter ${SETTLE_MS}ms ease-out` : 'none'
    if (cover) Object.assign(cover.style, { transition, translate: `${share * width}px 0` })
    if (scroller) {
      Object.assign(scroller.style, {
        transition,
        translate: `${-BELOW_SHIFT * (1 - share) * 100}% 0`,
        filter: `brightness(${1 - BELOW_DIM * (1 - share)})`,
      })
    }
  }

  function end() {
    cover?.remove()
    cover = null
    const scroller = options.scroller.value
    if (scroller) for (const property of ['transition', 'translate', 'filter']) scroller.style.removeProperty(property)
    kept.value = []
    swiping.value = false
  }

  function onPointerMove(event: PointerEvent) {
    if (event.pointerId !== pointerId) return
    const dx = event.clientX - start.x
    const dy = event.clientY - start.y
    if (decided === null) {
      if (dx > DECIDE_AFTER && dx > Math.abs(dy)) {
        decided = 'back'
        begin(event.pointerId)
      } else if (Math.abs(dx) > DECIDE_AFTER || Math.abs(dy) > DECIDE_AFTER) {
        decided = 'other'
      }
    }
    if (decided !== 'back') return
    const elapsed = event.timeStamp - last.time
    if (elapsed > 0) speed = 0.7 * ((event.clientX - last.x) / elapsed) + 0.3 * speed
    last = { x: event.clientX, time: event.timeStamp }
    place(Math.max(0, dx) / width)
  }

  function release(cancelled: boolean) {
    pointerId = null
    if (decided !== 'back') return
    const share = Math.max(0, last.x - start.x) / width
    const back = !cancelled && (share > COMMIT_SHARE || speed > COMMIT_SPEED)
    place(back ? 1 : 0, true)
    settling = window.setTimeout(async () => {
      if (!back) {
        // Forward again, to the page kept alive; the copy stays over it until it is there.
        router.forward()
        await new Promise<void>((resolve) => {
          const stop = router.afterEach((to) => {
            if (to.fullPath !== returnTo) return
            stop()
            resolve()
          })
          if (router.currentRoute.value.fullPath === returnTo) {
            stop()
            resolve()
          }
        })
        await nextTick()
      }
      end()
    }, SETTLE_MS)
  }

  onBeforeUnmount(() => {
    window.clearTimeout(settling)
    cover?.remove()
  })

  return {
    kept,
    swiping,
    handlers: {
      pointerdown: onPointerDown,
      pointermove: onPointerMove,
      pointerup: (event: PointerEvent) => event.pointerId === pointerId && release(false),
      pointercancel: (event: PointerEvent) => event.pointerId === pointerId && release(true),
    },
  }
}
