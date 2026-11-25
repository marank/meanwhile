import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DOMWrapper, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { fakeBackend, reply, type FakeBackend, type FakeRequest } from '@/__tests__/fakeBackend'
import type * as api from '@/api'
import { i18n } from '@/i18n'
import { browserTimeZone, toDateInputValue, toTimeInputValue } from '@/services/datetime'
import { dialog, submitDialog } from '@/services/dialog'
import type { OccurrenceRef } from '@/services/occurrences'
import EventModal from '../EventModal.vue'
import { useCalendarStore } from '@/stores/calendars'
import { calendarItem } from '@/components/calendar/__tests__/calendarFixtures'
import { calendar, event, me, participant, signIn } from './helpers'

const search = (id: string, label: string, type: string, meta: Record<string, unknown> | null = null) => ({
  id,
  type,
  label,
  subtitle: null,
  meta,
})

const searchResults: Record<string, api.SearchResult[]> = {
  locations: [search('l1', 'Main hall', 'resource', { requires_approval: true })],
  categories: [search('k1', 'Meeting', 'category', { color: '#00f' })],
  resources: [search('r1', 'Beamer', 'resource', { requires_approval: true }), search('r2', 'Flipchart', 'resource')],
  users: [],
}

let backend: FakeBackend
let wrapper: VueWrapper

/** The server of a calendar `cal1` with the event `ev1` in it. */
function serve(cal: api.Calendar = calendar(), ev: api.Event = event(), extra: Record<string, unknown> = {}) {
  backend = fakeBackend({
    'GET /api/calendars/cal1': cal,
    'GET /api/events/ev1': ev,
    'GET /api/events/ev1/reminders': { minutes: [] },
    'GET /api/events/ev1/participants': [],
    'GET /api/events/ev1/attachments': [],
    'GET /api/search': (request: FakeRequest) => searchResults[request.query.get('entity')!] ?? [],
    'POST /api/availability': { users: [], resources: [] },
    ...extra,
  })
  return backend
}

interface Props {
  calendarId?: string
  eventId?: string | null
  occurrence?: OccurrenceRef | null
  defaultStart?: Date
  defaultEnd?: Date
  defaultAllDay?: boolean
}

async function open(props: Props) {
  wrapper = mount(EventModal, { props, global: { plugins: [i18n] }, attachTo: document.body })
  await flushPromises()
  return wrapper
}

const openNew = (props: Props = {}) =>
  open({ calendarId: 'cal1', defaultStart: new Date('2026-03-10T09:00'), ...props })
const openExisting = (props: Props = {}) => open({ eventId: 'ev1', ...props })

// The dialog lives in <body>.
const page = () => new DOMWrapper(document.body)
const text = () => document.body.textContent.replace(/\s+/g, ' ')
const button = (label: string) =>
  page()
    .findAll('button')
    .find((b) => b.text() === label)
const tab = (label: string) =>
  page()
    .findAll('[role="tab"]')
    .find((b) => b.text() === label)
const tabs = () =>
  page()
    .findAll('[role="tab"]')
    .map((b) => b.text())
/** The input of a field by its label. */
function field(label: string) {
  const labelEl = page()
    .findAll('label')
    .find((l) => l.text().startsWith(label))!
  const forId = labelEl.attributes('for')
  return forId ? page().get(`[id="${forId}"]`) : labelEl.get('input, textarea')
}
const timeField = (label: string) => page().get(`input[aria-label="${label} (time)"]`)
const alertText = () => page().find('[role="alert"]').text()

async function click(label: string) {
  await button(label)!.trigger('click')
  await flushPromises()
}

async function answerDialog(value: unknown) {
  await flushPromises()
  submitDialog(value)
  await flushPromises()
}

async function chooseOption(label: string, optionLabel: string) {
  await field(label).trigger('focus')
  await flushPromises()
  const option = [...document.querySelectorAll<HTMLElement>('[role="option"]')].find((o) =>
    o.textContent.includes(optionLabel),
  )!
  option.dispatchEvent(new MouseEvent('mouseup'))
  await flushPromises()
}

const body = (pattern: string, index = 0) => backend.calls(pattern)[index]!.body as Record<string, unknown>

describe('EventModal', () => {
  beforeEach(() => {
    signIn()
    // Searches wait for a pause in typing.
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
  })

  afterEach(() => {
    wrapper.unmount()
    vi.useRealTimers()
    if (dialog.open) submitDialog(null)
    vi.restoreAllMocks()
  })

  describe('a new event', () => {
    it('starts at the time picked in the calendar and lasts an hour', async () => {
      serve()
      await openNew()
      expect(page().get('h3').text()).toBe('Add event')
      expect(tabs()).toEqual(['Details', 'Recurrence', 'Reminders', 'Participants', 'Attachments', 'Availability'])
      expect((field('Start').element as HTMLInputElement).value).toBe('2026-03-10')
      expect((timeField('Start').element as HTMLInputElement).value).toBe('09:00')
      expect((field('End').element as HTMLInputElement).value).toBe('2026-03-10')
      expect((timeField('End').element as HTMLInputElement).value).toBe('10:00')
      expect(button('Delete')).toBeUndefined()
      // The day is loaded for the availability tab in advance, with oneself on it.
      expect(body('POST /api/availability').user_ids).toEqual([me.id])
    })

    it('is created in the calendar with what was entered', async () => {
      serve(calendar(), event(), {
        'POST /api/calendars/cal1/events': event({ id: 'new1' }),
      })
      await openNew({ defaultEnd: new Date('2026-03-10T11:30') })
      await field('Title').setValue('Retro')
      await field('Description').setValue('How did it go?')
      await chooseOption('Category', 'Meeting')
      await click('Save')
      expect(body('POST /api/calendars/cal1/events')).toEqual({
        title: 'Retro',
        description: 'How did it go?',
        start: new Date('2026-03-10T09:00').toISOString(),
        end: new Date('2026-03-10T11:30').toISOString(),
        all_day: false,
        timezone: browserTimeZone(),
        show_recurrence_count: false,
        rrule: null,
        category_id: 'k1',
        resource_id: null,
        location: null,
        location_resource_id: null,
        show_as: 'busy',
        participants: [],
      })
      // Reminders unchanged: nothing more to save.
      expect(backend.calls('PUT /api/events/new1/reminders')).toHaveLength(0)
      expect(wrapper.emitted('saved')).toHaveLength(1)
    })

    it('stores all-day events as whole UTC days', async () => {
      serve(calendar(), event(), { 'POST /api/calendars/cal1/events': event() })
      await openNew({ defaultAllDay: true, defaultEnd: new Date('2026-03-12T00:00') })
      expect(page().find('input[type="time"]').exists()).toBe(false)
      await click('Save')
      expect(body('POST /api/calendars/cal1/events')).toMatchObject({
        all_day: true,
        start: '2026-03-10T00:00:00.000Z',
        end: '2026-03-12T00:00:00.000Z',
      })
    })

    it('can be switched to all day, unless the calendar allows only that', async () => {
      serve()
      await openNew()
      await page().get('[role="switch"]').trigger('click')
      expect(page().find('input[type="time"]').exists()).toBe(false)
      wrapper.unmount()

      serve(calendar('owner', { force_all_day: true }))
      await openNew()
      expect(page().get('[role="switch"]').attributes('disabled')).toBeDefined()
      expect(page().get('[role="switch"]').attributes('aria-checked')).toBe('true')
      expect(text()).toContain('This calendar only allows all-day events.')
    })

    it('does not save an end before the start', async () => {
      serve()
      await openNew()
      await timeField('End').setValue('08:00')
      expect(alertText()).toBe('The end must not be before the start.')
      expect(button('Save')!.attributes('disabled')).toBeDefined()
      await button('Save')!.trigger('click')
      await page().get('[role="switch"]').trigger('click')
      await field('End').setValue('2026-03-09')
      expect(alertText()).toBe('The end must not be before the start.')
      await field('End').setValue('2026-03-10')
      expect(page().find('[role="alert"]').exists()).toBe(false)
      expect(backend.calls('POST /api/calendars/cal1/events')).toHaveLength(0)
    })

    it('moves the end along with the start, keeping the duration', async () => {
      serve()
      await openNew()
      await timeField('Start').setValue('14:30')
      expect((timeField('End').element as HTMLInputElement).value).toBe('15:30')
      expect(page().find('[role="alert"]').exists()).toBe(false)
      await timeField('End').setValue('17:00')
      await timeField('Start').setValue('23:00')
      expect((field('End').element as HTMLInputElement).value).toBe('2026-03-11')
      expect((timeField('End').element as HTMLInputElement).value).toBe('01:30')
      // An end set before the start: a new start gets an hour.
      await field('End').setValue('2026-03-10')
      await timeField('End').setValue('08:00')
      await timeField('Start').setValue('10:00')
      expect((field('End').element as HTMLInputElement).value).toBe('2026-03-10')
      expect((timeField('End').element as HTMLInputElement).value).toBe('11:00')
      await page().get('[role="switch"]').trigger('click')
      await field('End').setValue('2026-03-12')
      await field('Start').setValue('2026-03-20')
      expect((field('End').element as HTMLInputElement).value).toBe('2026-03-22')
    })

    it('takes typed text as the place, and a picked place as a booking', async () => {
      serve(calendar(), event(), {
        'POST /api/calendars/cal1/events': event(),
        'PATCH /api/events/ev1': event(),
      })
      await openNew()
      await field('Location').setValue('Garden')
      await click('Save')
      expect(body('POST /api/calendars/cal1/events')).toMatchObject({ location: 'Garden', location_resource_id: null })

      await field('Location').setValue('')
      await chooseOption('Location', 'Main hall')
      expect(text()).toContain('Approval required')
      await chooseOption('Resource', 'Beamer')
      expect(
        page()
          .findAll('span')
          .filter((s) => s.text() === 'Approval required'),
      ).toHaveLength(2)
      // Saved again, the dialog changes the event it created.
      await click('Save')
      expect(body('PATCH /api/events/ev1')).toMatchObject({
        location: 'Main hall',
        location_resource_id: 'l1',
        resource_id: 'r1',
      })
    })

    it('sends the participants added along with it', async () => {
      serve(calendar(), event(), { 'POST /api/calendars/cal1/events': event({ id: 'new1' }) })
      searchResults.users = [{ id: 'u5', type: 'user', label: 'Dora', subtitle: 'dora@example.com', meta: null }]
      await openNew()
      await tab('Participants')!.trigger('click')
      const input = page().get('input[role="combobox"]')
      await input.setValue('Dora')
      await vi.advanceTimersByTimeAsync(200)
      await flushPromises()
      await input.trigger('keydown', { key: 'ArrowDown' })
      await input.trigger('keydown', { key: 'Enter' })
      await flushPromises()
      expect(text()).toContain('dora@example.com')

      // Their availability is shown, too.
      await tab('Availability')!.trigger('click')
      await flushPromises()
      expect(backend.calls('POST /api/availability').at(-1)!.body).toMatchObject({ user_ids: [me.id, 'u5'] })

      await click('Save')
      expect(body('POST /api/calendars/cal1/events').participants).toEqual([
        { user_id: 'u5', email: 'dora@example.com', status: 'needs_action' },
      ])
      searchResults.users = []
    })

    it('saves its reminders once created, and is not created twice when that fails', async () => {
      serve(calendar(), event(), {
        'POST /api/calendars/cal1/events': event({ id: 'new1' }),
        'PUT /api/events/new1/reminders': reply(500, { detail: 'Reminders down' }),
        'PATCH /api/events/new1': event({ id: 'new1' }),
      })
      await openNew()
      await tab('Reminders')!.trigger('click')
      await button('Add reminder')!.trigger('click')
      await click('Save')
      expect(alertText()).toBe('Reminders down')
      expect(wrapper.emitted('saved')).toBeUndefined()

      backend.on('PUT /api/events/new1/reminders', { minutes: [15] })
      await click('Save')
      expect(backend.calls('POST /api/calendars/cal1/events')).toHaveLength(1)
      expect(backend.calls('PATCH /api/events/new1')).toHaveLength(1)
      expect(body('PUT /api/events/new1/reminders', 1)).toEqual({ minutes: expect.any(Array) })
      expect(wrapper.emitted('saved')).toHaveLength(1)
    })

    it('explains a booking conflict', async () => {
      serve(calendar(), event(), { 'POST /api/calendars/cal1/events': reply(409, { detail: 'conflict' }) })
      await openNew()
      await click('Save')
      expect(alertText()).toBe('This time slot is already booked for this resource.')
    })

    it('saves with a recurrence', async () => {
      serve(calendar(), event(), { 'POST /api/calendars/cal1/events': event() })
      await openNew()
      await tab('Recurrence')!.trigger('click')
      const repeat = page().get('[role="combobox"]')
      await repeat.trigger('click')
      document
        .getElementById(repeat.attributes('aria-controls')!)!
        .querySelectorAll<HTMLElement>('[role="option"]')[1]!
        .click()
      await flushPromises()
      await page().get('input[type="checkbox"]').setValue(true)
      await click('Save')
      expect(body('POST /api/calendars/cal1/events')).toMatchObject({
        rrule: 'FREQ=DAILY',
        show_recurrence_count: true,
      })
    })

    it('opens with its form, the title field focused', async () => {
      serve()
      wrapper = mount(EventModal, {
        props: { calendarId: 'cal1', defaultStart: new Date('2026-03-10T09:00') },
        global: { plugins: [i18n] },
        attachTo: document.body,
      })
      // Not shown with only "Loading…" in it while the calendar is on its way.
      expect(page().find('[role="dialog"]').exists()).toBe(false)
      await flushPromises()
      expect(page().find('[role="dialog"]').exists()).toBe(true)
      expect(document.activeElement).toBe(field('Title').element)
    })

    it('shows that it is loading when the calendar takes a while, then focuses the title', async () => {
      let answer: (value: api.Calendar) => void = () => {}
      serve(calendar(), event(), {
        'GET /api/calendars/cal1': () => new Promise<api.Calendar>((resolve) => (answer = resolve)),
      })
      await openNew()
      expect(page().find('[role="dialog"]').exists()).toBe(false)
      vi.advanceTimersByTime(300)
      await flushPromises()
      expect(text()).toContain('Loading…')
      answer(calendar())
      await flushPromises()
      expect(document.activeElement).toBe(field('Title').element)
    })

    it('waits for a calendar to put it in', async () => {
      const backend = serve()
      await open({})
      vi.advanceTimersByTime(300)
      await flushPromises()
      expect(text()).toContain('Loading…')
      expect(backend.requests.filter((r) => r.path !== '/api/search')).toHaveLength(0)
    })
  })

  describe('show as', () => {
    const showAs = () => page().get('label:has([role="combobox"]) [role="combobox"]')
    /** It belongs to who takes part, so it is under "Participants", not with the details. */
    async function openParticipants() {
      expect(page().find('label:has([role="combobox"])').exists()).toBe(false)
      await tab('Participants')!.trigger('click')
      await flushPromises()
    }
    async function pickShowAs(label: string) {
      await showAs().trigger('click')
      const list = document.getElementById(showAs().attributes('aria-controls')!)!
      ;[...list.querySelectorAll<HTMLElement>('[role="option"]')].find((o) => o.textContent.trim() === label)!.click()
      await flushPromises()
    }

    it('starts as busy and offers Outlook’s choices in its order', async () => {
      serve()
      await openNew()
      await openParticipants()
      expect(showAs().text()).toBe('Busy')
      expect(text()).toContain('Free and working elsewhere don’t count as busy')
      await showAs().trigger('click')
      const list = document.getElementById(showAs().attributes('aria-controls')!)!
      expect([...list.querySelectorAll('[role="option"]')].map((o) => o.textContent.trim())).toEqual([
        'Free',
        'Working elsewhere',
        'Tentative',
        'Busy',
        'Out of office',
      ])
    })

    it('is sent with a new event', async () => {
      serve(calendar(), event(), { 'POST /api/calendars/cal1/events': event({ id: 'new1' }) })
      await openNew()
      await openParticipants()
      await pickShowAs('Out of office')
      await click('Save')
      expect(body('POST /api/calendars/cal1/events').show_as).toBe('out_of_office')
    })

    it('shows what an event was saved with and sends a change', async () => {
      serve(calendar(), event({ show_as: 'free' }), { 'PATCH /api/events/ev1': event() })
      await openExisting()
      await openParticipants()
      expect(showAs().text()).toBe('Free')
      await pickShowAs('Tentative')
      await click('Save')
      expect(body('PATCH /api/events/ev1').show_as).toBe('tentative')
    })

    it('can’t be changed without the right to change the event', async () => {
      serve(calendar('read'), event({ creator_id: 'someone-else', show_as: 'working_elsewhere' }))
      await openExisting()
      await openParticipants()
      expect(showAs().text()).toBe('Working elsewhere')
      // Inside the dialog's disabled fieldset, as every field of the event.
      expect(showAs().element.matches(':disabled')).toBe(true)
    })
  })

  describe('categories and resources', () => {
    /** The search answers with nothing for the entities left out of `found`. */
    const searchOnly = (...found: string[]) => ({
      'GET /api/search': (request: FakeRequest) => {
        const entity = request.query.get('entity')!
        return found.includes(entity) ? (searchResults[entity] ?? []) : []
      },
    })
    const labels = () =>
      page()
        .findAll('label')
        .map((l) => l.text())

    it('come last, after title, time, place and description', async () => {
      serve()
      await openNew()
      expect(labels()).toEqual(['Title', 'Start', 'End', 'Location', 'Description', 'Category', 'Resource'])
    })

    it('leaves out their fields when the calendar has none', async () => {
      serve(calendar(), event(), searchOnly('locations'))
      await openNew()
      expect(labels()).not.toContain('Category')
      expect(labels().some((l) => l.startsWith('Resource'))).toBe(false)
      expect(labels()).toContain('Location')
      const asked = backend.calls('GET /api/search').filter((c) => c.query.get('limit') === '1')
      expect(asked.map((c) => [c.query.get('entity'), c.query.get('calendar_id')])).toEqual([
        ['categories', 'cal1'],
        ['resources', 'cal1'],
      ])
    })

    it('shows only the field of what there is', async () => {
      serve(calendar(), event(), searchOnly('categories'))
      await openNew()
      expect(labels()).toContain('Category')
      expect(labels().some((l) => l.startsWith('Resource'))).toBe(false)

      wrapper.unmount()
      serve(calendar(), event(), searchOnly('resources'))
      await openNew()
      expect(labels()).not.toContain('Category')
      await chooseOption('Resource', 'Beamer')
      await click('Save')
      expect(backend.calls('POST /api/calendars/cal1/events')[0]!.body).toMatchObject({ resource_id: 'r1' })
    })

    it('keeps showing what an event has, though the calendar offers it no longer', async () => {
      serve(calendar(), event({ category_id: 'k1', resource_id: 'r2' }), searchOnly())
      await openExisting()
      expect(labels()).toContain('Category')
      expect(labels().some((l) => l.startsWith('Resource'))).toBe(true)
    })

    it('shows both when it cannot tell', async () => {
      serve(calendar(), event(), { 'GET /api/search': reply(500) })
      await openNew()
      expect(labels()).toContain('Category')
      expect(labels().some((l) => l.startsWith('Resource'))).toBe(true)
    })
  })

  describe('an existing event', () => {
    it('shows what was saved, and who created and changed it', async () => {
      serve(
        calendar(),
        event({
          location: 'Garden',
          category_id: 'k1',
          resource_id: 'r2',
          updated_at: '2026-03-02T08:00:00.000Z',
        }),
      )
      await openExisting()
      const start = new Date('2026-03-10T09:00:00.000Z')
      expect(page().get('h3').text()).toBe('Edit event')
      expect(tabs()).toContain('Activity')
      expect((field('Title').element as HTMLInputElement).value).toBe('Planning')
      expect((field('Description').element as HTMLTextAreaElement).value).toBe('Agenda')
      expect((field('Location').element as HTMLInputElement).value).toBe('Garden')
      expect((field('Category').element as HTMLInputElement).value).toBe('Meeting')
      expect((field('Resource').element as HTMLInputElement).value).toBe('Flipchart')
      expect((field('Start').element as HTMLInputElement).value).toBe(toDateInputValue(start))
      expect((timeField('Start').element as HTMLInputElement).value).toBe(toTimeInputValue(start))
      expect(text()).toContain('Created by Me Myself on 2026-03-01')
      expect(text()).toContain('Edited on 2026-03-02')
      // With a resource, it is a booking and shows its status.
      expect(page().get('[data-modal-header] [role="status"]').text()).toBe('Approved')
    })

    it('saves changes, participants and reminders', async () => {
      serve(calendar(), event({ creator_name: null }), {
        'GET /api/events/ev1/reminders': { minutes: [60] },
        'GET /api/events/ev1/participants': [
          participant(),
          participant({ id: 'p2', user_id: null, email: 'ben@example.com' }),
        ],
        'PATCH /api/events/ev1': event(),
        'DELETE /api/events/ev1/participants/*': undefined,
        'POST /api/events/ev1/participants': participant({ id: 'p3' }),
        'PUT /api/events/ev1/reminders': { minutes: [] },
      })
      await openExisting()
      expect(text()).toContain('Created by me@example.com')
      // The participants with an account are on the availability.
      expect(body('POST /api/availability')).toMatchObject({ user_ids: [me.id, 'u1'], exclude_event_id: 'ev1' })

      await field('Title').setValue('Planning (moved)')
      await tab('Participants')!.trigger('click')
      const anna = page()
        .findAll('li')
        .find((li) => li.text().includes('anna@example.com'))!
      await anna.get('button').trigger('click')
      const input = page().get('input[role="combobox"]')
      await input.setValue('cleo@example.com')
      await vi.advanceTimersByTimeAsync(200)
      await flushPromises()
      await input.trigger('keydown', { key: 'Enter' })
      await flushPromises()

      await tab('Reminders')!.trigger('click')
      await page().get('button[aria-label="Remove reminder"]').trigger('click')
      await click('Save')

      expect(body('PATCH /api/events/ev1')).toMatchObject({
        title: 'Planning (moved)',
        start: '2026-03-10T09:00:00.000Z',
        end: '2026-03-10T10:00:00.000Z',
      })
      expect(backend.calls('DELETE /api/events/ev1/participants/p1')).toHaveLength(1)
      expect(body('POST /api/events/ev1/participants')).toEqual({ email: 'cleo@example.com', status: 'needs_action' })
      expect(body('PUT /api/events/ev1/reminders')).toEqual({ minutes: [] })
      expect(wrapper.emitted('saved')).toHaveLength(1)
    })

    it('shows all-day events on their calendar dates', async () => {
      serve(calendar(), event({ all_day: true, start: '2026-03-10T00:00:00.000Z', end: '2026-03-11T00:00:00.000Z' }), {
        'PATCH /api/events/ev1': event(),
      })
      await openExisting()
      expect((field('Start').element as HTMLInputElement).value).toBe('2026-03-10')
      expect((field('End').element as HTMLInputElement).value).toBe('2026-03-11')
      await tab('Availability')!.trigger('click')
      await flushPromises()
      expect(text()).toContain('2026-03-10')
      await click('Save')
      expect(body('PATCH /api/events/ev1')).toMatchObject({
        start: '2026-03-10T00:00:00.000Z',
        end: '2026-03-11T00:00:00.000Z',
      })
    })

    it('reports when it cannot be loaded', async () => {
      serve(calendar(), event(), { 'GET /api/events/ev1': reply(404, { detail: 'Not found.' }) })
      await openExisting()
      expect(alertText()).toBe('Not found.')
      expect(text()).not.toContain('Loading…')
      expect(button('Save')!.attributes('disabled')).toBeDefined()
    })

    it('still opens when its reminders and participants cannot be loaded', async () => {
      serve(calendar(), event(), {
        'GET /api/events/ev1/reminders': reply(500),
        'GET /api/events/ev1/participants': reply(500),
      })
      await openExisting()
      await tab('Participants')!.trigger('click')
      expect(text()).toContain('No participants yet.')
    })

    it('is deleted after confirming', async () => {
      serve(calendar(), event(), { 'DELETE /api/events/ev1': undefined })
      await openExisting()
      await click('Delete')
      expect(dialog.message).toBe('This cannot be undone.')
      await answerDialog(false)
      expect(backend.calls('DELETE /api/events/ev1')).toHaveLength(0)

      await click('Delete')
      await answerDialog(true)
      expect(backend.calls('DELETE /api/events/ev1')).toHaveLength(1)
      expect(wrapper.emitted('deleted')).toHaveLength(1)
    })

    it('loads the activity once, when first opened', async () => {
      serve(calendar(), event(), {
        'GET /api/events/ev1/comments': [],
        'GET /api/events/ev1/activity': [],
      })
      await openExisting()
      expect(backend.calls('GET /api/events/ev1/activity')).toHaveLength(0)
      await tab('Activity')!.trigger('click')
      await flushPromises()
      expect(text()).toContain('No activity yet.')
      await tab('Details')!.trigger('click')
      await tab('Activity')!.trigger('click')
      await flushPromises()
      expect(backend.calls('GET /api/events/ev1/activity')).toHaveLength(1)
    })

    it('closes without saving', async () => {
      serve()
      await openExisting()
      // Without a resource, it is no booking and has no status.
      expect(page().find('[data-modal-header] [role="status"]').exists()).toBe(false)
      await click('Cancel')
      await page().get('button[aria-label="Close"]').trigger('click')
      expect(wrapper.emitted('cancel')).toHaveLength(2)
      expect(backend.requests.filter((r) => r.method !== 'GET' && r.path !== '/api/availability')).toHaveLength(0)
    })
  })

  describe('without the right to change it', () => {
    it('lets readers set only their own reminders', async () => {
      serve(calendar('read'), event({ creator_id: 'u1' }), {
        'GET /api/events/ev1/comments': [],
        'GET /api/events/ev1/activity': [],
        'PUT /api/events/ev1/reminders': { minutes: [15] },
      })
      await openExisting()
      expect(page().get('fieldset').attributes('disabled')).toBeDefined()
      expect(button('Delete')).toBeUndefined()
      expect(button('Save')).toBeUndefined()
      // Readers may not comment either.
      await tab('Activity')!.trigger('click')
      await flushPromises()
      expect(page().find('textarea[placeholder="Write a comment…"]').exists()).toBe(false)

      await tab('Reminders')!.trigger('click')
      await button('Add reminder')!.trigger('click')
      await click('Save')
      expect(backend.calls('PUT /api/events/ev1/reminders')).toHaveLength(1)
      expect(backend.calls('PATCH /api/events/ev1')).toHaveLength(0)
      expect(wrapper.emitted('saved')).toHaveLength(1)
    })

    it('lets those with access to their own events change only those', async () => {
      serve(calendar('own'), event({ creator_id: 'u1' }))
      await openExisting()
      expect(page().get('fieldset').attributes('disabled')).toBeDefined()
      wrapper.unmount()

      serve(calendar('own'), event())
      await openExisting()
      expect(page().get('fieldset').attributes('disabled')).toBeUndefined()
      expect(button('Delete')).toBeDefined()
    })
  })

  describe('attachments', () => {
    const saved: api.Attachment = {
      id: 'a1',
      kind: 'file',
      name: 'Agenda.pdf',
      url: '/api/attachments/a1/download',
      content_type: 'application/pdf',
      size: 2048,
      added_by_name: 'Anna',
      created_at: '2026-03-01T08:00:00Z',
    }

    it('shows those of the event and sends what was added and removed with the event', async () => {
      serve(calendar(), event(), {
        'GET /api/events/ev1/attachments': [saved],
        'PATCH /api/events/ev1': event(),
        'DELETE /api/events/ev1/attachments/a1': undefined,
        'POST /api/events/ev1/attachments/links': { ...saved, id: 'a2', kind: 'link' },
      })
      await openExisting()
      await tab('Attachments')!.trigger('click')
      await flushPromises()
      expect(page().get('li[data-kind="file"] a').attributes('href')).toBe('/api/attachments/a1/download')
      await page().get('button[aria-label="Remove Agenda.pdf"]').trigger('click')
      const [url] = page().findAll('form input')
      await url!.setValue('https://example.org/plan')
      await page().get('form').trigger('submit')
      // Nothing is sent before the event is saved.
      expect(backend.calls('DELETE /api/events/ev1/attachments/a1')).toHaveLength(0)
      await click('Save')
      expect(backend.calls('DELETE /api/events/ev1/attachments/a1')).toHaveLength(1)
      expect(body('POST /api/events/ev1/attachments/links')).toEqual({
        url: 'https://example.org/plan',
        name: 'https://example.org/plan',
      })
      expect(wrapper.emitted('saved')).toHaveLength(1)
    })

    it('are sent once a new event is created', async () => {
      serve(calendar(), event(), {
        'POST /api/calendars/cal1/events': event({ id: 'new1' }),
        'POST /api/events/new1/attachments/links': { ...saved, kind: 'link' },
      })
      await openNew()
      await tab('Attachments')!.trigger('click')
      await page().findAll('form input')[0]!.setValue('https://example.org/plan')
      await page().get('form').trigger('submit')
      await click('Save')
      expect(backend.calls('POST /api/events/new1/attachments/links')).toHaveLength(1)
      expect(wrapper.emitted('saved')).toHaveLength(1)
    })

    it('can only be looked at without the right to change the event', async () => {
      serve(calendar('read'), event({ creator_id: 'u1' }), { 'GET /api/events/ev1/attachments': [saved] })
      await openExisting()
      await tab('Attachments')!.trigger('click')
      expect(page().get('li[data-kind="file"] a').text()).toBe('Agenda.pdf')
      expect(page().find('input[type="file"]').exists()).toBe(false)
    })
  })

  describe('duplicating', () => {
    function mayAddTo(...calendars: [string, api.CalendarRole][]) {
      useCalendarStore().items = calendars.map(([id, role]) =>
        calendarItem(id, { role, calendar: { name: `Cal ${id}` } }),
      )
    }
    const dialogTitle = () =>
      page()
        .findAll('h3')
        .map((h) => h.text())
    const duplicateButton = () =>
      page()
        .findAll('button')
        .filter((b) => b.text() === 'Duplicate')

    it('is offered for saved events where one may add events somewhere', async () => {
      serve()
      mayAddTo(['cal1', 'read'])
      await openExisting()
      expect(duplicateButton()).toHaveLength(0)
      wrapper.unmount()

      serve()
      mayAddTo(['cal1', 'read'], ['mine', 'own'])
      await openNew()
      expect(duplicateButton()).toHaveLength(0)
      wrapper.unmount()

      serve(calendar('read'), event({ creator_id: 'u1' }))
      mayAddTo(['cal1', 'read'], ['mine', 'own'])
      await openExisting()
      // A reader copies into a calendar of their own.
      expect(duplicateButton()).toHaveLength(1)
    })

    it('copies the event to the day and calendar chosen and hands the copy on', async () => {
      const copy = event({ id: 'copy1', calendar_id: 'mine' })
      serve(calendar(), event(), { 'POST /api/events/ev1/duplicate': copy })
      mayAddTo(['cal1', 'owner'], ['mine', 'own'], ['theirs', 'read'])
      await openExisting()
      await duplicateButton()[0]!.trigger('click')
      expect(dialogTitle()).toContain('Duplicate event')
      // The calendar the event is in, among those one may add to.
      const select = page().get('#duplicate-event [role="combobox"]')
      expect(select.text()).toBe('Cal cal1')
      await select.trigger('click')
      const list = document.getElementById(select.attributes('aria-controls')!)!
      const options = [...list.querySelectorAll<HTMLElement>('[role="option"]')]
      expect(options.map((o) => o.textContent.trim())).toEqual(['Cal cal1', 'Cal mine'])
      options[1]!.click()
      await flushPromises()
      expect(text()).toContain('Resources stay behind')

      const date = page().get<HTMLInputElement>('#duplicate-event input[type="date"]')
      expect(date.element.value).toBe('2026-03-10')
      await date.setValue('2026-03-24')
      await page().get('#duplicate-event').trigger('submit')
      await flushPromises()
      expect(body('POST /api/events/ev1/duplicate')).toEqual({
        calendar_id: 'mine',
        start: new Date(`2026-03-24T${toTimeInputValue(new Date('2026-03-10T09:00:00.000Z'))}`).toISOString(),
        invite_participants: false,
      })
      expect(wrapper.emitted('duplicated')).toEqual([[copy]])
    })

    it('copies all-day events by their date, and asks about participants when there are any', async () => {
      serve(calendar(), event({ all_day: true, start: '2026-03-10T00:00:00Z', end: '2026-03-10T00:00:00Z' }), {
        'GET /api/events/ev1/participants': [participant()],
        'POST /api/events/ev1/duplicate': event({ id: 'copy1' }),
      })
      mayAddTo(['cal1', 'owner'])
      await openExisting()
      await duplicateButton()[0]!.trigger('click')
      expect(page().find('#duplicate-event input[type="time"]').exists()).toBe(false)
      await page().get('#duplicate-event [role="switch"]').trigger('click')
      await page().get('#duplicate-event').trigger('submit')
      await flushPromises()
      expect(body('POST /api/events/ev1/duplicate')).toEqual({
        calendar_id: 'cal1',
        start: '2026-03-10T00:00:00.000Z',
        invite_participants: true,
      })
    })

    it('starts a copy of a series on the day of the occurrence opened, and says what it copies', async () => {
      serve(calendar(), event({ rrule: 'FREQ=WEEKLY' }), { 'POST /api/events/ev1/duplicate': event({ id: 'c' }) })
      mayAddTo(['cal1', 'owner'])
      await openExisting({
        occurrence: { recurrenceId: '2026-03-17T09:00:00.000Z', start: '2026-03-17T09:00:00.000Z', end: '' },
      })
      await duplicateButton()[0]!.trigger('click')
      expect(page().get<HTMLInputElement>('#duplicate-event input[type="date"]').element.value).toBe('2026-03-17')
      expect(text()).toContain('Copies the whole series')
      expect(page().find('#duplicate-event [role="switch"]').exists()).toBe(false)
    })

    it('shows why a copy failed and can be closed again', async () => {
      serve(calendar(), event(), {
        'POST /api/events/ev1/duplicate': reply(409, {
          detail: { message: 'This booking conflicts with an approved booking', conflicts: ['x'] },
        }),
      })
      mayAddTo(['cal1', 'owner'])
      await openExisting()
      await duplicateButton()[0]!.trigger('click')
      await page().get('#duplicate-event').trigger('submit')
      await flushPromises()
      expect(page().get('#duplicate-event [role="alert"]').text()).not.toBe('')
      expect(wrapper.emitted('duplicated')).toBeUndefined()
      const cancel = page()
        .findAll('button')
        .filter((b) => b.text() === 'Cancel')
      await cancel[cancel.length - 1]!.trigger('click')
      expect(dialogTitle()).not.toContain('Duplicate event')
    })
  })

  describe('a series', () => {
    const series = event({ rrule: 'FREQ=WEEKLY;BYDAY=TU;COUNT=5' })
    const occurrence = {
      recurrenceId: '2026-03-17T09:00:00.000Z',
      start: '2026-03-17T09:00:00.000Z',
      end: '2026-03-17T10:00:00.000Z',
    }

    it('shows the occurrence that was opened and asks which ones a change applies to', async () => {
      serve(calendar(), series, { 'PATCH /api/events/ev1/occurrences/*': series })
      await openExisting({ occurrence })
      const start = new Date(occurrence.start)
      expect((field('Start').element as HTMLInputElement).value).toBe(toDateInputValue(start))

      await click('Save')
      expect(dialog.choices.map((c) => c.value)).toEqual(['this', 'following', 'all'])
      await answerDialog(null)
      expect(backend.calls('PATCH /api/events/ev1/occurrences/*')).toHaveLength(0)

      await click('Save')
      await answerDialog('this')
      const [request] = backend.calls('PATCH /api/events/ev1/occurrences/*')
      expect(request!.path).toBe(`/api/events/ev1/occurrences/${occurrence.recurrenceId}`)
      expect(request!.query.get('scope')).toBe('this')
      // The unchanged rule is sent back as it was.
      expect(request!.body).toMatchObject({ rrule: series.rrule, start: occurrence.start, end: occurrence.end })
      expect(wrapper.emitted('saved')).toHaveLength(1)
    })

    it('does not offer a new recurrence for one occurrence alone', async () => {
      serve(calendar(), series, { 'PATCH /api/events/ev1/occurrences/*': series })
      await openExisting({ occurrence })
      await tab('Recurrence')!.trigger('click')
      await page()
        .findAll('[role="radio"]')
        .find((b) => b.text() === 'Never')!
        .trigger('click')
      await click('Save')
      expect(dialog.choices.map((c) => c.value)).toEqual(['following', 'all'])
      await answerDialog('all')
      expect(body('PATCH /api/events/ev1/occurrences/*')).toMatchObject({ rrule: 'FREQ=WEEKLY;BYDAY=TU' })
    })

    it('deletes the occurrences chosen', async () => {
      serve(calendar(), series, { 'DELETE /api/events/ev1/occurrences/*': undefined })
      await openExisting({ occurrence })
      await click('Delete')
      expect(dialog.title).toBe('Delete recurring event')
      await answerDialog(null)
      await click('Delete')
      await answerDialog('following')
      const [request] = backend.calls('DELETE /api/events/ev1/occurrences/*')
      expect(request!.query.get('scope')).toBe('following')
      expect(wrapper.emitted('deleted')).toHaveLength(1)
    })

    it('shows the opened day of an all-day series', async () => {
      serve(
        calendar(),
        event({
          all_day: true,
          rrule: 'FREQ=DAILY',
          start: '2026-03-10T00:00:00.000Z',
          end: '2026-03-10T00:00:00.000Z',
        }),
      )
      await openExisting({
        occurrence: { recurrenceId: '2026-03-12', start: '2026-03-12T00:00:00.000Z', end: '2026-03-13T00:00:00.000Z' },
      })
      expect((field('Start').element as HTMLInputElement).value).toBe('2026-03-12')
      expect((field('End').element as HTMLInputElement).value).toBe('2026-03-12')
    })

    it('keeps a rule from another app as it is', async () => {
      const foreign = 'FREQ=HOURLY;INTERVAL=2'
      serve(calendar(), event({ rrule: foreign }), { 'PATCH /api/events/ev1': event() })
      await openExisting()
      await tab('Recurrence')!.trigger('click')
      expect(page().get('[role="combobox"]').text()).toBe('Keep as is')
      await click('Save')
      expect(body('PATCH /api/events/ev1').rrule).toBe(foreign)
    })

    it('treats a changed occurrence as an event of its own, apart from the series', async () => {
      serve(calendar(), event({ parent_id: 'ev0', recurrence_id: '2026-03-17T09:00:00.000Z' }), {
        'DELETE /api/events/ev1': undefined,
      })
      await openExisting()
      expect(text()).toContain('This event was changed apart from its series.')
      expect(tabs()).not.toContain('Recurrence')
      await click('Delete')
      expect(dialog.message).toBe('The event will be removed from the series.')
      await answerDialog(true)
      expect(backend.calls('DELETE /api/events/ev1')).toHaveLength(1)
    })
  })

  describe('a booking', () => {
    it('shows that it awaits approval and lets approvers decide', async () => {
      serve(
        calendar(),
        event({ resource_id: 'r1', status: 'pending', awaiting_approval: ['Beamer'], can_decide: true }),
        {
          'POST /api/events/ev1/approve': event({ status: 'approved' }),
          'POST /api/events/ev1/reject': reply(500, { detail: 'Try later' }),
        },
      )
      await openExisting()
      expect(page().get('[data-modal-header] [role="status"]').text()).toBe('Awaiting approval')
      expect(text()).toContain('Still awaiting approval for: Beamer')
      expect(text()).toContain('Until it is approved')

      await click('Reject')
      expect(body('POST /api/events/ev1/reject')).toEqual({})
      expect(alertText()).toBe('Try later')

      await page().get('input[placeholder="Note (optional)"]').setValue(' Enjoy ')
      await click('Approve')
      expect(body('POST /api/events/ev1/approve')).toEqual({ note: 'Enjoy' })
      expect(wrapper.emitted('saved')).toHaveLength(1)
    })

    it('shows the note of a decision', async () => {
      serve(calendar(), event({ location_resource_id: 'l1', status: 'rejected', decision_note: 'Taken' }))
      await openExisting()
      expect(page().get('[data-modal-header] [role="status"]').text()).toBe('Rejected')
      expect(text()).toContain('„Taken“')
      expect(button('Approve')).toBeUndefined()
    })
  })
})
