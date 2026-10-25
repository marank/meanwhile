import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import ContextMenu, { type MenuItem } from '../ContextMenu.vue'

function rect(width: number, height: number): DOMRect {
  return { left: 0, top: 0, right: width, bottom: height, width, height, x: 0, y: 0, toJSON: () => ({}) }
}

describe('ContextMenu', () => {
  let opener: HTMLButtonElement
  let items: MenuItem[]

  beforeEach(() => {
    // jsdom has no layout: the menu is 100 × 80 px in a 1024 × 768 window.
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue(rect(100, 80))
    opener = document.createElement('button')
    document.body.append(opener)
    opener.focus()
    items = [
      { label: 'Rename', action: vi.fn() },
      { label: 'Delete', action: vi.fn() },
      { label: 'Settings', action: vi.fn() },
    ]
  })

  afterEach(() => {
    vi.restoreAllMocks()
    document.body.innerHTML = ''
  })

  async function render(x: number, y: number, above = false, alignEnd = false) {
    const wrapper = mount(ContextMenu, { props: { x, y, items, above, alignEnd }, attachTo: document.body })
    await nextTick()
    return wrapper
  }

  const menu = (wrapper: Awaited<ReturnType<typeof render>>) => wrapper.get<HTMLElement>('[role="menu"]')
  const buttons = (wrapper: Awaited<ReturnType<typeof render>>) => wrapper.findAll<HTMLElement>('[role="menuitem"]')

  it('opens where it was asked for, with the first entry focused', async () => {
    const wrapper = await render(200, 150)
    expect(menu(wrapper).element.style.left).toBe('200px')
    expect(menu(wrapper).element.style.top).toBe('150px')
    expect(buttons(wrapper).map((b) => b.text())).toEqual(['Rename', 'Delete', 'Settings'])
    expect(document.activeElement).toBe(buttons(wrapper)[0]!.element)
  })

  it('stays on screen near the right and bottom edges', async () => {
    const wrapper = await render(1000, 760)
    expect(menu(wrapper).element.style.left).toBe(`${1024 - 100 - 4}px`)
    expect(menu(wrapper).element.style.top).toBe(`${768 - 80 - 4}px`)
  })

  it('opens upwards from a button at the bottom', async () => {
    const wrapper = await render(10, 300, true)
    expect(menu(wrapper).element.style.top).toBe('220px')
    expect((await render(10, 20, true)).get<HTMLElement>('[role="menu"]').element.style.top).toBe('4px')
  })

  it('ends at the button it opens under, and marks destructive entries', async () => {
    items[1]!.danger = true
    const wrapper = await render(500, 20, false, true)
    expect(menu(wrapper).element.style.left).toBe('400px')
    expect(buttons(wrapper).map((b) => b.attributes('data-tone'))).toEqual([undefined, 'danger', undefined])
  })

  it('runs the chosen entry and closes, giving the focus back', async () => {
    const wrapper = await render(10, 10)
    await buttons(wrapper)[1]!.trigger('click')
    expect(items[1]!.action).toHaveBeenCalled()
    expect(items[0]!.action).not.toHaveBeenCalled()
    expect(wrapper.emitted('close')).toHaveLength(1)
    expect(document.activeElement).toBe(opener)
  })

  it('moves through its entries with the arrow keys, Home and End', async () => {
    const wrapper = await render(10, 10)
    const focused = () => buttons(wrapper).findIndex((b) => b.element === document.activeElement)
    await menu(wrapper).trigger('keydown', { key: 'ArrowDown' })
    expect(focused()).toBe(1)
    await menu(wrapper).trigger('keydown', { key: 'End' })
    expect(focused()).toBe(2)
    await menu(wrapper).trigger('keydown', { key: 'ArrowDown' })
    expect(focused()).toBe(0)
    await menu(wrapper).trigger('keydown', { key: 'ArrowUp' })
    expect(focused()).toBe(2)
    await menu(wrapper).trigger('keydown', { key: 'Home' })
    expect(focused()).toBe(0)
    await menu(wrapper).trigger('keydown', { key: 'a' })
    expect(focused()).toBe(0)
    expect(wrapper.emitted('close')).toBeUndefined()
  })

  it('closes with Tab, Escape, and a click or right click outside it', async () => {
    const wrapper = await render(10, 10)
    await menu(wrapper).trigger('keydown', { key: 'Tab' })
    expect(wrapper.emitted('close')).toHaveLength(1)

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', cancelable: true }))
    expect(wrapper.emitted('close')).toHaveLength(2)

    await menu(wrapper).trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(2)
    await wrapper.trigger('click')
    await wrapper.trigger('contextmenu')
    expect(wrapper.emitted('close')).toHaveLength(4)
    expect(items.every((item) => !vi.mocked(item.action).mock.calls.length)).toBe(true)
  })
})
