import { beforeEach, describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import type * as api from '@/api'
import { i18n } from '@/i18n'
import ResourceIconPicker from '@/components/ResourceIconPicker.vue'
import SearchableSelect from '@/components/SearchableSelect.vue'
import { provideCalendarSettingsSync } from '@/composables/useCalendarSettingsSync'
import { fakeBackend, reply, type FakeBackend } from '@/__tests__/fakeBackend'
import {
  answerConfirm,
  buttonNamed,
  clearToasts,
  searchResult,
  toastTexts,
} from '@/components/__tests__/settingsFixtures'
import CalendarResources from '../CalendarResources.vue'

const approver = (id: string, name: string): api.Approver => ({
  user_id: id,
  display_name: name,
  email: `${id}@example.test`,
})

const resource = (id: string, name: string, overrides: Partial<api.Resource> = {}): api.Resource => ({
  id,
  calendar_id: 'cal',
  name,
  description: '',
  color: '#f59e0b',
  icon: '',
  requires_approval: false,
  is_location: false,
  is_active: true,
  approvers: [],
  created_at: '2026-03-01T08:00:00.000Z',
  updated_at: '2026-03-01T08:00:00.000Z',
  ...overrides,
})

let backend: FakeBackend

async function render(canManage = true) {
  let sync!: ReturnType<typeof provideCalendarSettingsSync>
  const Page = defineComponent({
    setup() {
      sync = provideCalendarSettingsSync()
      return () => h(CalendarResources, { calendarId: 'cal', canManage })
    },
  })
  const wrapper = mount(Page, { global: { plugins: [i18n] } })
  await flushPromises()
  return { wrapper, sync: () => sync }
}

describe('calendar resources: list and editing', () => {
  beforeEach(() => {
    i18n.global.locale.value = 'en'
    clearToasts()
    backend = fakeBackend({
      'GET /api/calendars/cal/resources': [
        resource('r1', 'Room', { description: 'Second floor', requires_approval: true }),
        resource('r2', 'Car', { requires_approval: true, approvers: [approver('kim', 'Kim')] }),
        resource('r3', 'Hall', { is_location: true, is_active: false }),
      ],
      'GET /api/calendars/cal/approvers': [approver('lea', 'Lea')],
      'GET /api/search': [],
    })
  })

  it('lists the resources with who approves them', async () => {
    const { wrapper } = await render()
    const rows = wrapper.findAll('tbody tr').map((r) => r.text())
    expect(rows[0]).toContain('Second floor')
    expect(rows[0]).toContain('Default (Lea)')
    expect(rows[1]).toContain('Kim')
    expect(rows[2]).toContain('Location')
    expect(rows[2]).toContain('No approval')
    expect(rows[2]).toContain('Inactive')
    expect(wrapper.findAll('li').map((li) => li.text())).toEqual(['LLea'])
  })

  it('says so when there are no resources and no default approvers', async () => {
    backend.on('GET /api/calendars/cal/resources', [resource('r1', 'Room', { requires_approval: true })])
    backend.on('GET /api/calendars/cal/approvers', [])
    const { wrapper } = await render()
    // Without approvers the owner decides, which the list says rather than "nobody".
    expect(wrapper.text()).toContain("Default (the calendar's owner)")
    expect(wrapper.text()).toContain("No default approvers: the calendar's owner approves bookings.")

    backend.on('GET /api/calendars/cal/resources', [])
    const empty = await render()
    expect(empty.wrapper.text()).toContain('No resources yet.')
  })

  it('offers no changes to those who cannot manage the calendar', async () => {
    const { wrapper } = await render(false)
    expect(wrapper.findComponent(SearchableSelect).exists()).toBe(false)
    expect(wrapper.findAll('button')).toHaveLength(0)
  })

  it('adds and removes default approvers', async () => {
    backend.on('PUT /api/calendars/cal/approvers', (req) =>
      (req.body as { user_ids: string[] }).user_ids.map((id) => approver(id, id === 'lea' ? 'Lea' : 'Max')),
    )
    const { wrapper } = await render()
    const select = wrapper.findComponent(SearchableSelect)
    // Someone who approves already isn't added twice.
    select.vm.$emit('select', 'lea', searchResult('lea', 'Lea'))
    await flushPromises()
    expect(backend.calls('PUT /api/calendars/cal/approvers')).toHaveLength(0)

    select.vm.$emit('select', 'max', searchResult('max', 'Max'))
    await flushPromises()
    expect(backend.calls('PUT /api/calendars/cal/approvers')[0]!.body).toEqual({ user_ids: ['lea', 'max'] })
    expect(wrapper.text()).toContain('Max')
    expect(toastTexts()).toEqual(['Approver added.'])

    await wrapper.findAll('li button[aria-label="Delete"]')[0]!.trigger('click')
    await answerConfirm(false)
    expect(backend.calls('PUT /api/calendars/cal/approvers')).toHaveLength(1)
    await wrapper.findAll('li button[aria-label="Delete"]')[0]!.trigger('click')
    await answerConfirm(true)
    expect(backend.calls('PUT /api/calendars/cal/approvers')[1]!.body).toEqual({ user_ids: ['max'] })
    expect(toastTexts()).toContain('Approver removed.')
  })

  it('adds a resource with its own approvers', async () => {
    backend.on('POST /api/calendars/cal/resources', (req) => resource('r4', (req.body as api.ResourceInput).name))
    backend.on('PUT /api/calendars/cal/resources/*/approvers', [])
    const { wrapper } = await render()
    await buttonNamed(wrapper, 'Add').trigger('click')
    expect(wrapper.text()).toContain('Add resource')
    const save = () => buttonNamed(wrapper, 'Save')
    expect(save().attributes('disabled')).toBeDefined()

    await wrapper.get('input:not([type])').setValue('Projector')
    await wrapper.get('textarea').setValue('HD')
    const pickIcon = wrapper.findComponent(ResourceIconPicker).findAll('button')[1]!
    await pickIcon.trigger('click')
    const [requiresApproval, , isLocation] = wrapper.findAll('[role="switch"]')
    await requiresApproval!.trigger('click')
    await isLocation!.trigger('click')
    expect(wrapper.text()).toContain('Default approvers')
    expect(wrapper.text()).toContain('(Lea)')
    await wrapper.get('input[value="custom"]').setValue(true)
    // Own approvers need at least one person.
    expect(wrapper.text()).toContain('Add at least one person.')
    expect(save().attributes('disabled')).toBeDefined()

    const select = wrapper.findComponent(SearchableSelect)
    select.vm.$emit('select', 'kim', searchResult('kim', 'Kim', 'kim@example.test'))
    select.vm.$emit('select', 'kim', searchResult('kim', 'Kim', 'kim@example.test'))
    select.vm.$emit('select', 'max', searchResult('max', 'Max'))
    await flushPromises()
    expect(wrapper.findAll('li').map((li) => li.text())).toEqual(['KKim', 'MMax'])
    await wrapper.findAll('li button')[1]!.trigger('click') // Max goes again
    expect(wrapper.findAll('li')).toHaveLength(1)

    await save().trigger('click')
    await flushPromises()
    expect(backend.calls('POST /api/calendars/cal/resources')[0]!.body).toEqual({
      name: 'Projector',
      description: 'HD',
      color: '#f59e0b',
      icon: pickIcon.attributes('aria-label'),
      requires_approval: true,
      is_location: true,
      is_active: true,
    })
    expect(backend.calls('PUT /api/calendars/cal/resources/r4/approvers')[0]!.body).toEqual({ user_ids: ['kim'] })
    expect(toastTexts()).toEqual(['Resource saved.'])
    expect(wrapper.find('table').exists()).toBe(true)
  })

  it('edits a resource, sending its approvers only when they changed', async () => {
    backend.on('PATCH /api/calendars/cal/resources/*', (req) => resource(req.path.split('/').at(-1)!, 'x'))
    backend.on('PUT /api/calendars/cal/resources/*/approvers', [])
    const { wrapper } = await render()
    const edit = () => wrapper.findAll('button[aria-label="Edit"]')
    await edit()[1]!.trigger('click') // Car, approved by Kim
    expect(wrapper.text()).toContain('Edit resource')
    expect((wrapper.get('input[value="custom"]').element as HTMLInputElement).checked).toBe(true)
    await wrapper.get('input:not([type])').setValue('Van')
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(backend.calls('PATCH /api/calendars/cal/resources/r2')[0]!.body).toMatchObject({ name: 'Van' })
    expect(backend.calls('PUT /api/calendars/cal/resources/*/approvers')).toHaveLength(0)

    // Approval no longer required: the own approvers go, the defaults take over.
    await edit()[1]!.trigger('click')
    await wrapper.findAll('[role="switch"]')[0]!.trigger('click')
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(backend.calls('PUT /api/calendars/cal/resources/r2/approvers')[0]!.body).toEqual({ user_ids: [] })
  })

  it('cancels editing without saving', async () => {
    const { wrapper } = await render()
    await wrapper.findAll('button[aria-label="Edit"]')[0]!.trigger('click')
    await buttonNamed(wrapper, 'Cancel').trigger('click')
    expect(wrapper.find('table').exists()).toBe(true)
    expect(backend.requests.filter((r) => r.method !== 'GET')).toHaveLength(0)
  })

  it('keeps the form open when saving fails', async () => {
    backend.on('PATCH /api/calendars/cal/resources/*', reply(500))
    const { wrapper } = await render()
    await wrapper.findAll('button[aria-label="Edit"]')[0]!.trigger('click')
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(toastTexts()).toEqual(['Could not save the changes.'])
    expect(wrapper.text()).toContain('Edit resource')
  })

  it('drops removed members from the approvers of the resource being edited', async () => {
    const { wrapper, sync } = await render()
    await wrapper.findAll('button[aria-label="Edit"]')[1]!.trigger('click') // Car, approved by Kim
    await wrapper.get('input:not([type])').setValue('Van')
    wrapper.findComponent(SearchableSelect).vm.$emit('select', 'max', searchResult('max', 'Max'))
    await flushPromises()

    backend.on('GET /api/calendars/cal/resources', [resource('r2', 'Car', { requires_approval: true })])
    sync().membersChanged()
    await flushPromises()
    // Kim was removed; Max, picked here, and the new name stay.
    expect(wrapper.findAll('li').map((li) => li.text())).toEqual(['MMax'])
    expect((wrapper.get('input:not([type])').element as HTMLInputElement).value).toBe('Van')
  })

  it('deletes a resource once confirmed, and reports a failure', async () => {
    backend.on('DELETE /api/calendars/cal/resources/*', undefined)
    const { wrapper } = await render()
    const remove = () => wrapper.findAll('td button[aria-label="Delete"]')[2]!
    await remove().trigger('click')
    await answerConfirm(false)
    expect(backend.calls('DELETE /api/calendars/cal/resources/*')).toHaveLength(0)
    await remove().trigger('click')
    await answerConfirm(true)
    expect(backend.calls('DELETE /api/calendars/cal/resources/r3')).toHaveLength(1)

    backend.on('DELETE /api/calendars/cal/resources/*', reply(500))
    await remove().trigger('click')
    await answerConfirm(true)
    expect(toastTexts()).toEqual(['Could not remove the item.'])
  })
})
