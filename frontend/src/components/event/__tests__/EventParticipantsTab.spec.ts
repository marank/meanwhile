import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { fakeBackend } from '@/__tests__/fakeBackend'
import type * as api from '@/api'
import { i18n } from '@/i18n'
import EventParticipantsTab, { type PendingParticipant } from '../EventParticipantsTab.vue'
import { participant, signIn } from './helpers'

const anna = participant()
const ben = participant({ id: 'p2', user_id: null, email: 'ben@example.com', display_name: null, status: 'declined' })

let wrapper: VueWrapper

/** Mounts the tab with its models wired up as a parent's v-model would. */
function render(
  props: Partial<{
    eventId: string | null
    canManage: boolean
    participants: api.EventParticipant[] | null
    pending: PendingParticipant[]
    removed: string[]
  }> = {},
) {
  wrapper = mount(EventParticipantsTab, {
    props: {
      eventId: 'ev1',
      canManage: true,
      participants: [anna, ben],
      pending: [],
      removed: [],
      'onUpdate:pending': (value: PendingParticipant[]) => wrapper.setProps({ pending: value }),
      'onUpdate:removed': (value: string[]) => wrapper.setProps({ removed: value }),
      ...props,
    },
    global: { plugins: [i18n] },
    attachTo: document.body,
  })
  return wrapper
}

const pending = () => (wrapper.props() as { pending: PendingParticipant[] }).pending
const removed = () => (wrapper.props() as { removed: string[] }).removed
const groups = () =>
  wrapper.findAll('ul').map((ul) => [
    ul.element.previousElementSibling!.textContent.trim(),
    ...ul.findAll('li').map((li) =>
      li
        .findAll('p')
        .map((p) => p.text())
        .join(' '),
    ),
  ])

async function enter(text: string) {
  const input = wrapper.get('input')
  await input.setValue(text)
  await vi.advanceTimersByTimeAsync(200)
  await flushPromises()
  await input.trigger('keydown', { key: 'Enter' })
  await flushPromises()
}

describe('EventParticipantsTab', () => {
  beforeEach(() => {
    signIn()
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
  })

  afterEach(() => {
    wrapper.unmount()
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('lists the participants by their answer', () => {
    render({
      pending: [{ tempId: 't1', email: 'cleo@example.com', display_name: 'cleo@example.com', status: 'needs_action' }],
    })
    expect(groups()).toEqual([
      ['Needs action', 'cleo@example.com'],
      ['Accepted', 'Anna anna@example.com'],
      ['Declined', 'ben@example.com'],
    ])
  })

  it('waits for the saved participants of an existing event', async () => {
    render({ participants: null })
    expect(wrapper.text()).toContain('Loading…')
    await wrapper.setProps({ eventId: null })
    expect(wrapper.text()).toContain('No participants yet.')
  })

  it('removes saved and added participants', async () => {
    render({
      pending: [{ tempId: 't1', email: 'cleo@example.com', display_name: 'cleo@example.com', status: 'needs_action' }],
    })
    const remove = (name: string) =>
      wrapper
        .findAll('li')
        .find((li) => li.text().includes(name))!
        .get('button')
        .trigger('click')
    await remove('Anna')
    expect(removed()).toEqual(['p1'])
    await remove('cleo')
    expect(pending()).toEqual([])
    expect(groups()).toEqual([['Declined', 'ben@example.com']])
  })

  it('adds a picked user or a typed email address', async () => {
    const backend = fakeBackend({
      'GET /api/search': [{ id: 'u9', type: 'user', label: 'Dora', subtitle: 'dora@example.com', meta: null }],
    })
    render()
    await enter('Do')
    // Enter takes the free text if no option is active, so pick the user with the arrow key.
    expect(pending()).toEqual([])
    await wrapper.get('input').setValue('Dor')
    await vi.advanceTimersByTimeAsync(200)
    await flushPromises()
    await wrapper.get('input').trigger('keydown', { key: 'ArrowDown' })
    await wrapper.get('input').trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(backend.calls('GET /api/search')[0]!.query.get('entity')).toBe('users')
    expect(pending()).toEqual([
      {
        tempId: expect.any(String),
        user_id: 'u9',
        email: 'dora@example.com',
        display_name: 'Dora',
        status: 'needs_action',
      },
    ])
    // The field is emptied for the next one.
    expect((wrapper.get('input').element as HTMLInputElement).value).toBe('')

    backend.on('GET /api/search', [])
    await enter('eve@example.com')
    expect(pending()[1]).toEqual({
      tempId: expect.any(String),
      user_id: undefined,
      email: 'eve@example.com',
      display_name: 'eve@example.com',
      status: 'needs_action',
    })
  })

  it('adds no one twice, and brings back a removed participant', async () => {
    fakeBackend({ 'GET /api/search': [] })
    render({ removed: ['p1'] })
    await enter('BEN@example.com')
    expect(pending()).toEqual([])
    await enter('anna@example.com')
    expect(pending()).toEqual([])
    expect(removed()).toEqual([])
  })

  it('only shows the participants to those who may not change them', () => {
    render({ canManage: false })
    expect(wrapper.find('input').exists()).toBe(false)
    expect(wrapper.find('button').exists()).toBe(false)
  })
})
