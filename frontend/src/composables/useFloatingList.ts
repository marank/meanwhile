import { nextTick, ref, type Ref } from 'vue'

const GAP = 4

/**
 * Places a dropdown list (position: fixed, in viewport coordinates) at its field: below it, or above it
 * where it doesn't fit below but does better there, and kept inside the viewport.
 */
export function useFloatingList(
  field: Ref<HTMLElement | null>,
  list: Ref<HTMLElement | null>,
  options: {
    /** 'min': at least as wide as the field (and wider for long options); 'exact': as wide as the field. */
    width: 'min' | 'exact'
    /** Which edge of the field the list lines up with. */
    align?: () => 'start' | 'end'
  },
) {
  const style = ref<Record<string, string>>({})

  /** `extra` styles are kept along, e.g. variables the list takes from its field. */
  async function place(extra: Record<string, string> = {}) {
    const anchor = field.value?.getBoundingClientRect()
    if (!anchor) return
    const width = { [options.width === 'min' ? 'minWidth' : 'width']: `${anchor.width}px` }
    style.value = { ...extra, ...width, left: `${anchor.left}px`, top: `${anchor.bottom + GAP}px` }
    await nextTick()
    const box = list.value?.getBoundingClientRect()
    if (!box) return
    const below = window.innerHeight - anchor.bottom - GAP
    const top = box.height > below && anchor.top > below ? anchor.top - GAP - box.height : anchor.bottom + GAP
    const left = options.align?.() === 'end' ? anchor.right - box.width : anchor.left
    style.value = {
      ...style.value,
      left: `${Math.max(GAP, Math.min(left, window.innerWidth - box.width - GAP))}px`,
      top: `${Math.max(GAP, top)}px`,
    }
  }

  return { style, place }
}
