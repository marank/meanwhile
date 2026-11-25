import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type { Occurrence } from '@/api'
import { i18n } from '@/i18n'
import { formatTime } from '@/services/datetime'
import CalendarWeekStack from '../CalendarWeekStack.vue'
import { allDay, at, occurrence } from './calendarFixtures'

// Monday, 12 October 2026.
const MONDAY = new Date(2026, 9, 12)

function render(occurrences: Occurrence[], props: Record<string, unknown> = {}) {
  return mount(CalendarWeekStack, {
    props: {
      occurrences,
      weekStart: MONDAY,
      hiddenDays: [],
      weekendDays: [0, 6],
      colorOf: () => '#654321',
      canCreate: true,
      ...props,
    },
    global: { plugins: [i18n] },
  })
}

describe('CalendarWeekStack', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    i18n.global.locale.value = 'en'
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(2026, 9, 14, 12))
  })

  afterEach(() => vi.useRealTimers())

  it('shows the seven days of the week, marking today and the weekend', () => {
    const wrapper = render([])
    const days = wrapper.findAll('.week-stack-day')
    expect(days.map((day) => day.find('.week-stack-daynumber').text())).toEqual([
      '12',
      '13',
      '14',
      '15',
      '16',
      '17',
      '18',
    ])
    expect(days[0]!.find('.week-stack-weekday').text()).toBe('Mon')
    expect(days[2]!.classes()).toContain('week-stack-today')
    expect(days[5]!.classes()).toContain('week-stack-weekend')
    expect(days[6]!.classes()).toContain('week-stack-weekend')
    expect(days[0]!.classes()).not.toContain('week-stack-weekend')
    expect(days[0]!.get('button').attributes('aria-label')).toBe('Monday, October 12')
  })

  it('leaves out hidden days', () => {
    const wrapper = render([], { hiddenDays: [0, 6] })
    expect(wrapper.findAll('.week-stack-day')).toHaveLength(5)
  })

  it('shows each event as a tile with its time and how long it takes', () => {
    const wrapper = render([
      occurrence({ event_id: 'a', title: 'Short', start: at(2026, 10, 12, 9), end: at(2026, 10, 12, 9, 30) }),
      occurrence({ event_id: 'b', title: 'Hour', start: at(2026, 10, 13, 9), end: at(2026, 10, 13, 10) }),
      occurrence({ event_id: 'c', title: 'Long', start: at(2026, 10, 14, 9), end: at(2026, 10, 14, 10, 45) }),
      allDay('2026-10-15', '2026-10-15', { event_id: 'd', title: 'Holiday' }),
    ])
    const times = wrapper.findAll('.week-stack-time').map((time) => time.text())
    expect(times[0]).toBe(`${formatTime(at(2026, 10, 12, 9))} · 30 min`)
    expect(times[1]).toBe(`${formatTime(at(2026, 10, 13, 9))} · 1 h`)
    expect(times[2]).toBe(`${formatTime(at(2026, 10, 14, 9))} · 1 h 45 min`)
    expect(times[3]).toBe('All day')
    const tile = wrapper.find<HTMLElement>('.week-stack-event').element
    expect(tile.style.getPropertyValue('--week-stack-color')).toBe('#654321')
  })

  it('shows an event over several days on each of its days in the week', () => {
    const wrapper = render([occurrence({ title: 'Trip', start: at(2026, 10, 16, 18), end: at(2026, 10, 18, 10) })])
    const times = wrapper.findAll('.week-stack-time').map((time) => time.text())
    expect(times).toEqual([
      `from ${formatTime(at(2026, 10, 16, 18))} · Day 1/3`,
      'All day · Day 2/3',
      `until ${formatTime(at(2026, 10, 18, 10))} · Day 3/3`,
    ])
  })

  it('marks past, pending and declined events and shows the series count, category, place and resource', () => {
    const wrapper = render([
      occurrence({ event_id: 'a', title: 'Past', start: at(2026, 10, 12, 9), end: at(2026, 10, 12, 10) }),
      occurrence({ event_id: 'b', title: 'Booking', status: 'pending', start: at(2026, 10, 15, 9) }),
      occurrence({ event_id: 'c', title: 'Off', status: 'cancelled', start: at(2026, 10, 16, 9) }),
      occurrence({
        event_id: 'd',
        title: 'Yoga',
        recurrence_count: 2,
        category_color: '#00ff00',
        category_name: 'Sport',
        location: 'Hall',
        location_resource_id: 'r1',
        location_resource_icon: 'door',
        resource_name: 'Mats',
        resource_icon: 'box',
        start: at(2026, 10, 17, 9),
      }),
      occurrence({ event_id: 'e', title: 'Picnic', location: 'Park', start: at(2026, 10, 18, 9) }),
    ])
    const tiles = wrapper.findAll('.week-stack-event')
    expect(tiles[0]!.classes()).toContain('week-stack-event-past')
    expect(tiles[1]!.classes()).toContain('week-stack-event-pending')
    expect(tiles[2]!.classes()).toContain('week-stack-event-declined')
    const yoga = tiles[3]!
    expect(yoga.find('.week-stack-title').text()).toBe('Yoga (2)')
    expect(yoga.find('.week-stack-title').attributes('title')).toBe('Sport')
    expect(yoga.find('.week-stack-category').exists()).toBe(true)
    expect(yoga.findAll('.week-stack-meta').map((meta) => meta.text())).toEqual(['Hall', 'Mats'])
    expect(tiles[4]!.find('.week-stack-meta').text()).toBe('Park')
  })

  it('opens an event when its tile is tapped', async () => {
    const occ = occurrence({ start: at(2026, 10, 13, 9), end: at(2026, 10, 13, 10) })
    const wrapper = render([occ])
    await wrapper.get('.week-stack-event').trigger('click')
    expect(wrapper.emitted('open')).toEqual([[occ]])
    expect(wrapper.emitted('create')).toBeUndefined()
  })

  it('adds an event on a day when its date or free space is tapped', async () => {
    const wrapper = render([])
    const days = wrapper.findAll('.week-stack-day')
    await days[1]!.get('.week-stack-date').trigger('click')
    await days[3]!.get('.week-stack-events').trigger('click')
    // At the start of the working day rather than at midnight.
    expect(wrapper.emitted('create')).toEqual([[new Date(2026, 9, 13, 9)], [new Date(2026, 9, 15, 9)]])
  })

  it('adds nothing for those who may not add events', async () => {
    const wrapper = render([], { canCreate: false })
    expect(wrapper.get('.week-stack-date').attributes('disabled')).toBeDefined()
    await wrapper.get('.week-stack-events').trigger('click')
    expect(wrapper.emitted('create')).toBeUndefined()
  })
})
