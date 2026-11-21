import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { fakeBackend, reply, type FakeBackend } from '@/__tests__/fakeBackend'
import type * as api from '@/api'
import { i18n } from '@/i18n'
import UnsubscribeView from '../UnsubscribeView.vue'

let wrapper: VueWrapper
let backend: FakeBackend

const subscription = (subscribed: boolean, eventTitle: string | null = null): api.Subscription => ({
  email: 'ann@example.test',
  kind: eventTitle === null ? 'comments' : null,
  event_title: eventTitle,
  subscribed,
})

async function render() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:any(.*)', component: { template: '<div />' } }],
  })
  await router.push('/unsubscribe/tok-1')
  wrapper = mount(UnsubscribeView, { props: { token: 'tok-1' }, global: { plugins: [i18n, router] } })
  await flushPromises()
}

beforeEach(() => {
  i18n.global.locale.value = 'en'
  setActivePinia(createPinia())
  backend = fakeBackend({ 'GET /api/unsubscribe/tok-1': subscription(true) })
})

afterEach(() => wrapper.unmount())

describe('UnsubscribeView', () => {
  it('asks first, then stops that kind of email', async () => {
    backend.on('POST /api/unsubscribe/tok-1', subscription(false))
    await render()
    expect(wrapper.text()).toContain('Stop sending emails about “Comments” to ann@example.test?')
    // Opening the link (as mail scanners do) changes nothing.
    expect(backend.calls('POST /api/unsubscribe/tok-1')).toHaveLength(0)
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(backend.calls('POST /api/unsubscribe/tok-1')).toHaveLength(1)
    expect(wrapper.get('[role="status"]').text()).toContain('ann@example.test no longer gets emails about “Comments”.')
    expect(wrapper.get('a').attributes('href')).toBe('/account?tab=emailNotifications')
  })

  it('says so when that kind of email was stopped already, and takes it back', async () => {
    backend.on('GET /api/unsubscribe/tok-1', subscription(false))
    backend.on('DELETE /api/unsubscribe/tok-1', subscription(true))
    await render()
    expect(wrapper.get('[role="status"]').text()).toContain('no longer gets emails')
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(backend.calls('DELETE /api/unsubscribe/tok-1')).toHaveLength(1)
    expect(wrapper.text()).toContain('Stop sending emails about “Comments” to ann@example.test?')
  })

  it('stops the emails about one event, which only this page can take back', async () => {
    backend.on('GET /api/unsubscribe/tok-1', subscription(true, 'Planning'))
    backend.on('POST /api/unsubscribe/tok-1', subscription(false, 'Planning'))
    await render()
    expect(wrapper.text()).toContain('Stop sending emails about the event “Planning” to ann@example.test?')
    await wrapper.get('button').trigger('click')
    await flushPromises()
    const status = wrapper.get('[role="status"]').text()
    expect(status).toContain('ann@example.test no longer gets emails about the event “Planning”.')
    expect(status).toContain('You can take it back here.')
    expect(wrapper.get('button').text()).toBe('Take it back')
  })

  it('shows why unsubscribing failed, and lets you try again', async () => {
    backend.on('POST /api/unsubscribe/tok-1', reply(500, { detail: 'Try later' }))
    await render()
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Try later')
    expect(wrapper.find('button').exists()).toBe(true)
  })

  it('points to the settings when the link is not valid', async () => {
    backend.on('GET /api/unsubscribe/tok-1', reply(404, { detail: 'This link is not valid' }))
    await render()
    expect(wrapper.text()).toContain('This link is not valid.')
    expect(wrapper.find('button').exists()).toBe(false)
    expect(wrapper.get('a').attributes('href')).toBe('/account?tab=emailNotifications')
  })
})
