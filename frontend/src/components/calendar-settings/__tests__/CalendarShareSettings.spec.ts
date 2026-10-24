import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type * as api from '@/api'
import { i18n } from '@/i18n'
import { realtime } from '@/services/realtime'
import { useAuthStore } from '@/stores/auth'
import { fakeBackend, reply, type FakeBackend } from '@/__tests__/fakeBackend'
import {
  answerConfirm,
  buttonNamed,
  calendar,
  clearToasts,
  toastTexts,
  user,
} from '@/components/__tests__/settingsFixtures'
import CalendarShareSettings from '../CalendarShareSettings.vue'

let backend: FakeBackend
const writeText = vi.fn<(text: string) => Promise<void>>()

async function render(props: { canManage?: boolean; calendar?: api.Calendar } = {}) {
  const wrapper = mount(CalendarShareSettings, {
    props: { calendar: props.calendar ?? calendar(), canManage: props.canManage ?? true },
    global: { plugins: [i18n] },
  })
  await flushPromises()
  return wrapper
}

const origin = window.location.origin
const copyButtons = (wrapper: Awaited<ReturnType<typeof render>>) => wrapper.findAll('button[aria-label="Copy URL"]')

describe('calendar share settings', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    i18n.global.locale.value = 'en'
    clearToasts()
    vi.spyOn(realtime, 'start').mockImplementation(() => {})
    vi.spyOn(realtime, 'stop').mockImplementation(() => {})
    useAuthStore().user = user()
    writeText.mockReset().mockResolvedValue()
    Object.assign(navigator, { clipboard: { writeText } })
    backend = fakeBackend({
      'GET /api/calendars/cal/feed-url': { feed_url: 'https://cal.test/feed/abc.ics' },
      'PATCH /api/calendars/cal': (req) => calendar(req.body as Partial<api.Calendar>),
    })
  })

  afterEach(() => vi.restoreAllMocks())

  it('shows the feed and CalDAV addresses', async () => {
    const wrapper = await render()
    expect(wrapper.text()).toContain('https://cal.test/feed/abc.ics')
    expect(wrapper.text()).toContain(`${origin}/caldav/ann@example.test/cal`)
    expect(wrapper.text()).toContain(`${origin}/calendar/`)
  })

  it('copies each address', async () => {
    const wrapper = await render({ calendar: calendar({ url_path: 'team' }) })
    const [page, feed, caldav] = copyButtons(wrapper)
    await page!.trigger('click')
    await feed!.trigger('click')
    await caldav!.trigger('click')
    await flushPromises()
    expect(writeText.mock.calls.map(([text]) => text)).toEqual([
      `${origin}/calendar/team`,
      'https://cal.test/feed/abc.ics',
      `${origin}/caldav/ann@example.test/cal`,
    ])
    expect(toastTexts()).toContain('URL copied.')
  })

  it('copies the address by id while the calendar has no URL of its own', async () => {
    const wrapper = await render()
    await copyButtons(wrapper)[0]!.trigger('click')
    expect(writeText).toHaveBeenCalledWith(`${origin}/calendar/cal`)
  })

  it('saves its own URL, and clears it', async () => {
    const wrapper = await render()
    const input = wrapper.get('#calendar-url')
    expect(buttonNamed(wrapper, 'Clear').attributes('disabled')).toBeDefined()
    await input.setValue('team-a')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(backend.calls('PATCH /api/calendars/cal')[0]!.body).toEqual({ url_path: 'team-a' })
    expect(wrapper.emitted('updated')![0]![0]).toMatchObject({ url_path: 'team-a' })
    expect(toastTexts()).toEqual(['Calendar URL saved.'])

    await buttonNamed(wrapper, 'Clear').trigger('click')
    await flushPromises()
    expect(backend.calls('PATCH /api/calendars/cal')[1]!.body).toEqual({ url_path: null })
    expect((input.element as HTMLInputElement).value).toBe('')
  })

  it('reports a URL that is taken', async () => {
    backend.on('PATCH /api/calendars/cal', reply(409, { detail: 'This URL is taken.' }))
    const wrapper = await render()
    await wrapper.get('#calendar-url').setValue('taken')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(toastTexts()).toEqual(['This URL is taken.'])
  })

  it('regenerates the feed token once confirmed', async () => {
    backend.on('POST /api/calendars/cal/feed-token/rotate', { feed_url: 'https://cal.test/feed/new.ics' })
    const wrapper = await render()
    await buttonNamed(wrapper, 'Regenerate token').trigger('click')
    await answerConfirm(false)
    expect(backend.calls('POST /api/calendars/cal/feed-token/rotate')).toHaveLength(0)

    await buttonNamed(wrapper, 'Regenerate token').trigger('click')
    await answerConfirm(true)
    expect(wrapper.text()).toContain('https://cal.test/feed/new.ics')
    expect(toastTexts()).toEqual(['Feed token regenerated.'])
  })

  it('lets only managers change the URL', async () => {
    const wrapper = await render({ canManage: false })
    expect(wrapper.get('#calendar-url').attributes('disabled')).toBeDefined()
    expect(wrapper.find('button[aria-label="Save"]').exists()).toBe(false)
    expect(wrapper.find('button[aria-label="Clear"]').exists()).toBe(false)
  })
})
