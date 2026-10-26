import { onBeforeUnmount, ref, type Ref } from 'vue'
import { useRouter, type RouteLocationNormalized } from 'vue-router'

export type PageTransition = 'push' | 'pop' | 'fade' | 'rise' | 'none'

interface Options {
  /** The scrolling area the pages are shown in (App.vue's <main>). */
  scroller: Ref<HTMLElement | null>
  isPhone: () => boolean
  reducedMotion: () => boolean
  /** While a swipe moves the pages itself, they change without a transition. */
  swiping: () => boolean
}

/**
 * Which transition a change of page gets, from the pages' layers (route meta `layer`): on phones a page
 * one layer up slides in over the one below ("push"), going back slides it out again ("pop"), pages on
 * the same layer cross-fade. On larger screens a page fades in, rising a little. Pages without a layer
 * (signing in and out, links from emails) change at once, as does everything with reduced motion.
 *
 * Both pages are shown while they change; the one leaving is taken out of the flow where it is on the
 * screen, and the new one starts at the top.
 */
export function usePageTransition(options: Options) {
  const name = ref<PageTransition>('none')

  function choose(to: RouteLocationNormalized, from: RouteLocationNormalized): PageTransition {
    const [above, below] = [to.meta.layer, from.meta.layer]
    if (options.swiping() || options.reducedMotion() || above === undefined || below === undefined) return 'none'
    if (!options.isPhone()) return 'rise'
    return above > below ? 'push' : above < below ? 'pop' : 'fade'
  }

  const removeHook = useRouter().afterEach((to, from) => {
    name.value = choose(to, from)
  })
  onBeforeUnmount(removeHook)

  function beforeLeave(el: Element) {
    const page = el as HTMLElement
    const scroller = options.scroller.value
    if (name.value === 'none' || !scroller) return
    const top = page.offsetTop - scroller.scrollTop
    Object.assign(page.style, {
      position: 'absolute',
      top: `${top}px`,
      left: `${page.offsetLeft}px`,
      width: `${page.offsetWidth}px`,
      height: `${page.offsetHeight}px`,
      margin: '0',
    })
    scroller.scrollTop = 0
  }

  function afterLeave(el: Element) {
    // A page kept alive comes back with the same element.
    for (const property of ['position', 'top', 'left', 'width', 'height', 'margin'])
      (el as HTMLElement).style.removeProperty(property)
  }

  return { name, beforeLeave, afterLeave }
}
