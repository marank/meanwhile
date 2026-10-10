import { afterEach, describe, expect, it } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import AppSelect from '../AppSelect.vue'

const options = [
  { value: 'jan', label: 'January' },
  { value: 'feb', label: 'February' },
  { value: 'mar', label: 'March' },
  { value: 'may', label: 'May' },
]

let wrapper: VueWrapper

function render(props: Record<string, unknown> = {}) {
  wrapper = mount(AppSelect, {
    props: { modelValue: 'feb', options, label: 'Month', ...props },
    attachTo: document.body,
  })
  return wrapper.get('[role="combobox"]')
}

// The list is teleported to <body>.
function optionTexts(): string[] {
  return [...document.querySelectorAll('[role="option"]')].map((option) => option.textContent!.trim())
}

afterEach(() => wrapper?.unmount())

describe('AppSelect', () => {
  it('shows the selected label, or the placeholder without a match', () => {
    expect(render().text()).toBe('February')
    wrapper.unmount()
    expect(render({ modelValue: null, placeholder: 'Pick one' }).text()).toBe('Pick one')
  })

  it('opens on click and chooses an option with the mouse', async () => {
    const field = render()
    await field.trigger('click')
    expect(field.attributes('aria-expanded')).toBe('true')
    expect(optionTexts()).toEqual(['January', 'February', 'March', 'May'])
    ;(document.querySelectorAll('[role="option"]')[2] as HTMLElement).click()
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('update:modelValue')).toEqual([['mar']])
    expect(field.attributes('aria-expanded')).toBe('false')
  })

  it('moves with the arrow, Home and End keys and chooses with Enter', async () => {
    const field = render()
    await field.trigger('keydown', { key: 'ArrowDown' }) // opens on the selected option
    expect(field.attributes('aria-activedescendant')).toMatch(/feb$/)
    await field.trigger('keydown', { key: 'ArrowDown' })
    await field.trigger('keydown', { key: 'End' })
    await field.trigger('keydown', { key: 'ArrowDown' }) // stays on the last one
    expect(field.attributes('aria-activedescendant')).toMatch(/may$/)
    await field.trigger('keydown', { key: 'Home' })
    await field.trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('update:modelValue')).toEqual([['jan']])
  })

  it('changes a closed field right away when typing, like a native select', async () => {
    const field = render()
    await field.trigger('keydown', { key: 'm' })
    await field.trigger('keydown', { key: 'a' })
    await field.trigger('keydown', { key: 'y' })
    // "m" and "ma" both name March, "may" names May.
    expect(wrapper.emitted('update:modelValue')).toEqual([['mar'], ['may']])
    expect(field.attributes('aria-expanded')).toBe('false')
  })

  it('handles Escape itself, so a surrounding dialog stays open', async () => {
    const field = render()
    await field.trigger('click')
    const event = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })
    field.element.dispatchEvent(event)
    expect(event.defaultPrevented).toBe(true)
    await wrapper.vm.$nextTick()
    expect(field.attributes('aria-expanded')).toBe('false')
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })

  it('closes on Escape anywhere before a dialog does, even without focus', async () => {
    const field = render()
    await field.trigger('click')
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', cancelable: true }))
    await wrapper.vm.$nextTick()
    expect(field.attributes('aria-expanded')).toBe('false')
  })

  it('does nothing while disabled', async () => {
    const field = render({ disabled: true })
    await field.trigger('click')
    await field.trigger('keydown', { key: 'ArrowDown' })
    expect(field.attributes('aria-expanded')).toBe('false')
  })
})
