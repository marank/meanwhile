import { ref, watch, type WatchSource } from 'vue'

/**
 * Keeps an element (`el`) as tall as the tallest content it has shown, measured before each change of
 * `trigger`, so it doesn't jump while switching e.g. between tabs of different height. At most as tall as
 * fits into the scrolling container without scrolling, though (phones), so short content doesn't scroll
 * into emptiness.
 */
export function useTallestHeight(trigger: WatchSource) {
  const el = ref<HTMLElement | null>(null)
  const minHeight = ref(0)
  watch(
    trigger,
    () => {
      const element = el.value
      if (!element) return
      const scroller = element.closest<HTMLElement>('.overflow-y-auto')
      let fits = Infinity
      if (scroller) {
        // What the scrolling body shows besides the element: what is above it, and below it.
        const top = element.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop
        const below = scroller.scrollHeight - top - element.offsetHeight
        fits = scroller.clientHeight - top - below
      }
      minHeight.value = Math.min(Math.max(minHeight.value, element.offsetHeight), fits)
    },
    { flush: 'pre' },
  )
  return { el, minHeight }
}
