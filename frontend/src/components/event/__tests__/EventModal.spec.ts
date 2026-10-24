import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DOMWrapper, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { fakeBackend, reply, type FakeBackend, type FakeRequest } from '@/__tests__/fakeBackend'
import type * as api from '@/api'
import { i18n } from '@/i18n'
import { browserTimeZone, toDateInputValue, toTimeInputValue } from '@/services/datetime'
import { dialog, submitDialog } from '@/services/dialog'
import type { OccurrenceRef } from '@/services/occurrences'
import EventModal from '../EventModal.vue'
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
const text = () => document.body.textContent!.replace(/\s+/g, ' ')
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
    o.textContent!.includes(optionLabel),
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
    wrapper?.unmount()
    vi.useRealTimers()
    if (dialog.open) submitDialog(null)
    vi.restoreAllMocks()
  })

  describe('a new event', () => {
    it('starts at the time picked in the calendar and lasts an hour', async () => {
      serve()
      await openNew()
      expect(page().get('h3').text()).toBe('Add')
      expect(tabs()).toEqual(['Details', 'Recurrence', 'Reminders', 'Participants', 'Availability'])
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

    it('waits for a calendar to put it in', async () => {
      const backend = serve()
      await open({})
      expect(text()).toContain('Loading…')
      expect(backend.requests.filter((r) => r.path !== '/api/search')).toHaveLength(0)
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
      expect(page().get('h3').text()).toBe('Edit')
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
