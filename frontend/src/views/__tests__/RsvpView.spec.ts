import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { fakeBackend, reply, type FakeBackend } from '@/__tests__/fakeBackend'
import type { Invitation } from '@/api'
import { i18n } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import RsvpView from '../RsvpView.vue'
import { makeUser, sessionRoutes, stubBrowser } from './session'

let wrapper: VueWrapper
let backend: FakeBackend

const invitation = (overrides: Partial<Invitation> = {}): Invitation => ({
  title: 'Planning',
  start: '2026-01-05T09:00:00',
  end: '2026-01-05T10:30:00',
  all_day: false,
  timezone: 'Europe/Berlin',
  location: '',
  description: '',
  rrule: null,
  organizer_name: 'Bob',
  email: 'alice@example.com',
  status: 'needs_action',
  cancelled: false,
  ...overrides,
})

async function render(answer?: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/rsvp/:token', component: { template: '<div />' } }],
  })
  await router.push({ path: '/rsvp/tok en', query: answer ? { answer } : {} })
  wrapper = mount(RsvpView, { props: { token: 'tok en' }, global: { plugins: [i18n, router] } })
  await flushPromises()
}

const answerButtons = () => wrapper.get('[role="group"]').findAll('button')
const answerButton = (label: string) => answerButtons().find((b) => b.text() === label)!

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

describe('RsvpView', () => {
  it('shows the invitation from the link', async () => {
    backend.on(
      'GET /api/rsvp/*',
      invitation({ location: 'Room 1', description: 'Agenda follows', rrule: 'FREQ=WEEKLY' }),
    )
    await render()
    expect(backend.calls('GET /api/rsvp/*')[0]!.path).toBe('/api/rsvp/tok en')
    const text = wrapper.text()
    expect(wrapper.get('h2').text()).toBe('Planning')
    expect(text).toContain('2026-01-05 09:00 – 10:30')
    expect(text).toContain('Repeats')
    expect(text).toContain('Room 1')
    expect(text).toContain('Agenda follows')
    expect(text).toContain('Bob invited you (alice@example.com).')
    expect(text).toContain('Choose your answer:')
    expect(answerButtons().map((b) => b.text())).toEqual(['Accept', 'Tentative', 'Decline'])
  })

  it('names untitled events and shows both dates of a timed event over several days', async () => {
    backend.on('GET /api/rsvp/*', invitation({ title: '', end: '2026-01-06T10:00:00' }))
    await render()
    expect(wrapper.get('h2').text()).toBe('Untitled')
    expect(wrapper.text()).toContain('2026-01-05 09:00 – 2026-01-06 10:00')
  })

  it('shows all-day events by their dates', async () => {
    // As the backend sends them: midnight UTC, the end inclusive.
    const day = (date: string) => `${date}T00:00:00Z`
    backend.on('GET /api/rsvp/*', invitation({ all_day: true, start: day('2026-01-05'), end: day('2026-01-05') }))
    await render()
    expect(wrapper.find('dd').text()).toBe('2026-01-05')
    wrapper.unmount()
    backend.on('GET /api/rsvp/*', invitation({ all_day: true, start: day('2026-01-05'), end: day('2026-01-07') }))
    await render()
    expect(wrapper.find('dd').text()).toBe('2026-01-05 – 2026-01-07')
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

  it('ignores a suggested answer it does not know', async () => {
    backend.on('GET /api/rsvp/*', invitation())
    await render('maybe')
    expect(answerButtons().some((b) => b.attributes('data-suggested'))).toBe(false)
  })

  it('sends the answer clicked and thanks for it', async () => {
    backend.on('GET /api/rsvp/*', invitation())
    backend.on('POST /api/rsvp/*', invitation({ status: 'accepted' }))
    await render()
    await answerButton('Accept').trigger('click')
    await flushPromises()
    expect(backend.calls('POST /api/rsvp/*')[0]!.body).toEqual({ status: 'accepted' })
    expect(wrapper.text()).toContain('Thank you, your answer was sent.')
    expect(answerButton('Accept').attributes('aria-pressed')).toBe('true')
  })

  it('shows the answer given earlier', async () => {
    backend.on('GET /api/rsvp/*', invitation({ status: 'declined' }))
    await render('accepted')
    expect(wrapper.text()).toContain('Current answer: Declined')
    expect(answerButton('Decline').attributes('aria-pressed')).toBe('true')
    expect(answerButton('Accept').attributes('aria-pressed')).toBe('false')
  })

  it('shows why an answer could not be sent', async () => {
    backend.on('GET /api/rsvp/*', invitation())
    backend.on('POST /api/rsvp/*', reply(400, { detail: 'Too late.' }))
    await render()
    await answerButton('Decline').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Too late.')
    expect(wrapper.text()).not.toContain('Thank you')
  })

  it('offers no answers for a cancelled event', async () => {
    backend.on('GET /api/rsvp/*', invitation({ cancelled: true }))
    await render()
    expect(wrapper.text()).toContain('This event has been cancelled.')
    expect(wrapper.find('[role="group"]').exists()).toBe(false)
  })

  it('says so when the invitation no longer exists', async () => {
    backend.on('GET /api/rsvp/*', reply(404))
    await render()
    expect(wrapper.text()).toContain('This invitation no longer exists.')
  })
})
