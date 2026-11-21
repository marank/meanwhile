import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, h, nextTick } from 'vue'
import { createMemoryHistory, createRouter, RouterView, type Router } from 'vue-router'
import type { Layout, Occurrence } from '@/api'
import { i18n } from '@/i18n'
import { dialog, submitDialog } from '@/services/dialog'
import { browserTimeZone } from '@/services/datetime'
import { realtime } from '@/services/realtime'
import { toasts } from '@/services/toast'
import { useCalendarStore } from '@/stores/calendars'
import { useThemeStore } from '@/stores/theme'
import { fakeBackend, reply, type FakeBackend } from '@/__tests__/fakeBackend'
import {
  allDay,
  at,
  calendarItem,
  folder,
  occurrence,
  overviewSettings,
  stubMatchMedia,
} from '@/components/calendar/__tests__/calendarFixtures'
import { event } from '@/components/event/__tests__/helpers'
import CalendarView from '../CalendarView.vue'
import { fullCalendar } from './fullCalendarStub'

/* eslint-disable @typescript-eslint/no-explicit-any -- FullCalendar's callback arguments, built by hand. */

vi.mock('@fullcalendar/vue3', () => import('./fullCalendarStub'))

enableAutoUnmount(afterEach)

const PHONE = '(max-width: 40rem)'

const EventModal = defineComponent({
  name: 'EventModal',
  props: {
    calendarId: { type: String, default: undefined },
    eventId: { type: String, default: null },
    occurrence: { type: Object, default: null },
    defaultStart: { type: Date, default: undefined },
    defaultEnd: { type: Date, default: undefined },
    defaultAllDay: { type: Boolean, default: undefined },
  },
  emits: ['saved', 'cancel', 'deleted'],
  setup(_, { emit }) {
    return () =>
      h('div', { class: 'event-modal' }, [
        h('button', { class: 'modal-save', onClick: () => emit('saved') }, 'save'),
        h('button', { class: 'modal-cancel', onClick: () => emit('cancel') }, 'cancel'),
        h('button', { class: 'modal-delete', onClick: () => emit('deleted') }, 'delete'),
      ])
  },
})

function layout(): Layout {
  return {
    folders: [folder('f1')],
    calendars: [
      calendarItem('c1', { calendar: { name: 'Work', url_path: 'work', event_color: '#336699' } }),
      calendarItem('c2', {
        role: 'read',
        folderId: 'f1',
        calendar: { name: 'Club', event_color: '#00aa00', show_weekends: false, first_weekday: 0 },
      }),
    ],
  }
}

let backend: FakeBackend
let router: Router
let media: ReturnType<typeof stubMatchMedia>
let events: Occurrence[]

async function open(path: string, options: { phone?: boolean; loadLayout?: boolean } = {}) {
  media.set(PHONE, options.phone ?? false)
  router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/calendar/folder/:folderId', component: CalendarView, props: true },
      { path: '/calendar/:calendarId?', component: CalendarView, props: true },
      { path: '/event/:eventId', component: CalendarView, props: true },
    ],
  })
  await router.push(path)
  if (options.loadLayout !== false) await useCalendarStore().load()
  const wrapper = mount(
    { render: () => h(RouterView) },
    { global: { plugins: [i18n, router], stubs: { EventModal } }, attachTo: document.body },
  )
  await flushPromises()
  return wrapper
}

type Wrapper = Awaited<ReturnType<typeof open>>

/** The ranges and calendars the events were asked for, in order. */
function eventRequests() {
  return backend.calls('GET /api/events').map((request) => ({
    ids: request.query.getAll('calendar_ids'),
    start: new Date(request.query.get('start')!),
    end: new Date(request.query.get('end')!),
  }))
}

const lastRange = () => {
  const last = eventRequests().at(-1)!
  return [last.start, last.end]
}

const modal = (wrapper: Wrapper) => wrapper.findComponent(EventModal)

async function click(wrapper: Wrapper, selector: string) {
  await wrapper.get(selector).trigger('click')
  await flushPromises()
}

async function clickText(wrapper: Wrapper, text: string) {
  await wrapper
    .findAll('button')
    .find((button) => button.text() === text)!
    .trigger('click')
  await flushPromises()
}

/** What FullCalendar is told to show. */
function fcEvents(): any[] {
  return fullCalendar.options!.events
}

function fcEvent(index = 0) {
  const event = fcEvents()[index]
  return { ...event, start: new Date(event.start), end: new Date(event.end) }
}

function changeInfo(event: Record<string, unknown>) {
  return { event, revert: vi.fn() } as any
}

describe('CalendarView', () => {
  beforeEach(() => {
    localStorage.clear()
    media = stubMatchMedia()
    setActivePinia(createPinia())
    i18n.global.locale.value = 'en'
    vi.useFakeTimers({ toFake: ['Date'] })
    // Wednesday, 14 October 2026, noon.
    vi.setSystemTime(new Date(2026, 9, 14, 12))
    vi.spyOn(realtime, 'setCalendars').mockImplementation(() => {})
    Element.prototype.scrollTo = vi.fn()
    fullCalendar.reset()
    events = []
    backend = fakeBackend({
      'GET /api/layout': layout(),
      'GET /api/users/me/settings': overviewSettings(),
      'GET /api/events': () => events,
    })
  })

  afterEach(() => {
    if (dialog.open) submitDialog(null)
    vi.useRealTimers()
    vi.restoreAllMocks()
    delete (Element.prototype as Partial<Element>).scrollTo
    document.body.innerHTML = ''
  })

  describe('what the URL selects', () => {
    it('shows the events of all calendars for the month on screen', async () => {
      const wrapper = await open('/calendar/all')
      expect(backend.calls('GET /api/users/me/settings')).toHaveLength(1)
      // The grid of October 2026, Monday to Sunday once the overview's first weekday is known.
      expect(eventRequests().at(-1)).toEqual({
        ids: ['c1', 'c2'],
        start: new Date(2026, 8, 28),
        end: new Date(2026, 10, 2),
      })
      expect(wrapper.get('.toolbar-title').text()).toBe(`Month of ${new Date(2026, 9, 1).toDateString()}`)
      expect(fullCalendar.options!.firstDay).toBe(1)
      expect(fullCalendar.options!.locale).toBe('en')
      expect(backend.unhandled).toEqual([])
    })

    it('shows one calendar, found by its readable path, in its own layout', async () => {
      await open('/calendar/work')
      expect(eventRequests().at(-1)!.ids).toEqual(['c1'])
      expect(fullCalendar.options!.selectable).toBe(true)
      expect(fullCalendar.options!.weekNumberCalculation).toBe('ISO')
    })

    it('shows the calendars of a folder, without the hidden weekend of the calendar shown', async () => {
      await open('/calendar/c2')
      expect(fullCalendar.options!.hiddenDays).toEqual([0, 6])
      expect(fullCalendar.options!.weekNumberCalculation).toBe('local')

      await router.push('/calendar/folder/f1')
      await flushPromises()
      expect(eventRequests().at(-1)!.ids).toEqual(['c2'])
      expect(fullCalendar.options!.hiddenDays).toEqual([])
    })

    it('falls back to the first calendar for a calendar that is gone', async () => {
      await open('/calendar/gone', { loadLayout: false })
      expect(router.currentRoute.value.fullPath).toBe('/calendar/gone')
      await useCalendarStore().load()
      await flushPromises()
      expect(router.currentRoute.value.fullPath).toBe('/calendar/c2')
    })

    it('opens the first calendar of the sidebar when opened without one, inside a folder too', async () => {
      // The folder comes first in the sidebar, with Club in it; Work follows.
      await open('/calendar?view=week')
      expect(router.currentRoute.value.fullPath).toBe('/calendar/c2?view=week')
      expect(eventRequests().map((request) => request.ids)).toEqual([['c2']])
    })

    it('opens what was shown last, all calendars included', async () => {
      await open('/calendar/folder/f1')
      await router.push('/calendar')
      await flushPromises()
      expect(router.currentRoute.value.fullPath).toBe('/calendar/folder/f1')

      await router.push('/calendar/all')
      await flushPromises()
      await router.push('/calendar')
      await flushPromises()
      expect(router.currentRoute.value.fullPath).toBe('/calendar/all')
    })

    it('opens the first calendar when the one shown last is gone', async () => {
      localStorage.setItem('calendar-selection', 'gone')
      await open('/calendar')
      expect(router.currentRoute.value.fullPath).toBe('/calendar/c2')
    })

    it('opens all calendars when there are none', async () => {
      backend.on('GET /api/layout', () => ({ folders: [], calendars: [] }))
      await open('/calendar')
      expect(router.currentRoute.value.fullPath).toBe('/calendar/all')
    })

    it('loads the events of the new selection when another calendar is chosen', async () => {
      await open('/calendar/all')
      const before = eventRequests().length
      await router.push('/calendar/work')
      await flushPromises()
      expect(
        eventRequests()
          .slice(before)
          .map((request) => request.ids),
      ).toEqual([['c1']])
    })

    it('uses the app defaults until the overview settings have come', async () => {
      backend.on('GET /api/users/me/settings', reply(500))
      await open('/calendar/all')
      expect(fullCalendar.options!.firstDay).toBe(0)
    })
  })

  describe('the events it shows', () => {
    it('labels each event with its title, status, place and resource', async () => {
      events = [
        occurrence({
          event_id: 'a',
          title: 'Yoga',
          recurrence_count: 3,
          location: 'Hall',
          location_resource_id: 'r1',
          location_resource_icon: 'door-open',
          resource_name: 'Mats',
          resource_icon: 'home',
        }),
        occurrence({ event_id: 'b', title: 'Room', status: 'pending', calendar_id: 'c2', can_edit: false }),
        occurrence({ event_id: 'c', title: 'Lunch', status: 'rejected' }),
        occurrence({ event_id: 'd', title: 'Party', status: 'cancelled' }),
        allDay('2026-10-20', '2026-10-21', { event_id: 'e', title: 'Fair' }),
      ]
      await open('/calendar/all')
      expect(fcEvents().map((event) => event.title)).toEqual([
        'Yoga (3) · Hall · Mats',
        'Room (pending)',
        'Lunch (declined)',
        'Party (declined)',
        'Fair',
      ])
      expect(fcEvents()[0]).toMatchObject({ id: `a-${events[0]!.start}`, startEditable: true, color: '#336699' })
      expect(fcEvents()[1]).toMatchObject({ startEditable: false, durationEditable: false, color: '#00aa00' })
      // All-day events go to FullCalendar as dates, so they stay on their days in every time zone.
      expect(fcEvents()[4]).toMatchObject({ start: '2026-10-20', end: '2026-10-21', allDay: true })
      expect(fullCalendar.options!.eventClass({ event: fcEvents()[1] })).toBe('calendar-event calendar-event-pending')
      expect(fullCalendar.options!.eventClass({ event: fcEvents()[0] })).toBe('calendar-event')
    })

    it('shows all events in the overview color when the overview asks for it, and dark colors in the dark', async () => {
      backend.on('GET /api/users/me/settings', overviewSettings({ use_calendar_colors: false }))
      events = [occurrence()]
      await open('/calendar/all')
      expect(fcEvents()[0].color).toBe('#aa0000')
      useThemeStore().setPreference('dark')
      await nextTick()
      expect(fcEvents()[0].color).toBe('#ff8888')
    })

    it('draws an event with its time, category, icons and status', async () => {
      events = [
        occurrence({
          title: 'Yoga',
          category_color: '#ff0000',
          location: 'Hall',
          location_resource_id: 'r1',
          location_resource_icon: 'door-open',
        }),
      ]
      await open('/calendar/all')
      const event = fcEvent()
      const { domNodes } = fullCalendar.options!.eventContent({
        event,
        timeText: '10:00',
        isShort: false,
        view: { type: 'dayGridMonth' },
      })
      const label = domNodes[0] as HTMLElement
      expect(label.className).toBe('fc-event-label')
      expect(label.querySelector('.fc-event-time-label')!.textContent).toBe('10:00')
      expect((label.querySelector('.fc-event-category-marker') as HTMLElement).style.backgroundColor).toBe(
        'rgb(255, 0, 0)',
      )
      expect(label.querySelector('.fc-event-resource-icon svg')).not.toBeNull()
      expect(label.lastElementChild!.textContent).toBe('Yoga · Hall')
    })

    it('stacks the time above the title of a long event in the week', async () => {
      events = [occurrence({ category_color: '#ff0000', status: 'cancelled' })]
      await open('/calendar/all')
      const event = fcEvent()
      const { domNodes } = fullCalendar.options!.eventContent({
        event,
        timeText: '10:00 – 11:00',
        isShort: false,
        view: { type: 'timeGridWeek' },
      })
      const label = domNodes[0] as HTMLElement
      expect(label.classList).toContain('fc-event-label-stacked')
      expect(label.classList).toContain('fc-event-declined')
      expect([...label.querySelectorAll('.fc-event-time-label')]).toHaveLength(2)
      expect(label.querySelector('.fc-event-end-label')).not.toBeNull()
      // The category marker starts the title.
      expect(label.lastElementChild!.firstElementChild!.className).toBe('fc-event-category-marker')
    })

    it('marks events over several days, and draws untimed ones without a time', async () => {
      events = [allDay('2026-10-20', '2026-10-22')]
      await open('/calendar/all')
      const event = { ...fcEvent(), end: new Date(2026, 9, 23) }
      const { domNodes } = fullCalendar.options!.eventContent({
        event,
        timeText: '',
        isShort: false,
        view: { type: 'dayGridMonth' },
      })
      expect((domNodes[0] as HTMLElement).className).toBe('fc-event-label fc-event-label-multiday')
      expect((domNodes[0] as HTMLElement).querySelector('.fc-event-time-label')).toBeNull()
    })

    it('colors today and the weekend, and labels the current time', async () => {
      await open('/calendar/all')
      const { dayCellClass, dayLaneClass, nowIndicatorHeaderContent } = fullCalendar.options!
      expect(dayCellClass({ dow: 3, isToday: true })).toBe('calendar-default calendar-today')
      expect(dayCellClass({ dow: 6, isToday: false })).toBe('calendar-default calendar-weekend')
      expect(dayLaneClass({ dow: 1, isToday: false })).toBe('calendar-default calendar-day-lane')
      expect(nowIndicatorHeaderContent({ date: new Date(2026, 9, 14, 9, 5) })).toMatch(/9:05/)
    })
  })

  describe('an event in the URL', () => {
    const monthShown = (wrapper: Wrapper) => wrapper.get('.toolbar-title').text()

    it('opens over what was shown last, at its date, and gives way to the calendar when closed', async () => {
      localStorage.setItem('calendar-selection', 'c1')
      backend.on('GET /api/events/e9', event({ id: 'e9', calendar_id: 'c1', start: '2026-12-03T10:00:00' }))
      const wrapper = await open('/event/e9')
      expect(modal(wrapper).props()).toMatchObject({ eventId: 'e9', occurrence: null })
      expect(monthShown(wrapper)).toBe(`Month of ${new Date(2026, 11, 1).toDateString()}`)
      expect(eventRequests().at(-1)!.ids).toEqual(['c1'])
      expect(router.currentRoute.value.fullPath).toBe('/event/e9')

      await click(wrapper, '.modal-cancel')
      expect(modal(wrapper).exists()).toBe(false)
      expect(router.currentRoute.value.fullPath).toBe('/calendar/work')
    })

    it("switches to the event's calendar where what was shown doesn't have it", async () => {
      localStorage.setItem('calendar-selection', 'c2')
      backend.on(
        'GET /api/events/e9',
        event({ id: 'e9', calendar_id: 'c1', start: '2026-11-20T00:00:00Z', all_day: true }),
      )
      const wrapper = await open('/event/e9')
      expect(eventRequests().at(-1)!.ids).toEqual(['c1'])
      expect(monthShown(wrapper)).toBe(`Month of ${new Date(2026, 10, 1).toDateString()}`)
      await click(wrapper, '.modal-save')
      expect(router.currentRoute.value.fullPath).toBe('/calendar/work')
    })

    it('opens one followed from the calendar over it', async () => {
      backend.on('GET /api/events/e9', event({ id: 'e9', calendar_id: 'c1', start: '2026-10-20T10:00:00' }))
      const wrapper = await open('/calendar/work')
      await router.push('/event/e9')
      await flushPromises()
      expect(modal(wrapper).props('eventId')).toBe('e9')
      expect(eventRequests().every((request) => request.ids.join() === 'c1')).toBe(true)
    })

    it('reports other failures as they come', async () => {
      toasts.splice(0)
      backend.on('GET /api/events/e9', reply(500))
      await open('/event/e9')
      expect(toasts.map((t) => t.message)).toEqual(['Could not load the requested settings.'])
    })

    it('says so and shows the calendar for an event that is gone or not to be seen', async () => {
      toasts.splice(0)
      localStorage.setItem('calendar-selection', 'c1')
      backend.on('GET /api/events/gone', reply(404, { detail: 'Event not found' }))
      const wrapper = await open('/event/gone')
      expect(modal(wrapper).exists()).toBe(false)
      expect(toasts.map((t) => t.message)).toEqual(['This event no longer exists, or you can’t see it.'])
      expect(router.currentRoute.value.fullPath).toBe('/calendar/work')
    })
  })

  describe('opening and adding events', () => {
    it('opens an event that is clicked, and closes it again', async () => {
      const occ = occurrence({ event_id: 'e7' })
      events = [occ]
      const wrapper = await open('/calendar/work')
      fullCalendar.options!.eventClick({ event: fcEvents()[0] })
      await flushPromises()
      expect(modal(wrapper).props()).toMatchObject({ calendarId: 'c1', eventId: 'e7', occurrence: null })
      await click(wrapper, '.modal-cancel')
      expect(modal(wrapper).exists()).toBe(false)
    })

    it('opens an occurrence of a series as that occurrence, and a changed one as an event of its own', async () => {
      const series = occurrence({ event_id: 's1', series_id: 's1', recurrence_id: '20261014T080000Z' })
      const changed = occurrence({ event_id: 'x1', series_id: 's1', recurrence_id: '20261015T080000Z' })
      events = [series, changed]
      const wrapper = await open('/calendar/all')
      fullCalendar.options!.eventClick({ event: fcEvents()[0] })
      await flushPromises()
      expect(modal(wrapper).props('occurrence')).toEqual({
        recurrenceId: '20261014T080000Z',
        start: series.start,
        end: series.end,
      })
      // Opened in "All calendars", it isn't tied to a calendar.
      expect(modal(wrapper).props('calendarId')).toBeUndefined()
      await click(wrapper, '.modal-cancel')

      fullCalendar.options!.eventClick({ event: fcEvents()[1] })
      await flushPromises()
      expect(modal(wrapper).props()).toMatchObject({ eventId: 'x1', occurrence: null })
    })

    it('adds an event on a clicked day, and loads the events again once it is saved', async () => {
      const wrapper = await open('/calendar/work')
      const before = eventRequests().length
      fullCalendar.options!.dateClick({ date: new Date(2026, 9, 20, 9) })
      await flushPromises()
      expect(modal(wrapper).props()).toMatchObject({
        calendarId: 'c1',
        eventId: null,
        defaultStart: new Date(2026, 9, 20, 9),
        defaultEnd: undefined,
        defaultAllDay: undefined,
      })
      await click(wrapper, '.modal-save')
      expect(modal(wrapper).exists()).toBe(false)
      expect(eventRequests()).toHaveLength(before + 1)

      fullCalendar.options!.dateClick({ date: new Date(2026, 9, 21) })
      await flushPromises()
      await click(wrapper, '.modal-delete')
      expect(modal(wrapper).exists()).toBe(false)
      expect(eventRequests()).toHaveLength(before + 2)
    })

    it('adds an event over the days or hours selected', async () => {
      const wrapper = await open('/calendar/work')
      fullCalendar.options!.select({ start: new Date(2026, 9, 20), end: new Date(2026, 9, 23), allDay: true })
      await flushPromises()
      // FullCalendar's end is the day after; the event ends on the last day selected.
      expect(modal(wrapper).props()).toMatchObject({
        defaultStart: new Date(2026, 9, 20),
        defaultEnd: new Date(2026, 9, 22),
        defaultAllDay: true,
      })
      await click(wrapper, '.modal-cancel')

      fullCalendar.options!.select({
        start: new Date(2026, 9, 20, 9),
        end: new Date(2026, 9, 20, 11),
        allDay: false,
      })
      await flushPromises()
      expect(modal(wrapper).props()).toMatchObject({ defaultEnd: new Date(2026, 9, 20, 11), defaultAllDay: false })
    })

    it('adds nothing where no single calendar is shown or one may not add events', async () => {
      const wrapper = await open('/calendar/all')
      expect(fullCalendar.options!.selectable).toBe(false)
      fullCalendar.options!.dateClick({ date: new Date(2026, 9, 20) })
      await flushPromises()
      expect(modal(wrapper).exists()).toBe(false)

      await router.push('/calendar/c2')
      await flushPromises()
      fullCalendar.options!.dateClick({ date: new Date(2026, 9, 20) })
      await flushPromises()
      expect(modal(wrapper).exists()).toBe(false)
    })

    it('closes a new event when the calendar it was for is left', async () => {
      events = [occurrence()]
      const wrapper = await open('/calendar/work')
      fullCalendar.options!.dateClick({ date: new Date(2026, 9, 20) })
      await flushPromises()
      await router.push('/calendar/all')
      await flushPromises()
      expect(modal(wrapper).exists()).toBe(false)

      // An event that is open stays open.
      await router.push('/calendar/work')
      await flushPromises()
      fullCalendar.options!.eventClick({ event: fcEvents()[0] })
      await flushPromises()
      await router.push('/calendar/all')
      await flushPromises()
      expect(modal(wrapper).exists()).toBe(true)
    })
  })

  describe('moving and resizing events', () => {
    beforeEach(() => {
      backend.on('PATCH /api/events/*', (request) => ({ id: request.path.split('/').at(-1) }))
    })

    it('saves a moved event and loads the events again', async () => {
      events = [occurrence({ event_id: 'e1' })]
      await open('/calendar/work')
      const before = eventRequests().length
      const info = changeInfo({
        ...fcEvent(),
        start: new Date(2026, 9, 15, 14),
        end: new Date(2026, 9, 15, 15, 30),
      })
      await fullCalendar.options!.eventDrop(info)
      await flushPromises()
      expect(backend.calls('PATCH /api/events/e1')[0]!.body).toEqual({
        start: at(2026, 10, 15, 14),
        end: at(2026, 10, 15, 15, 30),
        all_day: false,
        timezone: browserTimeZone(),
      })
      expect(info.revert).not.toHaveBeenCalled()
      expect(eventRequests()).toHaveLength(before + 1)
    })

    it('gives an event moved without an end an hour', async () => {
      events = [occurrence({ event_id: 'e1' })]
      await open('/calendar/work')
      await fullCalendar.options!.eventDrop(changeInfo({ ...fcEvent(), start: new Date(2026, 9, 15, 14), end: null }))
      expect(backend.calls('PATCH /api/events/e1')[0]!.body).toMatchObject({ end: at(2026, 10, 15, 15) })
    })

    it('saves the days of a resized all-day event as UTC midnights, the end inclusive', async () => {
      events = [allDay('2026-10-20', '2026-10-20', { event_id: 'e2' })]
      await open('/calendar/work')
      await fullCalendar.options!.eventResize(
        changeInfo({ ...fcEvent(), start: new Date(2026, 9, 20), end: new Date(2026, 9, 23) }),
      )
      expect(backend.calls('PATCH /api/events/e2')[0]!.body).toMatchObject({
        start: '2026-10-20T00:00:00.000Z',
        end: '2026-10-22T00:00:00.000Z',
        all_day: true,
      })

      await fullCalendar.options!.eventDrop(changeInfo({ ...fcEvent(), start: new Date(2026, 9, 25), end: null }))
      expect(backend.calls('PATCH /api/events/e2')[1]!.body).toMatchObject({
        start: '2026-10-25T00:00:00.000Z',
        end: '2026-10-25T00:00:00.000Z',
      })
    })

    it('puts back an event dropped without a start', async () => {
      events = [occurrence()]
      await open('/calendar/work')
      const info = changeInfo({ ...fcEvent(), start: null })
      await fullCalendar.options!.eventDrop(info)
      expect(info.revert).toHaveBeenCalled()
      expect(backend.calls('PATCH /api/events/*')).toHaveLength(0)
    })

    it('asks which events of a series a move is for', async () => {
      backend.on('PATCH /api/events/*/occurrences/*', {})
      events = [occurrence({ event_id: 's1', series_id: 's1', recurrence_id: '20261014T080000Z' })]
      await open('/calendar/work')
      const moved = { ...fcEvent(), start: new Date(2026, 9, 15, 14), end: new Date(2026, 9, 15, 15) }

      const kept = changeInfo(moved)
      const keeping = fullCalendar.options!.eventDrop(kept)
      await flushPromises()
      expect(dialog.kind).toBe('choice')
      expect(dialog.choices.map((choice) => choice.value)).toEqual(['this', 'following', 'all'])
      submitDialog(null)
      await keeping
      expect(kept.revert).toHaveBeenCalled()
      expect(backend.calls('PATCH /api/events/*/occurrences/*')).toHaveLength(0)

      const changing = fullCalendar.options!.eventDrop(changeInfo(moved))
      await flushPromises()
      submitDialog('following')
      await changing
      const [request] = backend.calls('PATCH /api/events/*/occurrences/*')
      expect(request!.path).toBe('/api/events/s1/occurrences/20261014T080000Z')
      expect(request!.query.get('scope')).toBe('following')
    })

    it('puts the event back and says why when the change is refused', async () => {
      backend.on('PATCH /api/events/*', reply(400, { detail: 'Too late' }))
      events = [occurrence({ event_id: 'e1' })]
      await open('/calendar/work')
      const info = changeInfo({ ...fcEvent(), start: new Date(2026, 9, 15, 14) })
      const changing = fullCalendar.options!.eventDrop(info)
      await flushPromises()
      expect(info.revert).toHaveBeenCalled()
      expect(dialog.kind).toBe('alert')
      expect(dialog.message).toBe('Too late')
      submitDialog()
      await changing
    })
  })

  describe('moving through the calendar', () => {
    it('steps through months with the toolbar and goes back to today', async () => {
      const wrapper = await open('/calendar/all')
      const today = wrapper.findAll('button').find((button) => button.text() === 'Today')!
      expect(today.attributes('disabled')).toBeDefined()

      await click(wrapper, 'button[aria-label="Next"]')
      expect(lastRange()).toEqual([new Date(2026, 9, 26), new Date(2026, 11, 7)])
      expect(wrapper.get('.toolbar-title').text()).toBe(`Month of ${new Date(2026, 10, 1).toDateString()}`)
      expect(today.attributes('disabled')).toBeUndefined()

      await click(wrapper, 'button[aria-label="Previous"]')
      await click(wrapper, 'button[aria-label="Previous"]')
      expect(fullCalendar.view!.currentStart).toEqual(new Date(2026, 8, 1))

      await clickText(wrapper, 'Today')
      expect(fullCalendar.view!.currentStart).toEqual(new Date(2026, 9, 1))

      await click(wrapper, 'button[aria-label="Next year"]')
      expect(fullCalendar.view!.currentStart).toEqual(new Date(2027, 9, 1))
    })

    it('switches to the week, opening it an hour before the current time', async () => {
      const wrapper = await open('/calendar/all')
      await clickText(wrapper, 'Week')
      expect(fullCalendar.view!.type).toBe('timeGridWeek')
      expect(lastRange()).toEqual([new Date(2026, 9, 12), new Date(2026, 9, 19)])
      expect(fullCalendar.scrollToTime).toHaveBeenCalledWith('11:00')
      // The line marking the current time spans all days, from Wednesday's column.
      const style = wrapper.get<HTMLElement>('.calendar-root').element.style
      expect(style.getPropertyValue('--calendar-now-column')).toBe('2')
      expect(style.getPropertyValue('--calendar-now-columns')).toBe('7')

      fullCalendar.scrollToTime.mockClear()
      await click(wrapper, 'button[aria-label="Next"]')
      expect(fullCalendar.scrollToTime).not.toHaveBeenCalled()
      expect(style.getPropertyValue('--calendar-now-columns')).toBe('1')
    })

    it('counts only the days shown for the current time line', async () => {
      const wrapper = await open('/calendar/c2?view=week')
      const style = wrapper.get<HTMLElement>('.calendar-root').element.style
      // Sunday to Saturday without the weekend: Wednesday is the third of five.
      expect(style.getPropertyValue('--calendar-now-column')).toBe('2')
      expect(style.getPropertyValue('--calendar-now-columns')).toBe('5')
    })

    it('opens on the month or week the URL names', async () => {
      await open('/calendar/all?date=2026-12-15&view=week')
      expect(fullCalendar.view!.type).toBe('timeGridWeek')
      expect(fullCalendar.view!.currentStart).toEqual(new Date(2026, 11, 14))
    })

    it('follows links to other months and views while open', async () => {
      await open('/calendar/all')
      await router.push('/calendar/all?date=2027-02')
      await flushPromises()
      expect(fullCalendar.view!.currentStart).toEqual(new Date(2027, 1, 1))

      await router.push('/calendar/all?view=week&date=2027-02-10')
      await flushPromises()
      expect(fullCalendar.view).toMatchObject({ type: 'timeGridWeek', currentStart: new Date(2027, 1, 8) })

      // What is on screen already stays.
      const requests = eventRequests().length
      await router.push('/calendar/all?view=week&date=2027-02-11')
      await flushPromises()
      expect(eventRequests()).toHaveLength(requests)

      await router.push('/calendar/all?view=month')
      await flushPromises()
      expect(fullCalendar.view!.type).toBe('dayGridMonth')
    })
  })

  describe('the list', () => {
    it('lists the events of the month, naming their calendars when several are shown', async () => {
      events = [
        occurrence({ event_id: 'a', title: 'Standup' }),
        occurrence({ event_id: 'b', title: 'Match', calendar_id: 'c2' }),
      ]
      const wrapper = await open('/calendar/all?view=list')
      expect(fullCalendar.mounts).toBe(0)
      expect(lastRange()).toEqual([new Date(2026, 9, 1), new Date(2026, 10, 1)])
      expect(wrapper.get('.toolbar-title').text()).toBe('October 2026')
      expect(wrapper.findAll('.agenda-calendar').map((name) => name.text())).toEqual(['Club', 'Work'])
    })

    it('names no calendar when only one is shown', async () => {
      events = [occurrence()]
      const wrapper = await open('/calendar/work?view=list')
      expect(wrapper.find('.agenda-entry').exists()).toBe(true)
      expect(wrapper.find('.agenda-calendar').exists()).toBe(false)
    })

    it('steps through months, and goes back to today', async () => {
      const wrapper = await open('/calendar/all?view=list')
      await click(wrapper, 'button[aria-label="Next"]')
      expect(lastRange()).toEqual([new Date(2026, 10, 1), new Date(2026, 11, 1)])
      await click(wrapper, 'button[aria-label="Previous"]')
      await click(wrapper, 'button[aria-label="Previous"]')
      expect(lastRange()).toEqual([new Date(2026, 8, 1), new Date(2026, 9, 1)])
      await click(wrapper, 'button[aria-label="Next year"]')
      expect(lastRange()).toEqual([new Date(2027, 8, 1), new Date(2027, 9, 1)])
      await clickText(wrapper, 'Today')
      expect(lastRange()).toEqual([new Date(2026, 9, 1), new Date(2026, 10, 1)])
      expect(wrapper.get('.toolbar-title').text()).toBe('October 2026')
    })

    it('opens and adds events from the list', async () => {
      events = [occurrence({ event_id: 'e5' })]
      const wrapper = await open('/calendar/work?view=list')
      await click(wrapper, '.agenda-entry')
      expect(modal(wrapper).props('eventId')).toBe('e5')
      await click(wrapper, '.modal-cancel')
      await clickText(wrapper, 'New event')
      expect(modal(wrapper).props()).toMatchObject({ eventId: null, defaultStart: new Date(2026, 9, 14) })

      // Saved, the month is loaded again.
      const before = eventRequests().length
      await click(wrapper, '.modal-save')
      expect(eventRequests()).toHaveLength(before + 1)
    })

    it('switches to the month or week the list showed', async () => {
      const wrapper = await open('/calendar/all?view=list&date=2026-12')
      await clickText(wrapper, 'Month')
      expect(fullCalendar.mounts).toBe(1)
      expect(fullCalendar.view!.currentStart).toEqual(new Date(2026, 11, 1))

      await clickText(wrapper, 'List')
      expect(wrapper.find('.calendar-agenda').exists()).toBe(true)
      expect(lastRange()).toEqual([new Date(2026, 11, 1), new Date(2027, 0, 1)])

      // From the month with today in it, the week of today.
      await clickText(wrapper, 'Today')
      await clickText(wrapper, 'Week')
      expect(fullCalendar.view).toMatchObject({ type: 'timeGridWeek', currentStart: new Date(2026, 9, 12) })
    })

    it('follows links while the list is open', async () => {
      const wrapper = await open('/calendar/all?view=list')
      await router.push('/calendar/all?view=list&date=2027-03')
      await flushPromises()
      expect(lastRange()).toEqual([new Date(2027, 2, 1), new Date(2027, 3, 1)])

      await router.push('/calendar/all?view=week&date=2027-03-10')
      await flushPromises()
      expect(wrapper.find('.calendar-agenda').exists()).toBe(false)
      expect(fullCalendar.view).toMatchObject({ type: 'timeGridWeek', currentStart: new Date(2027, 2, 8) })

      await router.push('/calendar/all?view=list')
      await flushPromises()
      expect(wrapper.find('.calendar-agenda').exists()).toBe(true)
    })

    it('loads the month again when the selection changes', async () => {
      await open('/calendar/all?view=list')
      await router.push('/calendar/work?view=list')
      await flushPromises()
      expect(eventRequests().at(-1)).toEqual({
        ids: ['c1'],
        start: new Date(2026, 9, 1),
        end: new Date(2026, 10, 1),
      })
    })
  })

  describe('the week on phones', () => {
    it('stacks the days of the week and steps by weeks', async () => {
      events = [occurrence({ event_id: 'e1', title: 'Standup' })]
      const wrapper = await open('/calendar/work?view=week', { phone: true })
      expect(fullCalendar.mounts).toBe(0)
      expect(wrapper.findAll('.week-stack-day')).toHaveLength(7)
      expect(lastRange()).toEqual([new Date(2026, 9, 12), new Date(2026, 9, 19)])
      expect(wrapper.get('.toolbar-title').text()).toMatch(/Oct 12.*18.*2026/)

      await click(wrapper, 'button[aria-label="Next"]')
      expect(lastRange()).toEqual([new Date(2026, 9, 19), new Date(2026, 9, 26)])
      await click(wrapper, 'button[aria-label="Previous"]')
      await click(wrapper, 'button[aria-label="Previous"]')
      expect(lastRange()).toEqual([new Date(2026, 9, 5), new Date(2026, 9, 12)])
      await clickText(wrapper, 'Today')
      expect(lastRange()).toEqual([new Date(2026, 9, 12), new Date(2026, 9, 19)])
      await click(wrapper, 'button[aria-label="Next year"]')
      expect(lastRange()).toEqual([new Date(2027, 9, 11), new Date(2027, 9, 18)])
    })

    it('opens and adds events from the stacked week', async () => {
      events = [occurrence({ event_id: 'e1' })]
      const wrapper = await open('/calendar/work?view=week', { phone: true })
      await click(wrapper, '.week-stack-event')
      expect(modal(wrapper).props('eventId')).toBe('e1')
      await click(wrapper, '.modal-cancel')
      await click(wrapper, '.week-stack-date')
      expect(modal(wrapper).props()).toMatchObject({ eventId: null, defaultStart: new Date(2026, 9, 12) })
      const before = eventRequests().length
      await click(wrapper, '.modal-save')
      expect(eventRequests()).toHaveLength(before + 1)
    })

    it('stacks the week chosen on a phone, and leaves it for the month or the list', async () => {
      const wrapper = await open('/calendar/all', { phone: true })
      await clickText(wrapper, 'Week')
      expect(wrapper.find('.week-stack').exists()).toBe(true)
      await clickText(wrapper, 'List')
      expect(wrapper.find('.calendar-agenda').exists()).toBe(true)
      await clickText(wrapper, 'Week')
      expect(wrapper.find('.week-stack').exists()).toBe(true)
      await clickText(wrapper, 'Month')
      expect(fullCalendar.view).toMatchObject({ type: 'dayGridMonth', currentStart: new Date(2026, 9, 1) })
    })

    it('follows links while the week is stacked', async () => {
      const wrapper = await open('/calendar/all?view=week', { phone: true })
      await router.push('/calendar/all?view=week&date=2026-11-04')
      await flushPromises()
      expect(lastRange()).toEqual([new Date(2026, 10, 2), new Date(2026, 10, 9)])
      await router.push('/calendar/all?view=list')
      await flushPromises()
      expect(wrapper.find('.calendar-agenda').exists()).toBe(true)
      await router.push('/calendar/all?view=week')
      await flushPromises()
      expect(wrapper.find('.week-stack').exists()).toBe(true)
    })

    it('keeps the week when the screen crosses the phone breakpoint', async () => {
      const wrapper = await open('/calendar/all?view=week')
      expect(fullCalendar.view!.type).toBe('timeGridWeek')
      media.set(PHONE, true)
      await flushPromises()
      expect(wrapper.find('.week-stack').exists()).toBe(true)
      media.set(PHONE, false)
      await flushPromises()
      expect(wrapper.find('.week-stack').exists()).toBe(false)
      expect(fullCalendar.view).toMatchObject({ type: 'timeGridWeek', currentStart: new Date(2026, 9, 12) })

      // The month stays a month.
      await clickText(wrapper, 'Month')
      media.set(PHONE, true)
      await flushPromises()
      expect(wrapper.find('.week-stack').exists()).toBe(false)
    })

    it('loads the week again when the selection changes', async () => {
      await open('/calendar/all?view=week', { phone: true })
      await router.push('/calendar/work?view=week')
      await flushPromises()
      expect(eventRequests().at(-1)).toEqual({
        ids: ['c1'],
        start: new Date(2026, 9, 12),
        end: new Date(2026, 9, 19),
      })
    })
  })
})
