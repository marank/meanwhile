import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { fakeBackend, reply, type FakeBackend } from '@/__tests__/fakeBackend'
import type { Invitation } from '@/api'
import { i18n } from '@/i18n'
import { browserTimeZone } from '@/services/datetime'
import { useAuthStore } from '@/stores/auth'
import InvitationView from '../InvitationView.vue'
import { makeUser, sessionRoutes, stubBrowser } from './session'

let wrapper: VueWrapper
let backend: FakeBackend

const invitation = (overrides: Partial<Invitation> = {}): Invitation => ({
  title: 'Planning',
  start: '2026-01-05T09:00:00',
  end: '2026-01-05T10:30:00',
  all_day: false,
  timezone: browserTimeZone(),
  location: '',
  description: '',
  rrule: null,
  organizer_name: 'Bob',
  email: 'alice@example.com',
  status: 'needs_action',
  cancelled: false,
  participants: [{ name: 'alice@example.com', status: 'needs_action', you: true }],
  ...overrides,
})

async function render(answer?: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/event/:token', component: { template: '<div />' } }],
  })
  await router.push({ path: '/event/tok en', query: answer ? { answer } : {} })
  wrapper = mount(InvitationView, { props: { token: 'tok en' }, global: { plugins: [i18n, router] } })
  await flushPromises()
}

const answerButtons = () => wrapper.get('[role="group"]').findAll('button')
const answerButton = (label: string) => answerButtons().find((b) => b.text() === label)!
const when = () => wrapper.get('[data-when]').text()

beforeEach(async () => {
  i18n.global.locale.value = 'en'
  setActivePinia(createPinia())
  stubBrowser()
  // Dates as the signed-in user formats them, so the expected texts don't depend on the machine's locale.
  backend = fakeBackend(sessionRoutes(makeUser()))
  await useAuthStore().init()
})

afterEach(() => {
  wrapper?.unmount()
  vi.restoreAllMocks()
})

describe('InvitationView', () => {
  it('shows the event of the invitation from the link', async () => {
    backend.on(
      'GET /api/rsvp/*',
      invitation({ location: 'Room 1', description: 'Agenda follows', rrule: 'FREQ=WEEKLY;BYDAY=MO' }),
    )
    await render()
    expect(backend.calls('GET /api/rsvp/*')[0]!.path).toBe('/api/rsvp/tok en')
    const text = wrapper.text()
    expect(wrapper.get('h1').text()).toBe('Planning')
    expect(text).toContain('Invitation from Bob')
    expect(when()).toBe('Monday, January 5, 2026')
    expect(text).toContain('09:00 – 10:30')
    expect(text).toContain('Weekly on Monday')
    expect(wrapper.get('a[href^="https://www.openstreetmap.org/"]').text()).toBe('Room 1')
    expect(text).toContain('Agenda follows')
    expect(text).toContain('Invited as alice@example.com')
    expect(answerButtons().every((b) => b.attributes('aria-pressed') === 'false')).toBe(true)
    expect(answerButtons().map((b) => b.text())).toEqual(['Accept', 'Tentative', 'Decline'])
    // Planned in the reader's zone: nothing to point out.
    expect(text).not.toContain('Times in your time zone')
  })

  it('leaves out an organizer without a name', async () => {
    backend.on('GET /api/rsvp/*', invitation({ organizer_name: '' }))
    await render()
    expect(wrapper.text()).toContain('Invitation')
    expect(wrapper.text()).not.toContain('Invitation from')
    expect(wrapper.find('[aria-label="Organizer"]').exists()).toBe(false)
  })

  it('names rules without a preset just as repeating', async () => {
    backend.on('GET /api/rsvp/*', invitation({ rrule: 'FREQ=DAILY;INTERVAL=3' }))
    await render()
    expect(wrapper.text()).toContain('Repeats')
  })

  it("says the times are in the reader's zone when the event was planned in another", async () => {
    backend.on('GET /api/rsvp/*', invitation({ timezone: 'Pacific/Chatham' }))
    await render()
    expect(wrapper.text()).toContain(`Times in your time zone (${browserTimeZone()})`)
  })

  it('shows who else is invited and how they answered', async () => {
    backend.on(
      'GET /api/rsvp/*',
      invitation({
        participants: [
          { name: 'alice@example.com', status: 'needs_action', you: true },
          { name: 'Carol', status: 'accepted', you: false },
          // A guest: anyone with the link sees the page, so nobody else's address is shown.
          { name: null, status: 'declined', you: false },
        ],
      }),
    )
    await render()
    expect(wrapper.text()).toContain('Participants (3)')
    const people = wrapper.get('[data-participants]').findAll('li')
    const shown = people.map((li) => {
      const [name, status] = li.findAll(':scope > span').map((span) => span.text().replace(/\s+/g, ' '))
      return [name, status, li.attributes('data-status')]
    })
    expect(shown).toEqual([
      ['alice@example.com (you)', 'Needs action', 'needs_action'],
      ['Carol', 'Accepted', 'accepted'],
      ['Guest', 'Declined', 'declined'],
    ])
  })

  it('offers the event as a file for calendar apps', async () => {
    backend.on('GET /api/rsvp/*', invitation())
    await render()
    const link = wrapper.get('a[download]')
    expect(link.text()).toBe('Add to calendar')
    expect(link.attributes('href')).toBe('/api/rsvp/tok%20en/ics')
  })

  it('names untitled events and shows both dates of a timed event over several days', async () => {
    backend.on('GET /api/rsvp/*', invitation({ title: '', end: '2026-01-06T10:00:00' }))
    await render()
    expect(wrapper.get('h1').text()).toBe('Untitled')
    expect(when()).toBe('2026-01-05 09:00 –\n2026-01-06 10:00')
  })

  it('shows all-day events by their dates', async () => {
    // As the backend sends them: midnight UTC, the end inclusive.
    const day = (date: string) => `${date}T00:00:00Z`
    backend.on('GET /api/rsvp/*', invitation({ all_day: true, start: day('2026-01-05'), end: day('2026-01-05') }))
    await render()
    expect(when()).toBe('Monday, January 5, 2026')
    expect(wrapper.text()).toContain('All day')
    wrapper.unmount()
    backend.on('GET /api/rsvp/*', invitation({ all_day: true, start: day('2026-01-05'), end: day('2026-01-07') }))
    await render()
    expect(when()).toBe('Monday, January 5, 2026 –\nWednesday, January 7, 2026')
  })

  it('highlights the answer the link suggests without giving it', async () => {
    backend.on('GET /api/rsvp/*', invitation())
    await render('tentative')
    expect(answerButton('Tentative').attributes('data-suggested')).toBe('true')
    expect(answerButton('Accept').attributes('data-suggested')).toBeUndefined()
    // Suggested, not given.
    expect(answerButtons().some((b) => b.attributes('aria-pressed') === 'true')).toBe(false)
    expect(backend.calls('POST /api/rsvp/*')).toHaveLength(0)
  })

  it('says a suggested answer is not saved until it is clicked', async () => {
    backend.on('GET /api/rsvp/*', invitation())
    backend.on('POST /api/rsvp/*', invitation({ status: 'tentative' }))
    await render('accepted')
    expect(wrapper.get('[data-unsaved]').text()).toBe('not saved yet')
    // Any answer clicked is saved: the hint goes.
    await answerButton('Tentative').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-unsaved]').exists()).toBe(false)
  })

  it.each([
    ['without a suggestion', undefined, 'needs_action'],
    ['when answered before', 'accepted', 'declined'],
  ] as const)('says nothing about saving %s', async (_, answer, status) => {
    backend.on('GET /api/rsvp/*', invitation({ status }))
    await render(answer)
    expect(wrapper.find('[data-unsaved]').exists()).toBe(false)
  })

  it('ignores a suggested answer it does not know', async () => {
    backend.on('GET /api/rsvp/*', invitation())
    await render('maybe')
    expect(answerButtons().some((b) => b.attributes('data-suggested'))).toBe(false)
  })

  it('sends the answer clicked and shows it as chosen', async () => {
    backend.on('GET /api/rsvp/*', invitation())
    backend.on('POST /api/rsvp/*', invitation({ status: 'accepted' }))
    await render()
    await answerButton('Accept').trigger('click')
    await flushPromises()
    expect(backend.calls('POST /api/rsvp/*')[0]!.body).toEqual({ status: 'accepted' })
    expect(answerButtons().map((b) => b.attributes('aria-pressed'))).toEqual(['true', 'false', 'false'])
    // The chosen one says what was answered.
    expect(answerButtons().map((b) => b.text())).toEqual(['Accepted', 'Tentative', 'Decline'])
    // Changed later, the other one is chosen.
    backend.on('POST /api/rsvp/*', invitation({ status: 'declined' }))
    await answerButton('Decline').trigger('click')
    await flushPromises()
    expect(answerButtons().map((b) => b.attributes('aria-pressed'))).toEqual(['false', 'false', 'true'])
    expect(answerButtons().map((b) => b.text())).toEqual(['Accept', 'Tentative', 'Declined'])
  })

  it('shows the answer given earlier', async () => {
    backend.on('GET /api/rsvp/*', invitation({ status: 'declined' }))
    await render('accepted')
    expect(answerButton('Declined').attributes('aria-pressed')).toBe('true')
    expect(answerButton('Accept').attributes('aria-pressed')).toBe('false')
  })

  it('shows why an answer could not be sent', async () => {
    backend.on('GET /api/rsvp/*', invitation())
    backend.on('POST /api/rsvp/*', reply(400, { detail: 'Too late.' }))
    await render()
    await answerButton('Decline').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Too late.')
    expect(answerButton('Decline').attributes('aria-pressed')).toBe('false')
  })

  it('offers no answers for a cancelled event', async () => {
    backend.on('GET /api/rsvp/*', invitation({ cancelled: true }))
    await render()
    expect(wrapper.text()).toContain('This event has been cancelled.')
    expect(wrapper.find('[role="group"]').exists()).toBe(false)
    expect(wrapper.find('a[download]').exists()).toBe(false)
  })

  it('says so when the invitation no longer exists', async () => {
    backend.on('GET /api/rsvp/*', reply(404))
    await render()
    expect(wrapper.text()).toContain('This invitation no longer exists.')
  })
})
