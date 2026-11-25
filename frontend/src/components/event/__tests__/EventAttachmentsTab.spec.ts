import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import type * as api from '@/api'
import type { PendingAttachment } from '@/composables/useEventExtras'
import { i18n } from '@/i18n'
import EventAttachmentsTab from '../EventAttachmentsTab.vue'

const file: api.Attachment = {
  id: 'a1',
  kind: 'file',
  name: 'Agenda.pdf',
  url: '/api/attachments/a1/download',
  content_type: 'application/pdf',
  size: 1536,
  added_by_name: 'Anna',
  created_at: '2026-03-01T08:00:00Z',
}
const link: api.Attachment = {
  id: 'a2',
  kind: 'link',
  name: 'Slides',
  url: 'https://example.org/slides',
  content_type: '',
  size: 0,
  added_by_name: null,
  created_at: '2026-03-01T09:00:00Z',
}

interface State {
  saved: api.Attachment[] | null
  pending: PendingAttachment[]
  removed: string[]
}

function render(options: { saved?: api.Attachment[] | null; canManage?: boolean; eventId?: string | null } = {}) {
  const state: State = { saved: options.saved === undefined ? [file, link] : options.saved, pending: [], removed: [] }
  const wrapper = mount(EventAttachmentsTab, {
    props: {
      eventId: options.eventId === undefined ? 'ev1' : options.eventId,
      canManage: options.canManage ?? true,
      saved: state.saved,
      pending: state.pending,
      removed: state.removed,
      'onUpdate:pending': (value: PendingAttachment[]) => {
        state.pending = value
        void wrapper.setProps({ pending: value })
      },
      'onUpdate:removed': (value: string[]) => {
        state.removed = value
        void wrapper.setProps({ removed: value })
      },
    },
    global: { plugins: [i18n] },
  })
  return { wrapper, state }
}

const rows = (wrapper: ReturnType<typeof render>['wrapper']) => wrapper.findAll('li')

describe('EventAttachmentsTab', () => {
  it('lists files to download and links to open, with their size and who added them', () => {
    const { wrapper } = render()
    const [pdf, slides] = rows(wrapper)
    expect(pdf!.attributes('data-kind')).toBe('file')
    const pdfLink = pdf!.get('a')
    expect(pdfLink.text()).toBe('Agenda.pdf')
    expect(pdfLink.attributes('href')).toBe('/api/attachments/a1/download')
    expect(pdfLink.attributes('download')).toBe('Agenda.pdf')
    expect(pdfLink.attributes('target')).toBeUndefined()
    expect(pdf!.text()).toContain('1.5 kB · Added by Anna')

    expect(slides!.attributes('data-kind')).toBe('link')
    const slidesLink = slides!.get('a')
    expect(slidesLink.attributes('href')).toBe('https://example.org/slides')
    expect(slidesLink.attributes('target')).toBe('_blank')
    expect(slidesLink.attributes('rel')).toBe('noopener noreferrer')
  })

  it('says when there is nothing, and waits for what is loading', () => {
    expect(render({ saved: [] }).wrapper.text()).toContain('No attachments yet.')
    expect(render({ saved: null }).wrapper.text()).toContain('Loading…')
    // A new event has nothing to load.
    expect(render({ saved: null, eventId: null }).wrapper.text()).toContain('No attachments yet.')
  })

  it('removes saved attachments when the event is saved', async () => {
    const { wrapper, state } = render()
    await wrapper.get('button[aria-label="Remove Agenda.pdf"]').trigger('click')
    expect(state.removed).toEqual(['a1'])
    expect(rows(wrapper).map((row) => row.get('a').text())).toEqual(['Slides'])
  })

  it('takes files picked, to be sent with the event', async () => {
    const { wrapper, state } = render({ saved: [] })
    const input = wrapper.get<HTMLInputElement>('input[type="file"]')
    const picked = [new File(['a'], 'a.txt'), new File(['bb'], 'b.png')]
    Object.defineProperty(input.element, 'files', { value: picked, configurable: true })
    await input.trigger('change')
    expect(state.pending.map((p) => [p.kind, p.name])).toEqual([
      ['file', 'a.txt'],
      ['file', 'b.png'],
    ])
    expect(input.element.value).toBe('')
    const [first] = rows(wrapper)
    expect(first!.attributes('data-pending')).toBe('true')
    expect(first!.find('a').exists()).toBe(false)
    expect(first!.text()).toContain('1 byte · added when the event is saved')
    await wrapper.get('button[aria-label="Remove a.txt"]').trigger('click')
    expect(state.pending.map((p) => p.name)).toEqual(['b.png'])
  })

  it('adds web links, named by their title or their address', async () => {
    const { wrapper, state } = render({ saved: [] })
    const [url, name] = wrapper.findAll('form input')
    const button = wrapper.get('form button[type="submit"]')
    expect(button.attributes('disabled')).toBeDefined()

    await url!.setValue('  https://example.org/plan ')
    await name!.setValue(' The plan ')
    await wrapper.get('form').trigger('submit')
    await url!.setValue('https://example.org/bare')
    await wrapper.get('form').trigger('submit')
    expect(state.pending.map((p) => (p.kind === 'link' ? [p.url, p.name] : null))).toEqual([
      ['https://example.org/plan', 'The plan'],
      ['https://example.org/bare', 'https://example.org/bare'],
    ])
    expect((url!.element as HTMLInputElement).value).toBe('')
  })

  it('refuses what is not a web link, until it is changed', async () => {
    const { wrapper, state } = render({ saved: [] })
    const [url] = wrapper.findAll('form input')
    await url!.setValue('javascript:alert(1)')
    await wrapper.get('form').trigger('submit')
    expect(state.pending).toEqual([])
    expect(wrapper.get('[role="alert"]').text()).toBe('Enter an address that starts with http:// or https://.')
    expect(url!.attributes('aria-invalid')).toBe('true')
    await url!.setValue('https://example.org')
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })

  it('offers no changes to who may not change the event', () => {
    const { wrapper } = render({ canManage: false })
    expect(rows(wrapper)).toHaveLength(2)
    expect(wrapper.find('input').exists()).toBe(false)
    expect(wrapper.find('button').exists()).toBe(false)
  })
})
