import { afterEach, describe, expect, it } from 'vitest'
import { mount, type DOMWrapper, type VueWrapper } from '@vue/test-utils'
import YearPicker from '../calendar/YearPicker.vue'

let wrapper: VueWrapper

function render(year = 2026) {
  wrapper = mount(YearPicker, { props: { modelValue: year, label: 'Year' }, attachTo: document.body })
  return wrapper.get('[role="combobox"]')
}

// The list is teleported to <body>.
function renderedYears(): number[] {
  return [...document.querySelectorAll('[role="option"]')].map((option) => Number(option.textContent))
}

function listbox(): HTMLElement {
  return document.querySelector('[role="listbox"]') as HTMLElement
}

async function typeDigits(field: Pick<DOMWrapper<Element>, 'trigger'>, digits: string) {
  for (const key of digits) await field.trigger('keydown', { key })
}

afterEach(() => wrapper.unmount())

describe('YearPicker', () => {
  it('is a button, not a text field', () => {
    const field = render()
    expect(field.element.tagName).toBe('BUTTON')
    expect(field.text()).toBe('2026')
  })

  it('opens on click with the selected year among only a few rendered rows', async () => {
    const field = render()
    await field.trigger('click')
    expect(field.attributes('aria-expanded')).toBe('true')
    expect(renderedYears()).toContain(2026)
    expect(renderedYears().length).toBeLessThan(20)
  })

  it('shows typed digits, jumps to the year and takes it with Enter', async () => {
    const field = render()
    await typeDigits(field, '203')
    expect(field.text()).toBe('203')
    await field.trigger('keydown', { key: 'Backspace' })
    await typeDigits(field, '31')
    expect(field.text()).toBe('2031')
    expect(field.attributes('aria-activedescendant')).toMatch(/-2031$/)
    await field.trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('update:modelValue')).toEqual([[2031]])
    expect(field.attributes('aria-expanded')).toBe('false')
  })

  it('ignores letters and takes a typed year when leaving the field, but drops partial input', async () => {
    const field = render()
    await typeDigits(field, '1x9')
    expect(field.text()).toBe('19')
    await field.trigger('blur')
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    expect(field.text()).toBe('2026')
    await typeDigits(field, '1999')
    await field.trigger('blur')
    expect(wrapper.emitted('update:modelValue')).toEqual([[1999]])
  })

  it('steps through years with the arrow and page keys', async () => {
    const field = render()
    await field.trigger('keydown', { key: 'ArrowDown' }) // opens
    await field.trigger('keydown', { key: 'ArrowDown' })
    await field.trigger('keydown', { key: 'PageUp' })
    expect(field.attributes('aria-activedescendant')).toMatch(/-2017$/)
    await field.trigger('keydown', { key: 'Escape' })
    expect(field.attributes('aria-expanded')).toBe('false')
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })

  it('generates earlier years when scrolling towards the top, keeping the view in place', async () => {
    const field = render()
    await field.trigger('click')
    const list = listbox()
    // The window starts 100 years before 2026; scrolled to its 5th row, 1931 is at the top.
    list.scrollTop = 5 * 32
    list.dispatchEvent(new Event('scroll'))
    await wrapper.vm.$nextTick()
    // 50 years were generated above, so the same years are now 50 rows further down …
    expect(list.scrollTop).toBe(55 * 32)
    expect(renderedYears()).toContain(1931)
    // … and scrolling up keeps going past the old start of the window.
    list.scrollTop = 0
    list.dispatchEvent(new Event('scroll'))
    await wrapper.vm.$nextTick()
    expect(Math.min(...renderedYears())).toBeLessThan(1926 - 50)
  })
})
