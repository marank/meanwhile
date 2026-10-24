import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, h } from 'vue'
import { fakeBackend, reply, type FakeBackend } from '@/__tests__/fakeBackend'
import type { AppNotification } from '@/api'
import { i18n } from '@/i18n'
import { realtime } from '@/services/realtime'
import { toasts } from '@/services/toast'
import NotificationsView from '../NotificationsView.vue'
import { makeNotification } from './session'

let wrapper: VueWrapper
let backend: FakeBackend

/** The event dialog is tested on its own; here it only has to say which event it shows and close. */
const EventModalStub = defineComponent({
  props: { eventId: { type: String, required: true } },
  emits: ['saved', 'cancel', 'deleted'],
  setup(props, { emit }) {
    return () =>
      h('div', { 'data-test': 'event-modal' }, [
        `Event ${props.eventId}`,
        h('button', { onClick: () => emit('saved') }, 'Save event'),
        h('button', { onClick: () => emit('cancel') }, 'Cancel event'),
        h('button', { onClick: () => emit('deleted') }, 'Delete event'),
      ])
  },
})

async function render(items: AppNotification[], counts = { unread: 0, approvals: 0, invitations: 0 }) {
  backend = fakeBackend({
    'GET /api/notifications': items,
    'GET /api/notifications/counts': counts,
  })
  wrapper = mount(NotificationsView, {
    global: { plugins: [i18n], stubs: { EventModal: EventModalStub } },
  })
  await flushPromises()
}

const item = (index = 0) => wrapper.findAll('li')[index]!
const button = (text: string, scope: { findAll: VueWrapper['findAll'] } = wrapper) =>
  scope.findAll('button').find((b) => b.text() === text)
const tab = (label: string) => wrapper.findAll('[role="tab"]').find((t) => t.text().startsWith(label))!

beforeEach(() => {
  i18n.global.locale.value = 'en'
  setActivePinia(createPinia())
  toasts.splice(0)
})

afterEach(() => {
  wrapper?.unmount()
  vi.restoreAllMocks()
})

describe('NotificationsView', () => {
  it('shows a loading note until the list has arrived', async () => {
    backend = fakeBackend({
      'GET /api/notifications': () => new Promise(() => {}),
      'GET /api/notifications/counts': { unread: 0, approvals: 0, invitations: 0 },
    })
    wrapper = mount(NotificationsView, { global: { plugins: [i18n], stubs: { EventModal: EventModalStub } } })
    await flushPromises()
    expect(wrapper.text()).toContain('Loading…')
  })

  it('says so when there are no notifications', async () => {
    await render([])
    expect(wrapper.text()).toContain('No notifications yet.')
    expect(button('Mark all as read')).toBeUndefined()
  })

  it('lists the notifications with their text and time', async () => {
    await render([
      makeNotification({ id: 'n1', type: 'booking_approved', title: 'Room booking' }),
      makeNotification({ id: 'n2', type: 'event_reminder', title: 'Standup', read_at: '2026-01-05T09:00:00' }),
    ])
    expect(wrapper.findAll('li')).toHaveLength(2)
    expect(item(0).text()).toContain('Bob approved "Room booking"')
    expect(item(0).classes()).not.toContain('opacity-70')
    expect(item(1).classes()).toContain('opacity-70')
  })

  it('shows the open counts on the tabs and loads a tab when it is selected', async () => {
    await render([], { unread: 0, approvals: 2, invitations: 1 })
    expect(tab('Approvals').text()).toBe('Approvals 2')
    expect(tab('Invitations').text()).toBe('Invitations 1')

    await tab('Approvals').trigger('click')
    await flushPromises()
    expect(backend.calls('GET /api/notifications').at(-1)!.query.get('group')).toBe('approvals')
    expect(wrapper.text()).toContain('No approval requests.')

    await tab('Invitations').trigger('click')
    await flushPromises()
    expect(backend.calls('GET /api/notifications').at(-1)!.query.get('group')).toBe('invitations')
    expect(wrapper.text()).toContain('No invitations.')

    await tab('All').trigger('click')
    await flushPromises()
    expect(backend.calls('GET /api/notifications').at(-1)!.query.has('group')).toBe(false)
    expect(wrapper.text()).toContain('No notifications yet.')
  })

  it('does not reload when the selected tab is clicked again', async () => {
    await render([])
    await tab('All').trigger('click')
    await flushPromises()
    expect(backend.calls('GET /api/notifications')).toHaveLength(1)
  })

  describe('approval requests', () => {
    const request = (overrides: Partial<AppNotification> = {}) =>
      makeNotification({ type: 'approval_requested', event_status: 'pending', ...overrides })

    it('approves a pending request and reloads the list', async () => {
      await render([request()])
      backend.on('POST /api/events/e1/approve', {})
      await button('Approve')!.trigger('click')
      await flushPromises()
      expect(backend.calls('POST /api/events/e1/approve')).toHaveLength(1)
      expect(backend.calls('GET /api/notifications')).toHaveLength(2)
    })

    it('declines a pending request', async () => {
      await render([request()])
      backend.on('POST /api/events/e1/reject', {})
      await button('Decline')!.trigger('click')
      await flushPromises()
      expect(backend.calls('POST /api/events/e1/reject')).toHaveLength(1)
    })

    it('explains a booking conflict when approving fails with one', async () => {
      await render([request()])
      backend.on('POST /api/events/e1/approve', reply(409, { detail: 'conflict' }))
      await button('Approve')!.trigger('click')
      await flushPromises()
      expect(toasts.map((t) => t.message)).toEqual([i18n.global.t('booking.conflict')])
    })

    it('shows how a request was decided instead of the buttons', async () => {
      await render([
        request({ id: 'a', event_status: 'approved' }),
        request({ id: 'b', event_status: 'confirmed' }),
        request({ id: 'c', event_status: 'rejected' }),
        request({ id: 'd', event_status: 'cancelled' }),
        request({ id: 'e', event_status: null, event_id: null }),
      ])
      expect(wrapper.findAll('li').map((li) => li.find('span').text())).toEqual([
        'Approved',
        'Approved',
        'Rejected',
        'Cancelled',
        'Event deleted',
      ])
      expect(button('Approve')).toBeUndefined()
    })
  })

  describe('invitations', () => {
    const invitation = (overrides: Partial<AppNotification> = {}) =>
      makeNotification({ type: 'participant_added', event_status: 'confirmed', ...overrides })

    it.each([
      ['Accept', 'accepted'],
      ['Tentative', 'tentative'],
      ['Decline', 'declined'],
    ])('answers with "%s" and reloads the list', async (label, status) => {
      await render([invitation()])
      backend.on('PATCH /api/events/e1/participants/me', {})
      await button(label)!.trigger('click')
      await flushPromises()
      expect(backend.calls('PATCH /api/events/e1/participants/me')[0]!.body).toEqual({ status })
      expect(backend.calls('GET /api/notifications')).toHaveLength(2)
    })

    it('shows the answer already given', async () => {
      await render([invitation({ response_status: 'tentative' })])
      expect(wrapper.text()).toContain('Your answer: Tentative')
    })

    it('offers no answers once the event is gone', async () => {
      await render([invitation({ event_status: null, event_id: null })])
      expect(button('Accept')).toBeUndefined()
      expect(button('Show event')).toBeUndefined()
    })

    it('reports a failed answer', async () => {
      await render([invitation()])
      backend.on('PATCH /api/events/e1/participants/me', reply(400, { detail: 'Not invited.' }))
      await button('Accept')!.trigger('click')
      await flushPromises()
      expect(toasts.map((t) => t.message)).toEqual(['Not invited.'])
    })
  })

  describe('the event', () => {
    it('opens the event and closes it without reloading when nothing changed', async () => {
      await render([makeNotification({ type: 'comment_added' })])
      await button('Show event')!.trigger('click')
      expect(wrapper.get('[data-test="event-modal"]').text()).toContain('Event e1')
      await button('Cancel event')!.trigger('click')
      await flushPromises()
      expect(wrapper.find('[data-test="event-modal"]').exists()).toBe(false)
      expect(backend.calls('GET /api/notifications')).toHaveLength(1)
    })

    it.each(['Save event', 'Delete event'])('reloads the list after "%s"', async (action) => {
      await render([makeNotification({ type: 'comment_added' })])
      await button('Show event')!.trigger('click')
      await button(action)!.trigger('click')
      await flushPromises()
      expect(wrapper.find('[data-test="event-modal"]').exists()).toBe(false)
      expect(backend.calls('GET /api/notifications')).toHaveLength(2)
    })
  })

  it('marks one notification read', async () => {
    await render([makeNotification()], { unread: 1, approvals: 0, invitations: 0 })
    backend.on('POST /api/notifications/n1/read', makeNotification({ read_at: '2026-01-05T10:00:00' }))
    await button('Mark as read')!.trigger('click')
    await flushPromises()
    expect(backend.calls('POST /api/notifications/n1/read')).toHaveLength(1)
    expect(item().classes()).toContain('opacity-70')
    expect(button('Mark as read')).toBeUndefined()
  })

  it('marks all notifications read', async () => {
    await render([makeNotification({ id: 'a' }), makeNotification({ id: 'b' })])
    backend.on('POST /api/notifications/read-all', { ok: true })
    await button('Mark all as read')!.trigger('click')
    await flushPromises()
    expect(backend.calls('POST /api/notifications/read-all')).toHaveLength(1)
    expect(wrapper.findAll('li').every((li) => li.classes().includes('opacity-70'))).toBe(true)
  })

  it('deletes a notification that may be deleted', async () => {
    await render([makeNotification({ id: 'a', deletable: true }), makeNotification({ id: 'b' })])
    expect(item(1).find('button[aria-label="Delete"]').exists()).toBe(false)
    backend.on('DELETE /api/notifications/a', undefined)
    await item(0).get('button[aria-label="Delete"]').trigger('click')
    await flushPromises()
    expect(backend.calls('DELETE /api/notifications/a')).toHaveLength(1)
    expect(wrapper.findAll('li')).toHaveLength(1)
  })

  it('reloads its list on live updates only while it is shown', async () => {
    await render([])
    const emit = (realtime as unknown as { emit(message: Record<string, unknown>): void }).emit.bind(realtime)
    emit({ type: 'notifications.changed' })
    await flushPromises()
    expect(backend.calls('GET /api/notifications')).toHaveLength(2)
    wrapper.unmount()
    emit({ type: 'notifications.changed' })
    await flushPromises()
    expect(backend.calls('GET /api/notifications')).toHaveLength(2)
  })
})
