import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'
import { collapsedFolders, draggingId, dropIndicator, dropTargetFolderId } from '@/services/sidebarState'
import { useSidebarDrag, type SidebarDrop } from '../useSidebarDrag'

/**
 * A sidebar tree of fixed rectangles (jsdom has no layout), 240 px wide, rows 32 px high, 4 px apart:
 *
 *   a         0 – 32
 *   b        36 – 68
 *   folder f 72 – 104
 *     c     108 – 140   (16 px further in)
 *
 * The scrolling list is 400 px high.
 */
function rect(left: number, top: number, width: number, height: number): DOMRect {
  return { left, top, width, height, right: left + width, bottom: top + height, x: left, y: top, toJSON: () => ({}) }
}

const rects = new Map<string, DOMRect>([
  ['container', rect(0, 0, 240, 400)],
  ['root', rect(0, 0, 240, 140)],
  ['a', rect(0, 0, 240, 32)],
  ['b', rect(0, 36, 240, 32)],
  ['f', rect(0, 72, 240, 32)],
  ['f-list', rect(16, 108, 224, 32)],
  ['c', rect(16, 108, 224, 32)],
])

const Host = defineComponent({
  props: { onDrop: { type: Function, required: true }, onHold: { type: Function, required: true } },
  setup(props) {
    const container = ref<HTMLElement | null>(null)
    useSidebarDrag(
      container,
      (drop) => props.onDrop(drop),
      (item, x, y) => props.onHold(item, x, y),
    )
    const calendarRow = (id: string) =>
      h('div', { class: 'sidebar-item', 'data-type': 'calendar', 'data-id': id, 'data-rect': id }, [
        h('span', { class: 'label' }, id),
        h('button', { class: 'menu' }, '…'),
      ])
    return () =>
      h('div', { ref: container, 'data-rect': 'container' }, [
        h('div', { class: 'sidebar-list', 'data-rect': 'root' }, [
          calendarRow('a'),
          calendarRow('b'),
          h('div', { class: 'sidebar-item', 'data-type': 'folder', 'data-id': 'f' }, [
            h('div', { 'data-rect': 'f' }, [h('span', 'f'), h('span', { class: 'sidebar-no-drag' }, '>')]),
            h('div', { class: 'sidebar-list', 'data-folder-id': 'f', 'data-rect': 'f-list' }, [calendarRow('c')]),
          ]),
        ]),
      ])
  },
})

let onDrop: ReturnType<typeof vi.fn<(drop: SidebarDrop) => void>>
let onHold: ReturnType<typeof vi.fn>

function render() {
  onDrop = vi.fn<(drop: SidebarDrop) => void>()
  onHold = vi.fn()
  return mount(Host, { props: { onDrop, onHold }, attachTo: document.body })
}

function pointer(type: string, x: number, y: number, init: PointerEventInit = {}) {
  return new PointerEvent(type, {
    bubbles: true,
    cancelable: true,
    button: 0,
    isPrimary: true,
    pointerId: 1,
    pointerType: 'mouse',
    clientX: x,
    clientY: y,
    ...init,
  })
}

/** Presses on an element and moves to (x, y) on the document, as a mouse would. */
function press(target: Element, x: number, y: number, init: PointerEventInit = {}) {
  target.dispatchEvent(pointer('pointerdown', x, y, init))
}

function move(x: number, y: number, init: PointerEventInit = {}) {
  document.dispatchEvent(pointer('pointermove', x, y, init))
}

function release(x: number, y: number, init: PointerEventInit = {}) {
  document.dispatchEvent(pointer('pointerup', x, y, init))
}

const ghost = () => [...document.body.children].find((el) => (el as HTMLElement).style.position === 'fixed')

describe('dragging in the sidebar tree', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function (this: Element) {
      return rects.get((this as HTMLElement).dataset?.rect ?? '') ?? rect(0, 0, 0, 0)
    })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
    collapsedFolders.clear()
    document.body.innerHTML = ''
  })

  const el = (wrapper: ReturnType<typeof render>, id: string) => wrapper.get(`[data-id="${id}"]`).element as HTMLElement

  it('moves a calendar below another one', () => {
    const wrapper = render()
    const a = el(wrapper, 'a')
    press(a.querySelector('.label')!, 10, 10)
    move(10, 60)

    // A ghost follows the pointer, the row itself fades, and a line shows where it would go.
    expect(draggingId.value).toBe('a')
    expect(ghost()).toBeDefined()
    expect((ghost() as HTMLElement).style.top).toBe('50px')
    expect(ghost()!.hasAttribute('data-id')).toBe(false)
    expect(a.style.opacity).toBe('0.4')
    expect(document.body.style.cursor).toBe('grabbing')
    expect(dropIndicator.value).toEqual({ top: 69, left: 0, width: 240 })

    release(10, 60)
    expect(onDrop).toHaveBeenCalledWith({ type: 'calendar', id: 'a', parentId: null, anchor: { after: 'b' } })
    expect(ghost()).toBeUndefined()
    expect(a.style.opacity).toBe('')
    expect(draggingId.value).toBeNull()
    expect(dropIndicator.value).toBeNull()
    expect(document.body.style.cursor).toBe('')
  })

  it('keeps the click that ends a drag from opening the row', () => {
    const wrapper = render()
    const clicked = vi.fn()
    el(wrapper, 'b').addEventListener('click', clicked)
    press(el(wrapper, 'a'), 10, 10)
    move(10, 40)
    release(10, 40)
    el(wrapper, 'b').click()
    expect(clicked).not.toHaveBeenCalled()

    vi.runAllTimers()
    el(wrapper, 'b').click()
    expect(clicked).toHaveBeenCalledTimes(1)
  })

  it('treats a press without moving far as a click', () => {
    const wrapper = render()
    const clicked = vi.fn()
    el(wrapper, 'a').addEventListener('click', clicked)
    press(el(wrapper, 'a'), 10, 10)
    move(12, 12)
    release(12, 12)
    el(wrapper, 'a').click()
    expect(draggingId.value).toBeNull()
    expect(onDrop).not.toHaveBeenCalled()
    expect(clicked).toHaveBeenCalled()
  })

  it('drops into the middle of a folder, opening it when it rests on a closed one', () => {
    const wrapper = render()
    collapsedFolders.add('f')
    press(el(wrapper, 'a'), 10, 10)
    move(10, 88)
    expect(dropTargetFolderId.value).toBe('f')
    expect(dropIndicator.value).toBeNull()

    vi.advanceTimersByTime(700)
    expect(collapsedFolders.has('f')).toBe(false)

    release(10, 88)
    expect(onDrop).toHaveBeenCalledWith({ type: 'calendar', id: 'a', parentId: 'f', anchor: 'end' })
    expect(dropTargetFolderId.value).toBeNull()
  })

  it('drags a folder by its row, but not by the space of its list', () => {
    const wrapper = render()
    const folder = el(wrapper, 'f')
    folder.querySelector('[data-folder-id]')!.dispatchEvent(pointer('pointerdown', 100, 120))
    move(100, 10)
    expect(draggingId.value).toBeNull()
    release(100, 10)

    press(folder.firstElementChild!.firstElementChild!, 100, 80)
    move(100, 5)
    expect(draggingId.value).toBe('f')
    expect((folder.firstElementChild as HTMLElement).style.opacity).toBe('0.4')
    release(100, 5)
    expect(onDrop).toHaveBeenCalledWith({ type: 'folder', id: 'f', parentId: null, anchor: { before: 'a' } })
    expect((folder.firstElementChild as HTMLElement).style.opacity).toBe('')
  })

  it('ignores presses on buttons, on parts that are not to be dragged, and with other buttons', () => {
    const wrapper = render()
    press(el(wrapper, 'a').querySelector('button')!, 10, 10)
    move(10, 60)
    expect(draggingId.value).toBeNull()
    release(10, 60)

    press(el(wrapper, 'f').querySelector('.sidebar-no-drag')!, 200, 80)
    move(200, 10)
    expect(draggingId.value).toBeNull()
    release(200, 10)

    press(el(wrapper, 'a'), 10, 10, { button: 2 })
    move(10, 60)
    expect(draggingId.value).toBeNull()

    press(wrapper.get('[data-rect="root"]').element, 10, 10)
    move(10, 60)
    expect(draggingId.value).toBeNull()
  })

  it('drops nothing when released outside the list or on the dragged item itself', () => {
    const wrapper = render()
    press(el(wrapper, 'a'), 10, 10)
    move(10, 60)
    move(500, 60)
    expect(dropIndicator.value).toBeNull()
    release(500, 60)
    expect(onDrop).not.toHaveBeenCalled()

    press(el(wrapper, 'b'), 10, 40)
    move(10, 10)
    move(10, 50)
    release(10, 50)
    expect(onDrop).not.toHaveBeenCalled()
  })

  it('follows only the pointer that started the drag', () => {
    const wrapper = render()
    press(el(wrapper, 'a'), 10, 10)
    move(10, 60, { pointerId: 2 })
    expect(draggingId.value).toBeNull()
    move(10, 60)
    release(10, 60, { pointerId: 2 })
    document.dispatchEvent(pointer('pointercancel', 10, 60, { pointerId: 2 }))
    expect(draggingId.value).toBe('a')
    // A second press while dragging starts nothing.
    press(el(wrapper, 'b'), 10, 40)
    expect(draggingId.value).toBe('a')
    release(10, 60)
    expect(onDrop).toHaveBeenCalledTimes(1)
  })

  it('is cancelled by Escape, a cancelled pointer, the window losing focus or a context menu', () => {
    const wrapper = render()
    const cancellations = [
      () => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', cancelable: true })),
      () => document.dispatchEvent(pointer('pointercancel', 10, 60)),
      () => window.dispatchEvent(new Event('blur')),
      () => document.dispatchEvent(new Event('visibilitychange')),
      () => document.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true })),
    ]
    for (const cancel of cancellations) {
      press(el(wrapper, 'a'), 10, 10)
      move(10, 60)
      // Other keys don't end it.
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Shift' }))
      expect(draggingId.value).toBe('a')
      cancel()
      expect(draggingId.value).toBeNull()
      expect(ghost()).toBeUndefined()
      release(10, 60)
    }
    expect(onDrop).not.toHaveBeenCalled()
  })

  it('starts a touch drag after a long press, and keeps the page from scrolling meanwhile', () => {
    const wrapper = render()
    press(el(wrapper, 'a'), 10, 10, { pointerType: 'touch' })
    move(11, 11, { pointerType: 'touch' })
    expect(draggingId.value).toBeNull()
    vi.advanceTimersByTime(350)
    expect(draggingId.value).toBe('a')

    const touch = new Event('touchmove', { cancelable: true })
    document.dispatchEvent(touch)
    expect(touch.defaultPrevented).toBe(true)

    move(10, 60, { pointerType: 'touch' })
    release(10, 60, { pointerType: 'touch' })
    expect(onDrop).toHaveBeenCalledWith({ type: 'calendar', id: 'a', parentId: null, anchor: { after: 'b' } })
  })

  it('hands over a row held and let go without moving, for its menu, and swallows the click after it', () => {
    const wrapper = render()
    const row = el(wrapper, 'a')
    press(row, 10, 10, { pointerType: 'touch' })
    vi.advanceTimersByTime(350)
    // Lifted, as for a drag; a finger wobbles a little.
    expect(draggingId.value).toBe('a')
    move(13, 12, { pointerType: 'touch' })
    release(13, 12, { pointerType: 'touch' })
    expect(onHold).toHaveBeenCalledWith({ type: 'calendar', id: 'a' }, 13, 12)
    expect(onDrop).not.toHaveBeenCalled()
    expect(draggingId.value).toBeNull()

    const click = vi.fn()
    row.addEventListener('click', click)
    row.click()
    expect(click).not.toHaveBeenCalled()
  })

  it('drags a held row once it moves, without handing it over', () => {
    const wrapper = render()
    press(el(wrapper, 'a'), 10, 10, { pointerType: 'touch' })
    vi.advanceTimersByTime(350)
    move(10, 60, { pointerType: 'touch' })
    move(10, 12, { pointerType: 'touch' })
    release(10, 12, { pointerType: 'touch' })
    expect(onHold).not.toHaveBeenCalled()
  })

  it('hands over nothing for a mouse, which has a right click', () => {
    const wrapper = render()
    press(el(wrapper, 'a'), 10, 10)
    vi.advanceTimersByTime(1000)
    release(10, 10)
    expect(onHold).not.toHaveBeenCalled()
  })

  it('lets a touch that moves before the long press scroll the list', () => {
    const wrapper = render()
    press(el(wrapper, 'a'), 10, 10, { pointerType: 'touch' })
    move(10, 40, { pointerType: 'touch' })
    vi.advanceTimersByTime(350)
    expect(draggingId.value).toBeNull()
    const touch = new Event('touchmove', { cancelable: true })
    document.dispatchEvent(touch)
    expect(touch.defaultPrevented).toBe(false)
  })

  it('scrolls the list while the pointer is near its bottom or top edge', () => {
    const wrapper = render()
    const container = wrapper.element as HTMLElement
    let scrollTop = 0
    Object.defineProperty(container, 'scrollTop', {
      configurable: true,
      get: () => scrollTop,
      set: (value: number) => {
        scrollTop = Math.max(0, value)
      },
    })
    press(el(wrapper, 'a'), 10, 10)
    move(10, 390)
    vi.advanceTimersByTime(50)
    expect(scrollTop).toBeGreaterThan(0)

    const reached = scrollTop
    move(10, 5)
    vi.advanceTimersByTime(500)
    expect(scrollTop).toBeLessThan(reached)

    // Scrolling by wheel looks for the target again.
    move(10, 40)
    container.dispatchEvent(new Event('scroll'))
    release(10, 40)
    expect(onDrop).toHaveBeenCalledWith({ type: 'calendar', id: 'a', parentId: null, anchor: { before: 'b' } })
  })

  it('stops listening when the sidebar goes away', () => {
    const wrapper = render()
    const a = el(wrapper, 'a')
    press(a, 10, 10)
    move(10, 60)
    wrapper.unmount()
    expect(draggingId.value).toBeNull()
    expect(ghost()).toBeUndefined()

    document.body.append(a)
    press(a, 10, 10)
    move(10, 60)
    expect(draggingId.value).toBeNull()
  })
})
