import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { fakeBackend, reply } from '@/__tests__/fakeBackend'
import type * as api from '@/api'
import { i18n } from '@/i18n'
import { formatDateTime } from '@/services/datetime'
import { toasts } from '@/services/toast'
import EventActivityTab from '../EventActivityTab.vue'
import { me, signIn } from './helpers'

const comment = (id: string, authorId: string, body: string, at: string): api.EventComment => ({
  id,
  event_id: 'ev1',
  author_id: authorId,
  author_name: authorId === me.id ? 'Me Myself' : 'Anna',
  body,
  created_at: at,
})

let n = 0
const entry = (action: string, details: api.EventActivity['details'] = null, actor: string | null = 'Ben') => ({
  id: `a${++n}`,
  event_id: 'ev1',
  actor_id: null,
  actor_name: actor,
  action,
  details,
  created_at: `2026-03-01T${String(n).padStart(2, '0')}:00:00.000Z`,
})

function render(props: Partial<{ canComment: boolean; canModerate: boolean }> = {}) {
  return mount(EventActivityTab, {
    props: { eventId: 'ev1', canComment: true, canModerate: false, ...props },
    global: { plugins: [i18n] },
  })
}

const lines = (wrapper: ReturnType<typeof render>) =>
  wrapper.findAll('li > div.text-sm > span:first-child').map((span) => span.text())

describe('EventActivityTab', () => {
  beforeEach(() => {
    signIn()
    n = 0
  })

  afterEach(() => {
    vi.restoreAllMocks()
    toasts.splice(0)
  })

  it('tells what happened to the event, oldest first', async () => {
    const occurrence = { occurrence: '2026-03-10T09:00:00' }
    fakeBackend({
      'GET /api/events/ev1/comments': [],
      'GET /api/events/ev1/activity': [
        entry('created', null, null),
        entry('updated', { fields: ['title', 'start'] }),
        entry('updated', { fields: ['resource'], status: 'pending' }),
        entry('approved'),
        entry('approved', { note: 'Fine' }),
        entry('rejected'),
        entry('rejected', { note: 'Taken' }),
        entry('cancelled'),
        entry('occurrence_changed', occurrence),
        entry('occurrence_deleted', occurrence),
        entry('series_ended', {}),
        entry('something_new'),
      ].reverse(),
    })
    const wrapper = render()
    expect(wrapper.text()).toContain('Loading…')
    await flushPromises()
    expect(lines(wrapper)).toEqual([
      'Someone created this event',
      'Ben changed title, start',
      'Ben changed resource — approval required again',
      'Ben approved this event',
      'Ben approved: Fine',
      'Ben rejected this event',
      'Ben rejected: Taken',
      'Ben cancelled this event',
      'Ben changed the occurrence on 2026-03-10 09:00',
      'Ben removed the occurrence on 2026-03-10 09:00 from the series',
      'Ben ended the series as of',
      'something_new',
    ])
  })

  it('says when nothing has happened yet', async () => {
    fakeBackend({ 'GET /api/events/ev1/comments': [], 'GET /api/events/ev1/activity': [] })
    const wrapper = render({ canComment: false })
    await flushPromises()
    expect(wrapper.text()).toContain('No activity yet.')
    expect(wrapper.find('textarea').exists()).toBe(false)
  })

  it('reports when the history cannot be loaded', async () => {
    fakeBackend({
      'GET /api/events/ev1/comments': reply(500, { detail: 'Broken' }),
      'GET /api/events/ev1/activity': [],
    })
    render()
    await flushPromises()
    expect(toasts.map((t) => t.message)).toEqual(['Broken'])
  })

  it('lists comments between the activity and lets one delete only their own', async () => {
    fakeBackend({
      'GET /api/events/ev1/comments': [
        comment('c1', 'u1', 'Count me in', '2026-03-01T01:30:00.000Z'),
        comment('c2', me.id, 'Bring snacks', '2026-03-01T03:00:00.000Z'),
      ],
      'GET /api/events/ev1/activity': [entry('created'), entry('approved')],
      'DELETE /api/events/ev1/comments/*': undefined,
    })
    const wrapper = render()
    await flushPromises()
    const items = wrapper.findAll('li').map((li) => li.text())
    expect(items[0]).toContain('Ben created this event')
    expect(items[1]).toContain('Count me in')
    expect(items[2]).toContain('Ben approved this event')
    expect(items[3]).toContain('Bring snacks')
    expect(items[3]).toContain(formatDateTime('2026-03-01T03:00:00.000Z'))

    const deletes = wrapper.findAll('button').filter((b) => b.text() === 'Delete')
    expect(deletes).toHaveLength(1)
    await deletes[0]!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).not.toContain('Bring snacks')
    expect(wrapper.text()).toContain('Count me in')
  })

  it('lets moderators delete the comments of others', async () => {
    const backend = fakeBackend({
      'GET /api/events/ev1/comments': [comment('c1', 'u1', 'Count me in', '2026-03-01T01:30:00.000Z')],
      'GET /api/events/ev1/activity': [],
      'DELETE /api/events/ev1/comments/*': reply(403, { detail: 'Not allowed' }),
    })
    const wrapper = render({ canModerate: true })
    await flushPromises()
    await wrapper.get('li button').trigger('click')
    await flushPromises()
    expect(backend.calls('DELETE /api/events/ev1/comments/c1')).toHaveLength(1)
    // It failed, so the comment stays.
    expect(wrapper.text()).toContain('Count me in')
    expect(toasts.map((t) => t.message)).toEqual(['Not allowed'])
  })

  it('posts a comment and shows the comments again', async () => {
    const saved: api.EventComment[] = []
    const backend = fakeBackend({
      'GET /api/events/ev1/comments': () => saved,
      'GET /api/events/ev1/activity': [],
      'POST /api/events/ev1/comments': (request) => {
        const created = comment('c9', me.id, (request.body as { body: string }).body, '2026-03-02T00:00:00.000Z')
        saved.push(created)
        return created
      },
    })
    const wrapper = render()
    await flushPromises()
    const post = wrapper.findAll('button').find((b) => b.text() === 'Comment')!
    expect(post.attributes('disabled')).toBeDefined()
    expect(wrapper.get('textarea').attributes('aria-label')).toBe('Write a comment…')
    await wrapper.get('textarea').setValue('   ')
    expect(post.attributes('disabled')).toBeDefined()

    await wrapper.get('textarea').setValue('  See you there  ')
    await post.trigger('click')
    await flushPromises()
    expect(backend.calls('POST /api/events/ev1/comments')[0]!.body).toEqual({ body: 'See you there' })
    expect(wrapper.text()).toContain('See you there')
    expect((wrapper.get('textarea').element as HTMLTextAreaElement).value).toBe('')
  })
})
