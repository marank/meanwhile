import { beforeEach, describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type * as api from '@/api'
import { i18n } from '@/i18n'
import { calendarColorPalettes, paletteColors } from '@/services/calendarColors'
import { fakeBackend, reply, type FakeBackend } from '@/__tests__/fakeBackend'
import { appColors, buttonNamed, calendar, clearToasts, toastTexts } from '@/components/__tests__/settingsFixtures'
import CalendarGeneralSettings from '../CalendarGeneralSettings.vue'

let backend: FakeBackend

function render(props: { canManage?: boolean; calendar?: api.Calendar } = {}) {
  return mount(CalendarGeneralSettings, {
    props: { calendar: props.calendar ?? calendar(), canManage: props.canManage ?? true },
    global: { plugins: [i18n] },
    attachTo: document.body,
  })
}

const colorMode = (wrapper: ReturnType<typeof render>, label: 'Preset' | 'Advanced') =>
  wrapper.findAll('[role="radio"]').find((b) => b.text() === label)!

function clickOption(text: string) {
  ;[...document.querySelectorAll<HTMLElement>('[role="option"]')].find((o) => o.textContent.trim() === text)!.click()
}

describe('calendar general settings', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    i18n.global.locale.value = 'en'
    clearToasts()
    backend = fakeBackend({
      'PATCH /api/calendars/cal': (req) => calendar(req.body as Partial<api.Calendar>),
    })
  })

  it('opens a calendar with preset colors in the simple mode, showing the preset', () => {
    const wrapper = render()
    expect(colorMode(wrapper, 'Preset').attributes('aria-checked')).toBe('true')
    expect(wrapper.find('input[type="color"]').exists()).toBe(false)
    expect(wrapper.get('[role="combobox"]').text()).toBe('App theme')
    wrapper.unmount()
  })

  it('opens a calendar with its own colors in the advanced mode', () => {
    const wrapper = render({ calendar: calendar({ base_color: '#123456' }) })
    expect(colorMode(wrapper, 'Advanced').attributes('aria-checked')).toBe('true')
    expect(wrapper.findAll('input[type="color"]')).toHaveLength(12)
    expect(wrapper.get('[role="combobox"]').text()).toBe('Custom colors')
    wrapper.unmount()
  })

  it('saves only the changed settings and passes on the saved calendar', async () => {
    const wrapper = render()
    await colorMode(wrapper, 'Advanced').trigger('click')
    await wrapper.get('input[type="color"]').setValue('#abcdef')
    expect(wrapper.findAll('[role="combobox"]')[0]!.text()).toBe('Custom colors')
    await wrapper.findAll('[role="switch"]').at(-1)!.trigger('click') // only all-day events
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(backend.calls('PATCH /api/calendars/cal')[0]!.body).toEqual({ base_color: '#abcdef', force_all_day: true })
    expect(wrapper.emitted('updated')![0]![0]).toMatchObject({ base_color: '#abcdef', force_all_day: true })
    expect(toastTexts()).toEqual(['Calendar settings saved.'])
    wrapper.unmount()
  })

  it('applies a preset with all its colors', async () => {
    const wrapper = render()
    await wrapper.findAll('[role="combobox"]')[0]!.trigger('click')
    clickOption('Midnight')
    await flushPromises()
    expect(wrapper.findAll('[role="combobox"]')[0]!.text()).toBe('Midnight')
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    const midnight = paletteColors(calendarColorPalettes.find((p) => p.id === 'midnight')!)
    const changed = Object.fromEntries(
      Object.entries(midnight).filter(([key, value]) => appColors[key as keyof typeof appColors] !== value),
    )
    expect(backend.calls('PATCH /api/calendars/cal')[0]!.body).toEqual(changed)
    wrapper.unmount()
  })

  it('saves the week layout', async () => {
    const wrapper = render()
    await buttonNamed(wrapper, 'Friday').trigger('click')
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(backend.calls('PATCH /api/calendars/cal')[0]!.body).toEqual({ weekend_days: [0, 5, 6] })
    wrapper.unmount()
  })

  it('sends nothing when nothing changed', async () => {
    const wrapper = render()
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(backend.requests).toHaveLength(0)
    expect(wrapper.emitted('updated')).toBeUndefined()
    wrapper.unmount()
  })

  it('reports a failed save', async () => {
    backend.on('PATCH /api/calendars/cal', reply(500))
    const wrapper = render()
    await wrapper.findAll('[role="switch"]').at(-1)!.trigger('click')
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(toastTexts()).toEqual(['Could not save the changes.'])
    wrapper.unmount()
  })

  it('lets only managers change anything', () => {
    const wrapper = render({ canManage: false })
    expect(buttonNamed(wrapper, 'Save').attributes('disabled')).toBeDefined()
    expect(wrapper.findAll('[role="switch"]').every((s) => s.attributes('disabled') !== undefined)).toBe(true)
    wrapper.unmount()
  })
})
