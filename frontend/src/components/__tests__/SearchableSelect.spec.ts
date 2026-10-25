import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { fakeBackend, reply, type FakeRequest } from '@/__tests__/fakeBackend'
import type { SearchResult } from '@/api'
import { i18n } from '@/i18n'
import SearchableSelect from '../SearchableSelect.vue'

const option = (id: string, label: string, extra: Partial<SearchResult> = {}): SearchResult => ({
  id,
  type: 'resource',
  label,
  subtitle: null,
  meta: null,
  ...extra,
})

const rooms = [option('r1', 'Room 1', { subtitle: 'First floor' }), option('r2', 'Room 2'), option('r3', 'Beamer')]

/** Answers a search like the server: options whose label contains the query. */
function search(request: FakeRequest) {
  const q = (request.query.get('q') ?? '').toLowerCase()
  return rooms.filter((o) => o.label.toLowerCase().includes(q))
}

let wrapper: VueWrapper

function render(props: Record<string, unknown> = {}) {
  wrapper = mount(SearchableSelect, {
    props: {
      modelValue: null,
      entity: 'resources',
      // As with v-model, the chosen value comes back.
      'onUpdate:modelValue': (value: string | null) => wrapper.setProps({ modelValue: value }),
      ...props,
    },
    global: { plugins: [i18n] },
    attachTo: document.body,
  })
  return wrapper.get('input')
}

// The list is teleported to <body>.
const listbox = () => document.querySelector<HTMLElement>('[role="listbox"]')
const optionTexts = () => [...document.querySelectorAll('[role="option"]')].map((o) => o.textContent!.trim())
const optionNamed = (text: string) =>
  [...document.querySelectorAll<HTMLElement>('[role="option"]')].find((o) => o.textContent!.includes(text))!

async function typeText(input: ReturnType<typeof render>, text: string) {
  await input.setValue(text)
  await vi.advanceTimersByTimeAsync(200)
  await flushPromises()
}

function lastEmitted(event: string) {
  const emitted = wrapper.emitted(event)!
  return emitted[emitted.length - 1]
}

describe('SearchableSelect', () => {
  beforeEach(() => {
    i18n.global.locale.value = 'en'
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
  })

  afterEach(() => {
    wrapper?.unmount()
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('loads the first options right away and lists them when focused', async () => {
    const backend = fakeBackend({ 'GET /api/search': search })
    const input = render({ openOnFocus: true, calendarId: 'c1', defaultLimit: 5 })
    await flushPromises()
    const [request] = backend.calls('GET /api/search')
    expect(Object.fromEntries(request!.query)).toEqual({ entity: 'resources', q: '', limit: '5', calendar_id: 'c1' })

    await input.trigger('focus')
    await flushPromises()
    expect(input.attributes('aria-expanded')).toBe('true')
    expect(optionTexts()).toEqual(['Room 1First floor', 'Room 2', 'Beamer'])
    expect(input.attributes('placeholder')).toBe('Search…')
  })

  it('chooses an option with the mouse', async () => {
    fakeBackend({ 'GET /api/search': search })
    const input = render({ openOnFocus: true })
    await input.trigger('focus')
    await flushPromises()
    optionNamed('Room 2').dispatchEvent(new MouseEvent('mouseenter'))
    optionNamed('Room 2').dispatchEvent(new MouseEvent('mouseup'))
    await flushPromises()
    expect(wrapper.emitted('update:modelValue')).toEqual([['r2']])
    expect(lastEmitted('select')).toEqual(['r2', rooms[1]])
    expect((input.element as HTMLInputElement).value).toBe('Room 2')
    expect(listbox()).toBeNull()
  })

  it('shows the label of a value set from outside once the options are there', async () => {
    fakeBackend({
      'GET /api/search': [option('k1', 'Meeting', { type: 'category', meta: { color: '#ff0000' } })],
    })
    const input = render({ modelValue: 'k1', entity: 'categories' })
    await flushPromises()
    expect((input.element as HTMLInputElement).value).toBe('Meeting')
    expect(wrapper.emitted('select')).toEqual([['k1', expect.objectContaining({ id: 'k1' })]])
    // The category's color shows before the label.
    expect(wrapper.find('span[aria-hidden="true"]').attributes('style')).toContain('background-color')

    await wrapper.setProps({ modelValue: null })
    expect((input.element as HTMLInputElement).value).toBe('')
    expect(wrapper.find('span[aria-hidden="true"]').exists()).toBe(false)
  })

  it('searches as one types, after a pause', async () => {
    const backend = fakeBackend({ 'GET /api/search': search })
    const input = render({ minSearchLength: 2 })
    await flushPromises()
    // Short queries don't search, not even when the field opens.
    expect(backend.calls('GET /api/search')).toHaveLength(0)
    await typeText(input, 'R')
    expect(backend.calls('GET /api/search')).toHaveLength(0)
    expect(listbox()).toBeNull()

    await input.setValue('Ro')
    await input.setValue('Roo')
    await vi.advanceTimersByTimeAsync(199)
    expect(backend.calls('GET /api/search')).toHaveLength(0)
    await vi.advanceTimersByTimeAsync(1)
    await flushPromises()
    expect(backend.calls('GET /api/search').map((r) => r.query.get('q'))).toEqual(['Roo'])
    expect(optionTexts()).toEqual(['Room 1First floor', 'Room 2'])
  })

  it('says so while loading and when nothing matches', async () => {
    let answer!: (value: SearchResult[]) => void
    fakeBackend({ 'GET /api/search': () => new Promise((resolve) => (answer = resolve)) })
    const input = render({ openOnFocus: true, minSearchLength: 0 })
    await input.trigger('focus')
    await flushPromises()
    expect(listbox()!.textContent).toContain('Loading…')
    answer([])
    await flushPromises()
    expect(listbox()!.textContent).toContain('No results')
  })

  it('shows no results when the search fails', async () => {
    fakeBackend({ 'GET /api/search': reply(500) })
    const input = render({ minSearchLength: 1 })
    await flushPromises()
    await typeText(input, 'zzz')
    expect(listbox()!.textContent).toContain('No results')
  })

  it('ignores answers to searches that were overtaken', async () => {
    const pending: Record<string, (value: SearchResult[]) => void> = {}
    fakeBackend({
      'GET /api/search': (request) => new Promise((resolve) => (pending[request.query.get('q')!] = resolve)),
    })
    const input = render({ minSearchLength: 1 })
    await typeText(input, 'Ro')
    await typeText(input, 'Be')
    pending['Be']!([rooms[2]!])
    await flushPromises()
    pending['Ro']!([rooms[0]!])
    await flushPromises()
    expect(optionTexts()).toEqual(['Beamer'])
  })

  it('moves through the options with the arrow keys and chooses with Enter', async () => {
    fakeBackend({ 'GET /api/search': search })
    const input = render()
    await flushPromises()
    // Arrow down opens the list (and searches) …
    await input.trigger('keydown', { key: 'ArrowDown' })
    await flushPromises()
    expect(input.attributes('aria-expanded')).toBe('true')
    await input.trigger('keydown', { key: 'ArrowDown' })
    await input.trigger('keydown', { key: 'ArrowDown' })
    await input.trigger('keydown', { key: 'ArrowUp' })
    expect(input.attributes('aria-activedescendant')).toBe(optionNamed('Room 2').id)
    await input.trigger('keydown', { key: 'Enter' })
    expect(lastEmitted('update:modelValue')).toEqual(['r2'])
    expect(listbox()).toBeNull()

    // … as does arrow up and Enter; Escape and Tab close it again.
    await input.trigger('keydown', { key: 'ArrowUp' })
    expect(listbox()).not.toBeNull()
    await input.trigger('keydown', { key: 'Escape' })
    expect(listbox()).toBeNull()
    await input.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(listbox()).not.toBeNull()
    await input.trigger('keydown', { key: 'Tab' })
    expect(listbox()).toBeNull()
    // The chosen option's label stays in the field.
    expect((input.element as HTMLInputElement).value).toBe('Room 2')
  })

  it('offers typed text as a value of its own where free text is allowed', async () => {
    fakeBackend({ 'GET /api/search': search })
    const input = render({ allowFreeText: true, minSearchLength: 1, freeTextValidator: (v: string) => v.includes('@') })
    await flushPromises()
    await typeText(input, 'nobody')
    expect(optionTexts()).toEqual([])
    expect(listbox()!.textContent).toContain('No results')

    await typeText(input, 'a@b.c')
    expect(optionTexts()).toEqual(['Use "a@b.c"'])
    await input.trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('update:modelValue')).toEqual([['a@b.c']])
    expect(lastEmitted('select')).toEqual(['a@b.c', null])
    expect((input.element as HTMLInputElement).value).toBe('a@b.c')

    // Text matching an option is not offered twice; the mouse picks the free text, too.
    await typeText(input, 'room 1')
    expect(optionTexts()).toEqual(['Room 1First floor'])
    await typeText(input, 'x@y.z')
    optionNamed('x@y.z').dispatchEvent(new MouseEvent('mouseenter'))
    optionNamed('x@y.z').dispatchEvent(new MouseEvent('mouseup'))
    expect(lastEmitted('update:modelValue')).toEqual(['x@y.z'])
  })

  it('takes typed text as the value right away with live free text', async () => {
    fakeBackend({ 'GET /api/search': search })
    const input = render({ allowFreeText: true, liveFreeText: true, modelValue: 'Garden' })
    await flushPromises()
    expect((input.element as HTMLInputElement).value).toBe('Garden')
    await input.setValue('Hall ')
    expect(lastEmitted('update:modelValue')).toEqual(['Hall'])
    expect(lastEmitted('select')).toEqual(['Hall', null])
    await input.setValue('')
    expect(lastEmitted('update:modelValue')).toEqual([null])
  })

  it('shows the mark of an option whose name a free-text field holds', async () => {
    fakeBackend({ 'GET /api/search': [option('l1', 'Hall', { meta: { icon: 'door-open' } })] })
    render({ allowFreeText: true, modelValue: 'hall' })
    await flushPromises()
    // The mark sits in the field, before the text.
    expect(wrapper.get('input + span svg').classes().join(' ')).toContain('door-open')
  })

  it('forgets text that matches no option when closed without free text', async () => {
    fakeBackend({ 'GET /api/search': search })
    const input = render()
    await flushPromises()
    await typeText(input, 'Beam')
    document.body.click()
    await flushPromises()
    expect(listbox()).toBeNull()
    expect((input.element as HTMLInputElement).value).toBe('')
  })

  it('clears the value with the clear button', async () => {
    fakeBackend({ 'GET /api/search': search })
    render({ modelValue: 'r1', clearable: true })
    await flushPromises()
    await wrapper.get('button[aria-label="Clear"]').trigger('click')
    expect(lastEmitted('update:modelValue')).toEqual([null])
    expect(lastEmitted('select')).toEqual([null, null])
  })

  it('neither opens nor offers clearing when disabled', async () => {
    fakeBackend({ 'GET /api/search': search })
    const input = render({ modelValue: 'r1', clearable: true, disabled: true, openOnFocus: true })
    await flushPromises()
    await input.trigger('focus')
    expect(listbox()).toBeNull()
    expect(wrapper.find('button').exists()).toBe(false)
  })

  it('closes when the page scrolls, but not when the list does', async () => {
    fakeBackend({ 'GET /api/search': search })
    const input = render({ openOnFocus: true })
    await input.trigger('focus')
    await flushPromises()
    listbox()!.dispatchEvent(new Event('scroll'))
    await flushPromises()
    expect(listbox()).not.toBeNull()
    // Clicks in the list keep it open, too.
    listbox()!.click()
    window.dispatchEvent(new Event('resize'))
    await flushPromises()
    expect(listbox()).not.toBeNull()
    document.dispatchEvent(new Event('scroll'))
    await flushPromises()
    expect(listbox()).toBeNull()
  })

  it('opens upwards where the list does not fit below the field', async () => {
    fakeBackend({ 'GET /api/search': search })
    vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function (this: Element) {
      const rect = this.tagName === 'UL' ? { top: 0, bottom: 200, height: 200 } : { top: 640, bottom: 676, height: 36 }
      return { ...rect, left: 10, right: 210, width: 200, x: 10, y: rect.top, toJSON: () => ({}) } as DOMRect
    })
    const input = render({ openOnFocus: true })
    await input.trigger('focus')
    await flushPromises()
    expect(listbox()!.style.top).toBe(`${640 - 4 - 200}px`)
    expect(listbox()!.style.width).toBe('200px')
  })
})
