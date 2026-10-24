import { afterEach, describe, expect, it } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { defineComponent, h, nextTick, ref } from 'vue'
import { i18n } from '@/i18n'
import AppModal from '../AppModal.vue'

let wrapper: VueWrapper

/** A button that opens the dialog, and the dialog with two buttons of its own. */
function render(props: Record<string, unknown> = {}) {
  const open = ref(false)
  const Host = defineComponent(() => () => [
    h('button', { id: 'opener', onClick: () => (open.value = true) }, 'Open'),
    h(
      AppModal,
      { open: open.value, title: 'Title', ...props, onClose: () => (open.value = false) },
      { default: () => [h('button', { id: 'first' }, 'First'), h('button', { id: 'last' }, 'Last')] },
    ),
  ])
  wrapper = mount(Host, { global: { plugins: [i18n] }, attachTo: document.body })
  return { open }
}

const dialog = () => document.querySelector<HTMLElement>('[role="dialog"]')
const active = () => document.activeElement?.id

function press(key: string, init: KeyboardEventInit = {}, target: EventTarget = document.activeElement!) {
  target.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true, ...init }))
}

async function openFromButton(open: { value: boolean }) {
  document.querySelector<HTMLElement>('#opener')!.focus()
  open.value = true
  await nextTick()
  await nextTick()
}

afterEach(() => wrapper?.unmount())

describe('AppModal', () => {
  it('is labelled by its title', async () => {
    const { open } = render()
    await openFromButton(open)
    const title = document.getElementById(dialog()!.getAttribute('aria-labelledby')!)
    expect(title?.textContent).toBe('Title')
  })

  it('moves focus to its content, keeps it inside and returns it when closed', async () => {
    const { open } = render()
    await openFromButton(open)
    expect(active()).toBe('first')

    document.querySelector<HTMLElement>('#last')!.focus()
    press('Tab')
    // Wraps around to the close button in the header, the first one in the dialog.
    expect(document.activeElement?.getAttribute('aria-label')).toBeTruthy()
    press('Tab', { shiftKey: true })
    expect(active()).toBe('last')

    open.value = false
    await nextTick()
    expect(active()).toBe('opener')
  })

  it('closes on Escape only when dismissible', async () => {
    const { open } = render({ dismissible: false })
    await openFromButton(open)
    press('Escape', {}, window)
    await nextTick()
    expect(open.value).toBe(true)

    wrapper.unmount()
    const dismissible = render()
    await openFromButton(dismissible.open)
    press('Escape', {}, window)
    await nextTick()
    expect(dismissible.open.value).toBe(false)
  })
})
