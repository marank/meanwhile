import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { i18n } from '@/i18n'
import CalendarToolbar from '../calendar/CalendarToolbar.vue'

function render(date: Date, view: 'dayGridMonth' | 'timeGridWeek' = 'dayGridMonth') {
  i18n.global.locale.value = 'en'
  return mount(CalendarToolbar, {
    props: { title: 'Title', view, date, todayInRange: false },
    global: { plugins: [i18n] },
  })
}

function gotoAfter(wrapper: ReturnType<typeof render>, label: string): Date {
  wrapper.get(`button[aria-label="${label}"]`).trigger('click')
  return wrapper.emitted('goto')!.at(-1)![0] as Date
}

describe('CalendarToolbar', () => {
  it('changes the year with the double arrows, keeping month and day', () => {
    const wrapper = render(new Date(2026, 9, 1))
    expect(gotoAfter(wrapper, 'Previous year')).toEqual(new Date(2025, 9, 1))
    expect(gotoAfter(wrapper, 'Next year')).toEqual(new Date(2027, 9, 1))
  })

  it('shows the same date a year on in the week view, and never spills into the next month', () => {
    expect(gotoAfter(render(new Date(2026, 9, 12), 'timeGridWeek'), 'Next year')).toEqual(new Date(2027, 9, 12))
    expect(gotoAfter(render(new Date(2028, 1, 29), 'timeGridWeek'), 'Next year')).toEqual(new Date(2029, 1, 28))
  })

  it('still steps by month or week with the single arrows', () => {
    const wrapper = render(new Date(2026, 9, 1))
    wrapper.get('button[aria-label="Previous"]').trigger('click')
    wrapper.get('button[aria-label="Next"]').trigger('click')
    expect(wrapper.emitted('prev')).toHaveLength(1)
    expect(wrapper.emitted('next')).toHaveLength(1)
  })
})
