import { onBeforeUnmount, ref } from 'vue'

/** Whether a media query matches, kept current while the component lives. */
export function useMediaQuery(query: string) {
  const list = typeof window.matchMedia === 'function' ? window.matchMedia(query) : null
  const matches = ref(list?.matches ?? false)
  const update = (event: MediaQueryListEvent) => (matches.value = event.matches)
  list?.addEventListener('change', update)
  onBeforeUnmount(() => list?.removeEventListener('change', update))
  return matches
}
