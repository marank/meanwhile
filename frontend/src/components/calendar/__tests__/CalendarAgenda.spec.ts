import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import type { Occurrence } from '@/api'
import { i18n } from '@/i18n'
import { formatTime } from '@/services/datetime'
import CalendarAgenda from '../CalendarAgenda.vue'
import { allDay, at, occurrence } from './calendarFixtures'

const OCTOBER = new Date(2026, 9, 1)
const NOVEMBER = new Date(2026, 10, 1)

function render(occurrences: Occurrence[], props: Record<string, unknown> = {}) {
  return mount(CalendarAgenda, {
    props: {
      occurrences,
      rangeStart: OCTOBER,
      rangeEnd: NOVEMBER,
      colorOf: () => '#123456',
      calendarNameOf: null,
      canCreate: true,
      ...props,
    },
    global: { plugins: [i18n] },
    attachTo: document.body,
  })
}

function titles(wrapper: ReturnType<typeof render>) {
  return wrapper.findAll('.agenda-title').map((title) => title.text())
}

describe('CalendarAgenda', () => {
  let scrollTo: ReturnType<typeof vi.fn>

  beforeEach(() => {
    setActivePinia(createPinia())
    i18n.global.locale.value = 'en'
    // Noon on Wednesday, 14 October 2026.
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(2026, 9, 14, 12))
    scrollTo = vi.fn()
    Element.prototype.scrollTo = scrollTo as unknown as typeof Element.prototype.scrollTo
  })

  afterEach(() => {
    vi.useRealTimers()
    delete (Element.prototype as Partial<Element>).scrollTo
    document.body.innerHTML = ''
  })

  it('lists the events of the month by day, with their times and how many there are', () => {
    const wrapper = render([
      occurrence({ event_id: 'a', title: 'Standup', start: at(2026, 10, 14, 9), end: at(2026, 10, 14, 9, 30) }),
      occurrence({ event_id: 'b', title: 'Review', start: at(2026, 10, 20, 15), end: at(2026, 10, 20, 16) }),
      occurrence({ event_id: 'c', title: 'Point', start: at(2026, 10, 21, 8), end: at(2026, 10, 21, 8) }),
    ])
    expect(wrapper.text()).toContain('3 events')
    const days = wrapper.findAll('.agenda-day')
    expect(days.map((day) => day.find('.agenda-daynumber').text())).toEqual(['14', '20', '21'])
    expect(days[0]!.find('.agenda-weekday').text()).toBe('Wed')
    expect(days[0]!.classes()).toContain('agenda-day-today')
    expect(days[1]!.find('.agenda-time').text()).toContain(formatTime(at(2026, 10, 20, 15)))
    expect(days[1]!.find('.agenda-time-sub').text()).toBe(formatTime(at(2026, 10, 20, 16)))
    // An event without a duration shows its time only once.
    expect(days[2]!.find('.agenda-time-sub').exists()).toBe(false)
    expect(wrapper.find<HTMLElement>('.agenda-entry').element.style.getPropertyValue('--agenda-event-color')).toBe(
      '#123456',
    )
  })

  it('shows an event over several days on each of them', () => {
    const wrapper = render([
      occurrence({ title: 'Trip', start: at(2026, 10, 20, 18), end: at(2026, 10, 22, 10) }),
      allDay('2026-10-25', '2026-10-25', { event_id: 'h', title: 'Holiday' }),
    ])
    const times = wrapper.findAll('.agenda-time').map((time) => time.text())
    expect(times[0]).toContain(`from ${formatTime(at(2026, 10, 20, 18))}`)
    expect(times[0]).toContain('Day 1/3')
    expect(times[1]).toContain('All day')
    expect(times[1]).toContain('Day 2/3')
    expect(times[2]).toContain(`until ${formatTime(at(2026, 10, 22, 10))}`)
    expect(times[3]).toBe('All day')
    // One event, though it is listed three times.
    expect(wrapper.text()).toContain('2 events')
  })

  it('shows events that leave the time free lighter, and says how each one shows', () => {
    const wrapper = render([
      occurrence({ event_id: 'a', show_as: 'free', start: at(2026, 10, 15, 9) }),
      occurrence({ event_id: 'b', show_as: 'tentative', start: at(2026, 10, 16, 9) }),
      occurrence({ event_id: 'c', show_as: 'working_elsewhere', start: at(2026, 10, 17, 9) }),
    ])
    const entries = wrapper.findAll('.agenda-entry')
    expect(entries.map((entry) => entry.attributes('data-show-as'))).toEqual(['free', 'tentative', 'working_elsewhere'])
    expect(entries.map((entry) => entry.classes().includes('agenda-entry-free'))).toEqual([true, false, true])
  })

  it('marks past events, pending and declined ones, series and categories', () => {
    const wrapper = render([
      occurrence({ event_id: 'p', title: 'Past', start: at(2026, 10, 2, 9), end: at(2026, 10, 2, 10) }),
      occurrence({ event_id: 'q', title: 'Booking', status: 'pending', start: at(2026, 10, 15, 9) }),
      occurrence({ event_id: 'r', title: 'Lunch', status: 'rejected', start: at(2026, 10, 16, 9) }),
      occurrence({
        event_id: 's',
        title: 'Yoga',
        recurrence_count: 4,
        is_recurring: true,
        category_color: '#ff0000',
        start: at(2026, 10, 17, 9),
      }),
    ])
    const entries = wrapper.findAll('.agenda-entry')
    expect(entries[0]!.classes()).toContain('agenda-entry-past')
    expect(wrapper.findAll('.agenda-day')[0]!.classes()).toContain('agenda-day-past')
    expect(entries[1]!.classes()).toContain('agenda-entry-pending')
    expect(entries[1]!.find('.agenda-badge-pending').text()).toBe('pending')
    expect(entries[2]!.classes()).toContain('agenda-entry-declined')
    expect(entries[2]!.find('.agenda-badge').text()).toBe('declined')
    expect(entries[3]!.find('.agenda-title').text()).toBe('Yoga (4)')
    expect(entries[3]!.find('[aria-label="Recurring"]').exists()).toBe(true)
    expect(entries[3]!.find<HTMLElement>('.agenda-category-marker').element.style.backgroundColor).toBe(
      'rgb(255, 0, 0)',
    )
  })

  it('names the place, the resource, the category and, when several are shown, the calendar', () => {
    const occ = occurrence({
      location: 'Room 1',
      location_resource_id: 'r1',
      location_resource_icon: 'door',
      resource_name: 'Projector',
      resource_icon: 'projector',
      category_name: 'Work',
    })
    const wrapper = render([occ, occurrence({ event_id: 'x', location: 'Garden', start: at(2026, 10, 15, 9) })], {
      calendarNameOf: (o: Occurrence) => `Cal ${o.calendar_id}`,
    })
    const meta = wrapper.findAll('.agenda-meta')
    expect(meta[0]!.text()).toContain('Room 1')
    expect(meta[0]!.text()).toContain('Projector')
    expect(meta[0]!.text()).toContain('Work')
    expect(meta[0]!.find('.agenda-calendar').text()).toBe('Cal c1')
    expect(meta[1]!.text()).toContain('Garden')
  })

  it('opens an event when it is clicked', async () => {
    const occ = occurrence()
    const wrapper = render([occ])
    await wrapper.get('.agenda-entry').trigger('click')
    expect(wrapper.emitted('open')).toEqual([[occ]])
  })

  it('draws the "now" line before the first event still to come today', () => {
    const wrapper = render([
      occurrence({ event_id: 'a', title: 'Morning', start: at(2026, 10, 14, 9), end: at(2026, 10, 14, 10) }),
      occurrence({ event_id: 'b', title: 'Evening', start: at(2026, 10, 14, 18), end: at(2026, 10, 14, 19) }),
    ])
    const items = wrapper.findAll('.agenda-day-today .agenda-entries > li')
    expect(items.map((item) => (item.classes('agenda-now') ? 'now' : item.find('.agenda-title').text()))).toEqual([
      'Morning',
      'now',
      'Evening',
    ])
  })

  it('draws the "now" line after the last event once everything today is over', () => {
    const wrapper = render([
      occurrence({ event_id: 'a', title: 'Morning', start: at(2026, 10, 14, 7), end: at(2026, 10, 14, 8) }),
      occurrence({ event_id: 'b', title: 'Lunch', start: at(2026, 10, 14, 11), end: at(2026, 10, 14, 11, 30) }),
    ])
    const items = wrapper.findAll('.agenda-day-today .agenda-entries > li')
    expect(items.map((item) => (item.classes('agenda-now') ? 'now' : item.find('.agenda-title').text()))).toEqual([
      'Morning',
      'Lunch',
      'now',
    ])
  })

  it('finds events by what they say, and clears the search', async () => {
    const wrapper = render([
      occurrence({ event_id: 'a', title: 'Dentist' }),
      occurrence({ event_id: 'b', title: 'Football', location: 'Park', start: at(2026, 10, 15, 9) }),
    ])
    const input = wrapper.get('input[type="search"]')
    await input.setValue('park')
    expect(titles(wrapper)).toEqual(['Football'])
    expect(wrapper.text()).toContain('1 event')

    await wrapper.get('button[aria-label="Clear search"]').trigger('click')
    expect(titles(wrapper)).toEqual(['Dentist', 'Football'])
    expect(document.activeElement).toBe(input.element)

    await input.setValue('nothing')
    expect(wrapper.text()).toContain('No matches for “nothing”')
    expect(wrapper.text()).toContain('No events')
    await input.trigger('keydown', { key: 'Escape' })
    expect(titles(wrapper)).toHaveLength(2)

    await input.setValue('zzz')
    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Show all')!
      .trigger('click')
    expect(titles(wrapper)).toHaveLength(2)
  })

  it('can show only the events still to come', async () => {
    const wrapper = render([
      occurrence({ event_id: 'a', title: 'Earlier', start: at(2026, 10, 3, 9), end: at(2026, 10, 3, 10) }),
      occurrence({ event_id: 'b', title: 'Later', start: at(2026, 10, 30, 9), end: at(2026, 10, 30, 10) }),
    ])
    const toggle = wrapper.findAll('button').find((b) => b.text() === 'Upcoming only')!
    await toggle.trigger('click')
    expect(toggle.attributes('aria-pressed')).toBe('true')
    expect(titles(wrapper)).toEqual(['Later'])

    await wrapper.setProps({ occurrences: [occurrence({ start: at(2026, 10, 3, 9), end: at(2026, 10, 3, 10) })] })
    expect(wrapper.text()).toContain('No more upcoming events in October')
    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Show all')!
      .trigger('click')
    expect(titles(wrapper)).toHaveLength(1)
  })

  it('says when a month has no events', () => {
    const wrapper = render([])
    expect(wrapper.text()).toContain('No events in October')
    expect(wrapper.findAll('button').some((b) => b.text() === 'Show all')).toBe(false)
  })

  it('adds an event today at the next hour in the current month, and on the first day in other months', async () => {
    const wrapper = render([])
    const create = () =>
      wrapper
        .findAll('button')
        .find((b) => b.text() === 'New event')!
        .trigger('click')
    await create()
    expect(wrapper.emitted('create')![0]).toEqual([new Date(2026, 9, 14, 13)])

    await wrapper.setProps({ rangeStart: new Date(2026, 11, 1), rangeEnd: new Date(2027, 0, 1) })
    await create()
    expect(wrapper.emitted('create')![1]).toEqual([new Date(2026, 11, 1, 9)])
  })

  it('offers no new event to those who may not add any', () => {
    const wrapper = render([], { canCreate: false })
    expect(wrapper.findAll('button').some((b) => b.text() === 'New event')).toBe(false)
  })

  it('jumps to the search with "/", but not while typing elsewhere or with a modifier', () => {
    const wrapper = render([])
    const other = document.createElement('input')
    document.body.append(other)
    other.focus()
    other.dispatchEvent(new KeyboardEvent('keydown', { key: '/', bubbles: true }))
    expect(document.activeElement).toBe(other)

    other.blur()
    document.body.dispatchEvent(new KeyboardEvent('keydown', { key: '/', ctrlKey: true, bubbles: true }))
    expect(document.activeElement).not.toBe(wrapper.get('input[type="search"]').element)

    const event = new KeyboardEvent('keydown', { key: '/', bubbles: true, cancelable: true })
    document.body.dispatchEvent(event)
    expect(event.defaultPrevented).toBe(true)
    expect(document.activeElement).toBe(wrapper.get('input[type="search"]').element)

    wrapper.unmount()
    other.focus()
    document.body.dispatchEvent(new KeyboardEvent('keydown', { key: '/', bubbles: true }))
    expect(document.activeElement).toBe(other)
  })

  it('scrolls to today when it opens on the current month and when asked to', async () => {
    const wrapper = render([
      occurrence({ event_id: 'a', start: at(2026, 10, 2, 9), end: at(2026, 10, 2, 10) }),
      occurrence({ event_id: 'b', start: at(2026, 10, 20, 9), end: at(2026, 10, 20, 10) }),
    ])
    await nextTick()
    await nextTick()
    expect(scrollTo).toHaveBeenCalledWith({ top: expect.any(Number), behavior: 'auto' })

    scrollTo.mockClear()
    await (wrapper.vm as unknown as { scrollToToday(): Promise<void> }).scrollToToday()
    expect(scrollTo).toHaveBeenCalledWith({ top: expect.any(Number), behavior: 'smooth' })
  })

  it('scrolls to the end of the current month when nothing comes after today', async () => {
    const wrapper = render([occurrence({ start: at(2026, 10, 2, 9), end: at(2026, 10, 2, 10) })])
    await nextTick()
    await nextTick()
    expect(scrollTo).toHaveBeenCalledWith({ top: expect.any(Number) })

    // Another month goes back to its top.
    scrollTo.mockClear()
    await wrapper.setProps({ rangeStart: new Date(2026, 8, 1), rangeEnd: OCTOBER })
    expect(scrollTo).toHaveBeenCalledWith({ top: 0 })
  })
})
