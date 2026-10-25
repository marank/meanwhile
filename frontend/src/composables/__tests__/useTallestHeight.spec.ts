import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h, nextTick, ref } from 'vue'
import { useTallestHeight } from '../useTallestHeight'

/** An element of the given height, in a scrolling container showing `visible` pixels of `content`. */
function setup(scroller?: { visible: number; content: number }) {
  const tab = ref('a')
  const height = ref(100)
  let result!: ReturnType<typeof useTallestHeight>
  const wrapper = mount(
    defineComponent({
      setup() {
        result = useTallestHeight(tab)
        return () =>
          h('div', { class: scroller ? 'overflow-y-auto' : '' }, [
            h('div', { ref: (el) => (result.el.value = el as HTMLElement) }),
          ])
      },
    }),
  )
  const el = result.el.value!
  Object.defineProperty(el, 'offsetHeight', { get: () => height.value })
  if (scroller) {
    const container = wrapper.element as HTMLElement
    Object.defineProperty(container, 'clientHeight', { value: scroller.visible })
    Object.defineProperty(container, 'scrollHeight', { get: () => scroller.content + height.value })
  }
  return { tab, height, minHeight: result.minHeight }
}

describe('useTallestHeight', () => {
  it('keeps the height of the tallest content shown', async () => {
    const { tab, height, minHeight } = setup()
    tab.value = 'b'
    await nextTick()
    expect(minHeight.value).toBe(100)
    height.value = 300
    tab.value = 'c'
    await nextTick()
    height.value = 50
    tab.value = 'a'
    await nextTick()
    expect(minHeight.value).toBe(300)
  })

  it('grows no taller than fits into its scrolling container', async () => {
    // 40 pixels below the element; 240 fit.
    const { tab, height, minHeight } = setup({ visible: 280, content: 40 })
    height.value = 500
    tab.value = 'b'
    await nextTick()
    expect(minHeight.value).toBe(240)
  })
})
