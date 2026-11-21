import { computed, onBeforeUnmount, ref, watch, type Ref } from 'vue'

const FADE = '1.5rem'

/**
 * Fades out the edges of a scrolling element where there is more content behind them, as a hint that it
 * scrolls. `content` is the element inside it whose size changes; it is watched along with the scroller.
 * Both may come and go (v-if).
 */
export function useScrollFade(scroller: Ref<HTMLElement | null>, axis: 'x' | 'y', content?: Ref<HTMLElement | null>) {
  const overflow = ref({ start: false, end: false })

  function update() {
    const el = scroller.value
    if (!el) return
    const [position, visible, total] =
      axis === 'x' ? [el.scrollLeft, el.clientWidth, el.scrollWidth] : [el.scrollTop, el.clientHeight, el.scrollHeight]
    overflow.value = { start: position > 1, end: position + visible < total - 1 }
  }

  const style = computed(() => {
    const { start, end } = overflow.value
    if (!start && !end) return undefined
    const direction = axis === 'x' ? 'to right' : 'to bottom'
    const mask = `linear-gradient(${direction}, ${start ? 'transparent' : 'black'}, black ${FADE}, black calc(100% - ${FADE}), ${end ? 'transparent' : 'black'})`
    return { maskImage: mask, WebkitMaskImage: mask }
  })

  const resize = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(update)

  watch(
    [scroller, () => content?.value],
    ([el, inner], previous) => {
      // On the first run there is no previous value.
      previous[0]?.removeEventListener('scroll', update)
      resize?.disconnect()
      overflow.value = { start: false, end: false }
      if (!el) return
      el.addEventListener('scroll', update, { passive: true })
      resize?.observe(el)
      if (inner) resize?.observe(inner)
      update()
    },
    { immediate: true, flush: 'post' },
  )

  onBeforeUnmount(() => {
    scroller.value?.removeEventListener('scroll', update)
    resize?.disconnect()
  })

  return { style, update }
}
