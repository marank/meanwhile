import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { fakeBackend, reply, type FakeRequest } from '@/__tests__/fakeBackend'
import type { SearchResult } from '@/api'
import { i18n } from '@/i18n'
import AccessGrantSearch from '../AccessGrantSearch.vue'

const result = (id: string, label: string, subtitle: string | null = null): SearchResult => ({
  id,
  type: 'user',
  label,
  subtitle,
  meta: null,
})

const users = [result('u1', 'Anna', 'anna@example.com'), result('u2', 'Ben', 'ben@example.com')]
const groups = [result('g1', 'Staff')]

function search(request: FakeRequest) {
  return request.query.get('entity') === 'groups' ? groups : users
}

let wrapper: VueWrapper

function render(props: Record<string, unknown> = {}) {
  wrapper = mount(AccessGrantSearch, {
    props: {
      placeholder: 'Add people',
      excludeUserIds: new Set<string>(),
      excludeGroupIds: new Set<string>(),
      ...props,
    },
    global: { plugins: [i18n] },
    attachTo: document.body,
  })
  return wrapper.get('input')
}

// Name, email (if any) and kind of each option.
const optionTexts = () =>
  wrapper.findAll('[role="option"]').map((o) =>
    o
      .findAll('span')
      .filter((span) => !span.find('span').exists() && span.text())
      .map((span) => span.text())
      .join(' '),
  )

describe('AccessGrantSearch', () => {
  beforeEach(() => {
    i18n.global.locale.value = 'en'
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
  })

  afterEach(() => {
    wrapper.unmount()
    vi.useRealTimers()
  })

  it('lists users and groups when focused, leaving out those listed already', async () => {
    const backend = fakeBackend({ 'GET /api/search': search })
    const input = render({ groups: true, excludeUserIds: new Set(['u2']) })
    expect(input.attributes('placeholder')).toBe('Add people')
    expect(input.attributes('aria-label')).toBe('Add people')
    await input.trigger('focus')
    await flushPromises()
    expect(wrapper.get('[role="listbox"]').attributes('id')).toBe(input.attributes('aria-controls'))
    expect(backend.calls('GET /api/search').map((r) => r.query.get('entity'))).toEqual(['users', 'groups'])
    expect(optionTexts()).toEqual(['Staff Group', 'Anna anna@example.com User'])
  })

  it('searches users only once two letters are typed', async () => {
    const backend = fakeBackend({ 'GET /api/search': search })
    const input = render()
    await input.setValue('A')
    await vi.advanceTimersByTimeAsync(200)
    await flushPromises()
    // One letter asks for no one.
    expect(backend.calls('GET /api/search')).toHaveLength(0)
    expect(wrapper.text()).toContain('No results')

    await input.setValue('An')
    await vi.advanceTimersByTimeAsync(200)
    await flushPromises()
    expect(backend.calls('GET /api/search').map((r) => r.query.get('q'))).toEqual(['An'])
    expect(optionTexts()).toHaveLength(2)
  })

  it('shows that it is loading, and no results when the search fails', async () => {
    let fail!: () => void
    fakeBackend({ 'GET /api/search': () => new Promise((resolve) => (fail = () => resolve(reply(500)))) })
    const input = render()
    await input.trigger('focus')
    expect(wrapper.text()).toContain('Loading…')
    fail()
    await flushPromises()
    expect(wrapper.text()).toContain('No results')
  })

  it('picks with the mouse and empties the field', async () => {
    fakeBackend({ 'GET /api/search': search })
    const input = render()
    await input.trigger('focus')
    await flushPromises()
    const ben = wrapper.findAll('[role="option"]')[1]!
    await ben.trigger('mouseenter')
    expect(ben.attributes('aria-selected')).toBe('true')
    await ben.trigger('mouseup')
    expect(wrapper.emitted('pick')).toEqual([[{ kind: 'user', id: 'u2', label: 'Ben', subtitle: 'ben@example.com' }]])
    expect((input.element as HTMLInputElement).value).toBe('')
    expect(wrapper.find('[role="listbox"]').exists()).toBe(false)
  })

  it('moves with the arrow keys and picks with Enter', async () => {
    fakeBackend({ 'GET /api/search': search })
    const input = render()
    // An arrow key opens the list first.
    await input.trigger('keydown', { key: 'ArrowDown' })
    await flushPromises()
    expect(input.attributes('aria-expanded')).toBe('true')
    await input.trigger('keydown', { key: 'ArrowDown' })
    await input.trigger('keydown', { key: 'ArrowDown' })
    await input.trigger('keydown', { key: 'ArrowDown' })
    await input.trigger('keydown', { key: 'ArrowUp' })
    await input.trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('pick')![0]![0]).toMatchObject({ id: 'u1' })
  })

  it('picks the only result with Enter', async () => {
    fakeBackend({ 'GET /api/search': [users[0]] })
    const input = render()
    await input.trigger('focus')
    await flushPromises()
    await input.trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('pick')![0]![0]).toMatchObject({ id: 'u1' })
  })

  it('picks nothing with Enter among several results', async () => {
    fakeBackend({ 'GET /api/search': search })
    const input = render()
    await input.trigger('focus')
    await flushPromises()
    await input.trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('pick')).toBeUndefined()
  })

  it('closes with Escape, Tab, a click elsewhere and scrolling the page', async () => {
    fakeBackend({ 'GET /api/search': search })
    const input = render()
    const isOpen = () => wrapper.find('[role="listbox"]').exists()
    const closers: (() => unknown)[] = [
      () => input.trigger('keydown', { key: 'Escape' }),
      () => input.trigger('keydown', { key: 'Tab' }),
      () => document.body.click(),
      () => document.dispatchEvent(new Event('scroll')),
    ]
    for (const close of closers) {
      await input.trigger('focus')
      await flushPromises()
      expect(isOpen()).toBe(true)
      // Scrolling the list itself and clicking in it keep it open.
      const list = wrapper.get('[role="listbox"]').element as HTMLElement
      list.dispatchEvent(new Event('scroll'))
      list.click()
      await flushPromises()
      expect(isOpen()).toBe(true)
      await close()
      await flushPromises()
      expect(isOpen()).toBe(false)
    }
  })

  it('does not open when disabled', async () => {
    const backend = fakeBackend({ 'GET /api/search': search })
    const input = render({ disabled: true })
    await input.trigger('focus')
    expect(wrapper.find('[role="listbox"]').exists()).toBe(false)
    expect(backend.requests).toHaveLength(0)
  })
})
