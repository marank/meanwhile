import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { computed, defineComponent, h, ref } from 'vue'
import type * as api from '@/api'
import { fakeBackend, reply, type FakeBackend } from '@/__tests__/fakeBackend'
import { calendar, event } from '@/components/event/__tests__/helpers'
import { i18n } from '@/i18n'
import { dialog, submitDialog } from '@/services/dialog'
import type { OccurrenceRef } from '@/services/occurrences'
import { useEventParticipants, useEventReminders } from '../useEventExtras'
import { useEventSave } from '../useEventSave'

const INPUT = { title: 'Planning', rrule: null } as api.EventInput
const OCCURRENCE: OccurrenceRef = { recurrenceId: '2026-03-17T09:00:00Z', start: '', end: '' }

let backend: FakeBackend

function setup(
  options: {
    event?: api.Event | null
    canModify?: boolean
    occurrence?: OccurrenceRef | null
    valid?: boolean
    input?: api.EventInput
  } = {},
) {
  const participants = useEventParticipants()
  const reminders = useEventReminders()
  const current = ref(options.event ?? null)
  const onSaved = vi.fn()
  const onDeleted = vi.fn()
  let save!: ReturnType<typeof useEventSave>
  mount(
    defineComponent({
      setup() {
        save = useEventSave({
          calendar: ref(calendar()),
          event: current,
          eventId: () => options.event?.id,
          seriesOccurrence: ref(options.occurrence ?? null),
          isException: computed(() => !!current.value?.parent_id),
          canModify: ref(options.canModify ?? true),
          valid: () => options.valid ?? true,
          eventInput: () => options.input ?? INPUT,
          participants,
          reminders,
          onSaved,
          onDeleted,
        })
        return () => h('div')
      },
    }),
    { global: { plugins: [i18n] } },
  )
  return { ...save, event: current, participants, reminders, onSaved, onDeleted }
}

/** Answers the dialog that opened. */
async function answer(value: unknown) {
  await flushPromises()
  expect(dialog.open).toBe(true)
  submitDialog(value)
  await flushPromises()
}

beforeEach(() => {
  i18n.global.locale.value = 'en'
  backend = fakeBackend({
    'POST /api/calendars/cal1/events': event({ id: 'new1' }),
    'PATCH /api/events/*': event(),
    'PATCH /api/events/ev1/occurrences/*': event(),
    'PUT /api/events/*/reminders': { minutes: [] },
    'DELETE /api/events/*': undefined,
    'DELETE /api/events/ev1/occurrences/*': undefined,
    'POST /api/events/ev1/approve': event(),
    'POST /api/events/ev1/reject': event(),
  })
})

afterEach(() => {
  if (dialog.open) submitDialog(null)
  vi.unstubAllGlobals()
})

describe('useEventSave', () => {
  it('creates an event once, and edits the created one when a later step failed', async () => {
    const s = setup()
    s.participants.pending.value = [{ tempId: 't', email: 'a@example.com', display_name: '', status: 'needs_action' }]
    s.reminders.minutes.value = [15]
    backend.on('PUT /api/events/new1/reminders', reply(500, { detail: 'Reminders down' }))
    await s.save()
    expect(s.error.value).toBe('Reminders down')
    expect(s.event.value?.id).toBe('new1')
    expect(s.participants.pending.value).toEqual([])
    expect(backend.calls('POST /api/calendars/cal1/events')[0]!.body).toMatchObject({
      title: 'Planning',
      participants: [{ email: 'a@example.com', status: 'needs_action' }],
    })
    backend.on('PUT /api/events/new1/reminders', { minutes: [15] })
    await s.save()
    expect(s.error.value).toBe('')
    expect(backend.calls('POST /api/calendars/cal1/events')).toHaveLength(1)
    expect(backend.calls('PATCH /api/events/new1')).toHaveLength(1)
    expect(s.onSaved).toHaveBeenCalledOnce()
  })

  it('sends nothing while what is entered is invalid', async () => {
    const s = setup({ valid: false })
    await s.save()
    expect(backend.requests).toHaveLength(0)
  })

  it("saves only one's own reminders where the event may not be changed", async () => {
    const s = setup({ event: event(), canModify: false })
    s.reminders.minutes.value = [30]
    await s.save()
    expect(backend.requests.map((r) => `${r.method} ${r.path}`)).toEqual(['PUT /api/events/ev1/reminders'])
    expect(s.onSaved).toHaveBeenCalledOnce()
  })

  it('asks which occurrences of a series a change applies to', async () => {
    const s = setup({
      event: event({ rrule: 'FREQ=WEEKLY' }),
      occurrence: OCCURRENCE,
      input: { ...INPUT, rrule: 'FREQ=WEEKLY' },
    })
    let saving = s.save()
    await answer(null)
    await saving
    expect(backend.requests).toHaveLength(0)
    saving = s.save()
    await answer('this')
    await saving
    expect(backend.requests[0]!.path).toBe('/api/events/ev1/occurrences/2026-03-17T09:00:00Z')
    expect(backend.requests[0]!.query.get('scope')).toBe('this')
    expect(s.onSaved).toHaveBeenCalledOnce()
  })

  it('offers only whole parts of the series when its recurrence changed', async () => {
    const s = setup({
      event: event({ rrule: 'FREQ=WEEKLY' }),
      occurrence: OCCURRENCE,
      input: { ...INPUT, rrule: 'FREQ=DAILY' },
    })
    void s.save()
    await flushPromises()
    expect(dialog.choices.map((choice) => choice.value)).toEqual(['following', 'all'])
  })

  it('deletes after asking, an occurrence of a series in the scope chosen', async () => {
    const single = setup({ event: event({ parent_id: 'series1' }) })
    let deleting = single.remove()
    await flushPromises()
    expect(dialog.message).toBe(i18n.global.t('series.deleteExceptionText'))
    await answer(false)
    await deleting
    expect(backend.requests).toHaveLength(0)
    deleting = single.remove()
    await answer(true)
    await deleting
    expect(backend.calls('DELETE /api/events/ev1')).toHaveLength(1)
    expect(single.onDeleted).toHaveBeenCalledOnce()

    const series = setup({ event: event({ rrule: 'FREQ=WEEKLY' }), occurrence: OCCURRENCE })
    deleting = series.remove()
    await answer('all')
    await deleting
    expect(backend.calls('DELETE /api/events/ev1/occurrences/*')[0]!.query.get('scope')).toBe('all')
  })

  it('does nothing for a new event', async () => {
    const s = setup()
    await s.remove()
    await s.decide('approve', 'ok')
    expect(dialog.open).toBe(false)
    expect(backend.requests).toHaveLength(0)
  })

  it('decides on a booking, with the note if there is one', async () => {
    const s = setup({ event: event() })
    await s.decide('approve', '  Fine  ')
    await s.decide('reject', '   ')
    expect(backend.calls('POST /api/events/ev1/approve')[0]!.body).toEqual({ note: 'Fine' })
    expect(backend.calls('POST /api/events/ev1/reject')[0]!.body).toEqual({})
    expect(s.onSaved).toHaveBeenCalledTimes(2)
  })
})
