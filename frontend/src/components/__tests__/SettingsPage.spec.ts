import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { h } from 'vue'
import { i18n } from '@/i18n'
import SettingsPage from '../SettingsPage.vue'
import { stubMatchMedia } from '../calendar/__tests__/calendarFixtures'

const PHONE = '(width < 40rem)'
const REDUCED_MOTION = '(prefers-reduced-motion: reduce)'
const WIDTH = 300

const tabs = [
  { id: 'one', label: 'One' },
  { id: 'two', label: 'Two' },
  { id: 'three', label: 'Three' },
]

/** The settings page with a paragraph per tab; choosing a tab makes it the active one, as the views do. */
function open(activeTab = 'one', attachTo: Element = document.body) {
  const wrapper = mount(SettingsPage, {
    props: { title: 'Settings', tabs, activeTab, onSelectTab: (id: string) => wrapper.setProps({ activeTab: id }) },
    slots: { default: ({ tab }: { tab: string | undefined }) => h('p', `content ${tab}`) },
    global: { plugins: [i18n] },
    attachTo,
  })
  return wrapper
}

/**
 * Opens the page in a scrolling container, scrolled to `scrollTop`: the tabs' content starts 200px down the
 * page, below a 40px tab bar. jsdom doesn't lay out, so those sizes are made up.
 */
function openScrolled(scrollTop: number) {
  const scroller = document.body.appendChild(document.createElement('div'))
  scroller.style.overflowY = 'auto'
  vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockReturnValue(600)
  vi.spyOn(HTMLElement.prototype, 'offsetHeight', 'get').mockImplementation(function (this: HTMLElement) {
    return this.tagName === 'NAV' ? 40 : 0
  })
  vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function (this: Element) {
    const top = this.parentElement?.hasAttribute('data-tab-panels') ? 200 - scroller.scrollTop : 0
    return { top } as DOMRect
  })
  const wrapper = open('one', scroller.appendChild(document.createElement('div')))
  scroller.scrollTop = scrollTop
  return { wrapper, scroller }
}

const shown = (wrapper: ReturnType<typeof open>) => wrapper.findAll('p').map((p) => p.text())
const selected = (wrapper: ReturnType<typeof open>) => wrapper.get('[aria-selected="true"]').text()

function pointer(type: string, x: number, y = 100) {
  return new PointerEvent(type, { bubbles: true, pointerId: 1, pointerType: 'touch', clientX: x, clientY: y })
}

/** Puts a finger down at x and moves it to each of `to` in turn, along a line or up and down. */
function swipe(wrapper: ReturnType<typeof open>, x: number, to: number[], { vertical = false } = {}) {
  const area = wrapper.get('[data-tab-panels]').element
  area.dispatchEvent(pointer('pointerdown', x))
  for (const point of to)
    area.dispatchEvent(vertical ? pointer('pointermove', x, point) : pointer('pointermove', point))
  return {
    release: () => area.dispatchEvent(pointer('pointerup', to.at(-1)!)),
  }
}

describe('SettingsPage', () => {
  let media: ReturnType<typeof stubMatchMedia>

  beforeEach(() => {
    i18n.global.locale.value = 'en'
    media = stubMatchMedia([PHONE])
    vi.useFakeTimers()
    vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(WIDTH)
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('shows only the active tab at rest', () => {
    const wrapper = open('two')
    expect(shown(wrapper)).toEqual(['content two'])
    wrapper.unmount()
  })

  it('drags the next tab in while swiping left, and moves to it when let go far enough', async () => {
    const wrapper = open()
    const finger = swipe(wrapper, 250, [230, 120])
    await wrapper.vm.$nextTick()
    // Both tabs are shown, the active one shifted aside by as far as the finger went.
    expect(shown(wrapper)).toEqual(['content one', 'content two'])
    expect(wrapper.find('[data-sliding]').exists()).toBe(true)
    expect(selected(wrapper)).toBe('One')

    finger.release()
    await wrapper.vm.$nextTick()
    expect(selected(wrapper)).toBe('Two')
    vi.advanceTimersByTime(500)
    await wrapper.vm.$nextTick()
    expect(shown(wrapper)).toEqual(['content two'])
    expect(wrapper.find('[data-sliding]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('swipes right to the tab before', async () => {
    const wrapper = open('three')
    swipe(wrapper, 50, [70, 250]).release()
    vi.advanceTimersByTime(500)
    await wrapper.vm.$nextTick()
    expect(selected(wrapper)).toBe('Two')
    expect(shown(wrapper)).toEqual(['content two'])
    wrapper.unmount()
  })

  it('takes a short swipe back', async () => {
    const wrapper = open()
    swipe(wrapper, 250, [230, 200]).release()
    vi.advanceTimersByTime(500)
    await wrapper.vm.$nextTick()
    expect(selected(wrapper)).toBe('One')
    expect(shown(wrapper)).toEqual(['content one'])
    wrapper.unmount()
  })

  it('moves on after a short but quick flick', async () => {
    const wrapper = open()
    const area = wrapper.get('[data-tab-panels]').element
    const at = (type: string, x: number, timeStamp: number) => {
      const event = pointer(type, x)
      Object.defineProperty(event, 'timeStamp', { value: timeStamp })
      area.dispatchEvent(event)
    }
    at('pointerdown', 250, 0)
    at('pointermove', 235, 10)
    at('pointermove', 200, 20)
    at('pointerup', 200, 25)
    await wrapper.vm.$nextTick()
    expect(selected(wrapper)).toBe('Two')
    wrapper.unmount()
  })

  it('takes the swipe back when the system cancels it', async () => {
    const wrapper = open()
    swipe(wrapper, 250, [230, 50])
    wrapper.get('[data-tab-panels]').element.dispatchEvent(pointer('pointercancel', 50))
    vi.advanceTimersByTime(500)
    await wrapper.vm.$nextTick()
    expect(selected(wrapper)).toBe('One')
    expect(shown(wrapper)).toEqual(['content one'])
    wrapper.unmount()
  })

  it('goes nowhere past the last tab', async () => {
    const wrapper = open('three')
    swipe(wrapper, 250, [230, 50]).release()
    vi.advanceTimersByTime(500)
    await wrapper.vm.$nextTick()
    expect(selected(wrapper)).toBe('Three')
    expect(shown(wrapper)).toEqual(['content three'])
    expect(wrapper.emitted('selectTab')).toBeUndefined()
    wrapper.unmount()
  })

  it('leaves swipes up and down to scrolling', async () => {
    const wrapper = open()
    swipe(wrapper, 150, [130, 20], { vertical: true }).release()
    await wrapper.vm.$nextTick()
    expect(shown(wrapper)).toEqual(['content one'])
    expect(wrapper.emitted('selectTab')).toBeUndefined()
    wrapper.unmount()
  })

  it('ignores the mouse', async () => {
    const wrapper = open()
    const area = wrapper.get('[data-tab-panels]').element
    for (const [type, x] of [
      ['pointerdown', 250],
      ['pointermove', 100],
      ['pointerup', 100],
    ] as const) {
      area.dispatchEvent(new PointerEvent(type, { bubbles: true, pointerId: 1, pointerType: 'mouse', clientX: x }))
    }
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('selectTab')).toBeUndefined()
    wrapper.unmount()
  })

  it('slides a tab chosen in the tab bar in from its side, the underline along', async () => {
    const wrapper = open()
    await wrapper.findAll('[role="tab"]')[2]!.trigger('click')
    expect(selected(wrapper)).toBe('Three')
    vi.advanceTimersByTime(100)
    await wrapper.vm.$nextTick()
    expect(shown(wrapper)).toEqual(['content one', 'content three'])
    expect(wrapper.find('[data-underline]').exists()).toBe(true)

    vi.advanceTimersByTime(500)
    await wrapper.vm.$nextTick()
    expect(shown(wrapper)).toEqual(['content three'])
    wrapper.unmount()
  })

  it('starts a tab chosen further down at its top, right below the bar', async () => {
    media.set(PHONE, false)
    const { wrapper, scroller } = openScrolled(500)
    await wrapper.findAll('[role="tab"]')[1]!.trigger('click')
    // 200px down the page, less the bar.
    expect(scroller.scrollTop).toBe(160)
    wrapper.unmount()
    scroller.remove()
  })

  it('leaves the scrolling alone while the content is still in view below the bar', async () => {
    media.set(PHONE, false)
    const { wrapper, scroller } = openScrolled(100)
    await wrapper.findAll('[role="tab"]')[1]!.trigger('click')
    expect(scroller.scrollTop).toBe(100)
    wrapper.unmount()
    scroller.remove()
  })

  it('swipes in the next tab from its top while scrolled down, then scrolls up to it', async () => {
    const { wrapper, scroller } = openScrolled(500)
    const finger = swipe(wrapper, 250, [230, 120])
    await wrapper.vm.$nextTick()
    // The incoming tab is lowered to where the page is scrolled; the outgoing one stays put.
    const panes = wrapper.findAll('[data-tab-panels] .grid > div')
    expect(panes[1]!.attributes('style')).toContain('340px')
    expect(panes[0]!.attributes('style')).not.toContain('340px')

    finger.release()
    vi.advanceTimersByTime(500)
    await wrapper.vm.$nextTick()
    expect(scroller.scrollTop).toBe(160)
    wrapper.unmount()
    scroller.remove()
  })

  it('switches at once with reduced motion', async () => {
    media.set(REDUCED_MOTION, true)
    const wrapper = open()
    await wrapper.findAll('[role="tab"]')[1]!.trigger('click')
    expect(shown(wrapper)).toEqual(['content two'])
    wrapper.unmount()
  })

  it('switches at once from tablets up, without swiping or a sliding underline', async () => {
    media.set(PHONE, false)
    const wrapper = open()
    expect(wrapper.find('[data-underline]').exists()).toBe(false)
    await wrapper.findAll('[role="tab"]')[1]!.trigger('click')
    expect(shown(wrapper)).toEqual(['content two'])

    swipe(wrapper, 250, [230, 50]).release()
    await wrapper.vm.$nextTick()
    expect(selected(wrapper)).toBe('Two')
    wrapper.unmount()
  })
})
