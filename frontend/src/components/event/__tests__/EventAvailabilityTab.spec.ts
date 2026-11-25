import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { fakeBackend, reply, type FakeRequest } from '@/__tests__/fakeBackend'
import type * as api from '@/api'
import { i18n } from '@/i18n'
import { createAvailabilityCache, type AvailabilityCache } from '@/services/availability'
import EventAvailabilityTab from '../EventAvailabilityTab.vue'
import { signIn } from './helpers'

const local = (time: string, day = '2026-03-10') => new Date(`${day}T${time}`)
const period = (from: string, to: string, tentative = false, day = '2026-03-10', outOfOffice = false) => ({
  start: local(from, day).toISOString(),
  end: local(to, day).toISOString(),
  tentative,
  out_of_office: outOfOffice,
})

const people = [
  { id: 'me', name: 'Me' },
  { id: 'u1', name: 'Anna' },
  { id: 'u2', name: 'Ben' },
]

const availability: api.Availability = {
  users: [
    { id: 'me', name: 'Me Myself', busy: [] },
    // Busy before the event, and tentatively during it.
    { id: 'u1', name: 'Anna', busy: [period('07:00', '08:00'), period('09:30', '10:30', true)] },
  ],
  resources: [
    { id: 'r1', name: 'Room 1', busy: [period('22:00', '23:59'), period('10:00', '11:00', false, '2026-03-11')] },
  ],
}

interface Props {
  eventId?: string | null
  start: Date
  end: Date
  people: { id: string; name: string }[]
  resourceIds: string[]
  cache: AvailabilityCache
}

function render(props: Partial<Props> = {}) {
  return mount(EventAvailabilityTab, {
    props: {
      eventId: 'ev1',
      start: local('09:00'),
      end: local('10:00'),
      people,
      resourceIds: ['r1'],
      cache: createAvailabilityCache(),
      ...props,
    },
    global: { plugins: [i18n] },
  })
}

const rowNames = (wrapper: ReturnType<typeof render>) => wrapper.findAll('span[title]').map((s) => s.text())
const status = (wrapper: ReturnType<typeof render>) => wrapper.find('[role="status"]').text()
const days = (backend: { calls(pattern: string): FakeRequest[] }) =>
  backend.calls('POST /api/availability').map((r) => new Date((r.body as { start: string }).start).getDate())

describe('EventAvailabilityTab', () => {
  beforeEach(() => signIn())
  afterEach(() => vi.restoreAllMocks())

  it('asks for the day of the event, apart from the event itself', async () => {
    const backend = fakeBackend({ 'POST /api/availability': availability })
    render()
    await flushPromises()
    const [request] = backend.calls('POST /api/availability')
    expect(request!.body).toEqual({
      start: local('00:00').toISOString(),
      end: local('00:00', '2026-03-11').toISOString(),
      user_ids: ['me', 'u1', 'u2'],
      resource_ids: ['r1'],
      exclude_event_id: 'ev1',
    })
  })

  it('shows who is taken when, and that everyone is free', async () => {
    fakeBackend({ 'POST /api/availability': availability })
    const wrapper = render()
    await flushPromises()
    // Ben has no entry (e.g. no access), so no row.
    expect(rowNames(wrapper)).toEqual(['Me', 'Anna', 'Room 1'])
    const anna = wrapper.get('[role="img"][aria-label^="Anna"]')
    expect(anna.findAll('[title="Busy"]')).toHaveLength(1)
    expect(anna.findAll('[title="Tentatively busy"]')).toHaveLength(1)
    expect(anna.get('[title="This event"]').attributes('style')).toContain('left: 37.5%')
    expect(wrapper.get('[role="img"][aria-label^="Me"]').attributes('aria-label')).toBe('Me: —')
    // The room's booking of the next day is not on this one.
    expect(wrapper.get('[role="img"][aria-label^="Room 1"]').findAll('[title="Busy"]')).toHaveLength(1)
    // Tentative bookings don't count as conflicts.
    expect(status(wrapper)).toBe('Everyone is free at this time.')
  })

  it('tells time out of office apart, and counts it as a conflict', async () => {
    fakeBackend({
      'POST /api/availability': {
        users: [{ id: 'u1', name: 'Anna', busy: [period('08:00', '12:00', false, '2026-03-10', true)] }],
        resources: [],
      },
    })
    const wrapper = render()
    await flushPromises()
    const anna = wrapper.get('[role="img"][aria-label^="Anna"]')
    const away = anna.get('[data-kind="outOfOffice"]')
    expect(away.attributes('title')).toBe('Out of office')
    expect(anna.findAll('[title="Busy"]')).toHaveLength(0)
    expect(wrapper.text()).toContain('Out of office')
    expect(status(wrapper)).toBe('Busy at this time: Anna')
  })

  it('names those who are busy at the time of the event', async () => {
    fakeBackend({ 'POST /api/availability': availability })
    const wrapper = render({ start: local('07:30'), end: local('09:45') })
    await flushPromises()
    expect(status(wrapper)).toBe('Busy at this time: Anna')
  })

  it('asks for nothing without people or resources', async () => {
    const backend = fakeBackend()
    const wrapper = render({ people: [], resourceIds: [] })
    await flushPromises()
    expect(backend.requests).toHaveLength(0)
    expect(wrapper.text()).toContain('Add participants or a resource to see their availability.')
  })

  it('browses to other days, asking for each day only once', async () => {
    const backend = fakeBackend({ 'POST /api/availability': availability })
    const cache = createAvailabilityCache()
    const wrapper = render({ cache })
    await flushPromises()
    const [previous, next] = wrapper.findAll('button')
    await next!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('2026-03-11')
    await previous!.trigger('click')
    await previous!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('2026-03-09')
    expect(days(backend)).toEqual([10, 11, 9])

    // The day the event moves to is shown; known days come from the cache.
    await wrapper.setProps({ start: local('09:00', '2026-03-11'), end: local('10:00', '2026-03-11') })
    await flushPromises()
    expect(wrapper.text()).toContain('2026-03-11')
    render({ cache })
    await flushPromises()
    expect(days(backend)).toEqual([10, 11, 9])
  })

  it('shows only the day browsed to last', async () => {
    const answers: Array<() => void> = []
    fakeBackend({
      'POST /api/availability': (request) =>
        new Promise((resolve) => {
          const day = new Date((request.body as { start: string }).start).getDate()
          answers[day] = () => resolve({ users: [], resources: [{ id: 'r1', name: `Room on ${day}`, busy: [] }] })
        }),
    })
    const wrapper = render({ people: [] })
    await flushPromises()
    await wrapper.findAll('button')[1]!.trigger('click')
    answers[11]!()
    await flushPromises()
    answers[10]!()
    await flushPromises()
    expect(rowNames(wrapper)).toEqual(['Room on 11'])
  })

  it('reports when the availability cannot be loaded', async () => {
    fakeBackend({ 'POST /api/availability': reply(500, { detail: 'Server down' }) })
    const wrapper = render()
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toBe('Server down')
  })
})
