import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue'

/** How far (px) a finger moves before the swipe decides between sideways (tabs) and up and down (scroll). */
const DECIDE_AFTER = 10
/** Let go past this share of the width, or flicked faster than this (px/ms), the swipe goes to the next tab. */
const COMMIT_SHARE = 0.35
const COMMIT_SPEED = 0.4
/** Past the first and the last tab, the content follows the finger only this much, as if on a rubber band. */
const RUBBER_BAND = 0.3
/** How long sliding over one whole tab takes (ms). */
const SLIDE_MS = 280

interface Options<T extends string> {
  tabs: () => readonly T[]
  active: () => T | undefined
  select: (id: T) => void
  /** Phones only; elsewhere tabs switch at once. */
  enabled: () => boolean
  /** Off for reduced motion: tabs switch at once, swiping still works. */
  animate: () => boolean
  width: () => number
}

/**
 * Tabs that follow the finger: swiping sideways drags the active tab's content aside and the next one in,
 * and letting go finishes the move or takes it back. A tab chosen otherwise (the tab bar, the keyboard, the
 * URL) slides in too, from the side it lies on. `panes` says which tabs to show and how far to shift each
 * (in widths), `position` where between the tabs things are (e.g. 1.4), for the tab bar.
 */
export function useTabSwipe<T extends string>(options: Options<T>) {
  // At rest only `base` is shown. While moving, `target` comes in as `progress` goes from 0 to 1.
  const base = shallowRef(options.active())
  const target = shallowRef<T | null>(null)
  const progress = ref(0)
  // Past the first or last tab: how far (px) the content is pulled aside.
  const pull = ref(0)
  const dragging = ref(false)
  const animating = ref(false)

  const index = (id: T | null | undefined) => (id ? options.tabs().indexOf(id) : -1)
  const direction = () => Math.sign(index(target.value) - index(base.value))

  const panes = computed(() => {
    if (base.value === undefined) return []
    if (target.value === null) {
      const width = options.width()
      return [{ id: base.value, shift: width ? pull.value / width : 0 }]
    }
    const dir = direction()
    return [
      { id: base.value, shift: -dir * progress.value },
      { id: target.value, shift: dir * (1 - progress.value) },
    ]
  })

  const position = computed(() => {
    const from = index(base.value)
    if (target.value === null) return from
    return from + (index(target.value) - from) * progress.value
  })

  const moving = computed(() => dragging.value || animating.value)

  let frame = 0
  function stopAnimation() {
    cancelAnimationFrame(frame)
    animating.value = false
  }

  /** Eases `set` from `from` to `to`, then calls `done`. */
  function tween(from: number, to: number, share: number, set: (value: number) => void, done: () => void) {
    stopAnimation()
    if (!options.animate() || from === to) {
      set(to)
      done()
      return
    }
    animating.value = true
    const duration = Math.max(120, SLIDE_MS * share)
    const start = performance.now()
    const step = (now: number) => {
      const linear = Math.min(1, (now - start) / duration)
      const eased = 1 - (1 - linear) ** 3
      set(from + (to - from) * eased)
      if (linear < 1) {
        frame = requestAnimationFrame(step)
      } else {
        animating.value = false
        done()
      }
    }
    frame = requestAnimationFrame(step)
  }

  function settle() {
    if (target.value !== null) base.value = target.value
    target.value = null
    progress.value = 0
    pull.value = 0
  }

  function finish() {
    tween(progress.value, 1, 1 - progress.value, (value) => (progress.value = value), settle)
  }

  function takeBack() {
    if (target.value !== null) {
      tween(
        progress.value,
        0,
        progress.value,
        (value) => (progress.value = value),
        () => (target.value = null),
      )
    } else {
      tween(pull.value, 0, 0.5, (value) => (pull.value = value), settle)
    }
  }

  // A tab chosen otherwise slides in. One the swipe chose itself (the target) is already on its way.
  watch(options.active, (active) => {
    if (active === target.value) return
    stopAnimation()
    settle()
    if (!options.enabled() || active === undefined || base.value === undefined || active === base.value) {
      base.value = active
      return
    }
    target.value = active
    finish()
  })

  // The swipe itself.
  let start = { x: 0, y: 0 }
  let last = { x: 0, time: 0 }
  let speed = 0
  let decided: 'sideways' | 'scroll' | null = null
  let pointerId: number | null = null

  function onPointerDown(event: PointerEvent) {
    if (event.pointerType !== 'touch' || !options.enabled() || options.tabs().length < 2) return
    if (moving.value || base.value === undefined) return
    pointerId = event.pointerId
    decided = null
    start = { x: event.clientX, y: event.clientY }
    last = { x: event.clientX, time: event.timeStamp }
    speed = 0
  }

  function onPointerMove(event: PointerEvent) {
    if (event.pointerId !== pointerId) return
    const dx = event.clientX - start.x
    const dy = event.clientY - start.y
    if (decided === null) {
      if (Math.abs(dx) > DECIDE_AFTER && Math.abs(dx) > Math.abs(dy) * 1.2) {
        decided = 'sideways'
        dragging.value = true
        ;(event.currentTarget as Element | null)?.setPointerCapture?.(event.pointerId)
      } else if (Math.abs(dy) > DECIDE_AFTER) {
        decided = 'scroll'
      }
    }
    if (decided !== 'sideways') return

    const elapsed = event.timeStamp - last.time
    if (elapsed > 0) speed = 0.7 * ((event.clientX - last.x) / elapsed) + 0.3 * speed
    last = { x: event.clientX, time: event.timeStamp }

    const tabs = options.tabs()
    // Dragged left, the next tab comes in from the right; dragged right, the one before from the left.
    const neighbour = tabs[index(base.value) + (dx < 0 ? 1 : -1)]
    const width = options.width() || 1
    if (dx !== 0 && neighbour !== undefined) {
      target.value = neighbour
      progress.value = Math.min(1, Math.abs(dx) / width)
      pull.value = 0
    } else {
      target.value = null
      progress.value = 0
      pull.value = dx * RUBBER_BAND
    }
  }

  function onPointerUp(event: PointerEvent) {
    if (event.pointerId !== pointerId) return
    pointerId = null
    if (decided !== 'sideways') return
    dragging.value = false
    const flicked = Math.abs(speed) > COMMIT_SPEED && Math.sign(speed) === -direction()
    if (target.value !== null && (progress.value > COMMIT_SHARE || flicked)) {
      options.select(target.value)
      finish()
    } else {
      takeBack()
    }
  }

  function onPointerCancel(event: PointerEvent) {
    if (event.pointerId !== pointerId) return
    pointerId = null
    if (decided !== 'sideways') return
    dragging.value = false
    takeBack()
  }

  onBeforeUnmount(() => cancelAnimationFrame(frame))

  return {
    panes,
    position,
    moving,
    handlers: {
      pointerdown: onPointerDown,
      pointermove: onPointerMove,
      pointerup: onPointerUp,
      pointercancel: onPointerCancel,
    },
  }
}
