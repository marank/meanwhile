import { beforeEach, describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, h } from 'vue'
import type * as api from '@/api'
import { i18n } from '@/i18n'
import AccessGrantSearch from '@/components/AccessGrantSearch.vue'
import RoleSelect from '@/components/RoleSelect.vue'
import { provideCalendarSettingsSync } from '@/composables/useCalendarSettingsSync'
import { fakeBackend, reply, type FakeBackend } from '@/__tests__/fakeBackend'
import { buttonNamed, calendar, clearToasts, member, toastTexts } from '@/components/__tests__/settingsFixtures'
import CalendarAccessSettings from '../CalendarAccessSettings.vue'

const groupLink = (
  id: string,
  name: string,
  role: api.GrantableRole,
  members: api.CalendarGroupLink['members'],
): api.CalendarGroupLink => ({ id, group: { id: `g-${id}`, name }, role, members })

const person = (id: string, name: string) => ({ id, display_name: name, email: `${id}@example.test` })

let backend: FakeBackend

function render(props: { canManage?: boolean; calendar?: api.Calendar } = {}) {
  let sync!: ReturnType<typeof provideCalendarSettingsSync>
  const Page = defineComponent({
    setup() {
      sync = provideCalendarSettingsSync()
      return () =>
        h(CalendarAccessSettings, {
          calendar: props.calendar ?? calendar(),
          canManage: props.canManage ?? true,
          onUpdated: (c: api.Calendar) => updated.push(c),
        })
    },
  })
  const updated: api.Calendar[] = []
  const wrapper = mount(Page, { global: { plugins: [i18n] }, attachTo: document.body })
  return { wrapper, updated, sync: () => sync }
}

describe('calendar access settings', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    i18n.global.locale.value = 'en'
    clearToasts()
    backend = fakeBackend({
      'GET /api/calendars/cal/members': [member('ann', 'Ann', 'owner'), member('bob', 'Bob', 'read')],
      'GET /api/calendars/cal/groups': [groupLink('l1', 'Sales', 'full', [person('bob', 'Bob'), person('cy', 'Cy')])],
      'GET /api/search': [],
    })
  })

  it('lists members and groups with their roles, and explains the roles', async () => {
    const { wrapper } = render()
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('Can view events.')
    expect(text).toContain('Ann')
    expect(text).toContain('Owner')
    expect(text).toContain('Bob')
    expect(text).toContain('Sales')
    expect(text).toContain('2 members')
    // The owner's role can't be changed: one role field for Bob, one for the group.
    expect(wrapper.findAllComponents(RoleSelect)).toHaveLength(2)
    wrapper.unmount()
  })

  it('shows read-only access to non-managers, without group links', async () => {
    const { wrapper } = render({ canManage: false })
    await flushPromises()
    expect(wrapper.text()).toContain('Read only')
    expect(wrapper.findComponent(AccessGrantSearch).exists()).toBe(false)
    expect(wrapper.find('[role="switch"]').exists()).toBe(false)
    expect(wrapper.findAll('button').some((b) => b.text() === 'Save')).toBe(false)
    expect(backend.calls('GET /api/calendars/cal/groups')).toHaveLength(0)
    wrapper.unmount()
  })

  it('says so when nobody has access', async () => {
    backend.on('GET /api/calendars/cal/members', [])
    backend.on('GET /api/calendars/cal/groups', [])
    const { wrapper } = render()
    await flushPromises()
    expect(wrapper.text()).toContain('No members yet.')
    wrapper.unmount()
  })

  it('shows who is in a group, and whose role is set elsewhere', async () => {
    backend.on('GET /api/calendars/cal/groups', [
      groupLink('l1', 'Sales', 'read', [person('bob', 'Bob'), person('cy', 'Cy'), person('di', 'Di')]),
      groupLink('l2', 'Leads', 'manage', [person('di', 'Di')]),
      groupLink('l3', 'Empty', 'read', []),
    ])
    const { wrapper } = render()
    await flushPromises()
    const toggles = wrapper.findAll('button[aria-expanded]:not([role])')
    await toggles[0]!.trigger('click')
    expect(toggles[0]!.attributes('aria-expanded')).toBe('true')
    const rows = wrapper.findAll('li li')
    // Bob is a member himself, Di gets more through Leads; Cy has the group's role.
    const row = (name: string) => rows.find((r) => r.text().includes(name))!
    expect(row('Bob').text()).toContain('overridden')
    expect(row('Di').text()).toContain('overridden')
    expect(row('Cy').text()).not.toContain('overridden')

    await toggles[2]!.trigger('click')
    expect(wrapper.text()).toContain('This group has no members.')
    await toggles[0]!.trigger('click')
    expect(toggles[0]!.attributes('aria-expanded')).toBe('false')
    wrapper.unmount()
  })

  it('sends nothing until saved, then only what changed', async () => {
    backend.on('GET /api/groups/*', { id: 'g-new', name: 'Ops', description: null, members: [person('ed', 'Ed')] })
    backend.on('PATCH /api/calendars/cal', (req) => calendar(req.body as Partial<api.Calendar>))
    backend.on('DELETE /api/calendars/cal/members/*', undefined)
    backend.on('POST /api/calendars/cal/members', {})
    backend.on('PATCH /api/calendars/cal/groups/*', {})
    backend.on('POST /api/calendars/cal/groups', {})
    const { wrapper, updated, sync } = render()
    await flushPromises()

    // Public, with its own role
    await wrapper.get('[role="switch"]').trigger('click')
    const publicRole = wrapper.findAllComponents(RoleSelect)[0]!
    publicRole.vm.$emit('update:modelValue', 'own')
    // Bob goes, Dan comes, the group gets another role, and a new group is linked.
    await buttonNamed(wrapper, 'Delete').trigger('click')
    const search = wrapper.findComponent(AccessGrantSearch)
    search.vm.$emit('pick', { kind: 'user', id: 'dan', label: 'Dan', subtitle: 'dan@example.test' })
    search.vm.$emit('pick', { kind: 'group', id: 'g-new', label: 'Ops', subtitle: null })
    await flushPromises()
    expect(wrapper.text()).toContain('Dan')
    expect(wrapper.text()).toContain('Ops')
    const roles = wrapper.findAllComponents(RoleSelect)
    // public role, Dan, Sales, Ops
    roles[2]!.vm.$emit('update:modelValue', 'manage')
    await flushPromises()
    expect(backend.requests.filter((r) => r.method !== 'GET')).toHaveLength(0)

    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(backend.calls('PATCH /api/calendars/cal')[0]!.body).toEqual({ is_public: true, public_role: 'own' })
    expect(updated[0]!.is_public).toBe(true)
    expect(backend.calls('DELETE /api/calendars/cal/members/bob')).toHaveLength(1)
    expect(backend.calls('POST /api/calendars/cal/members')[0]!.body).toEqual({ user_id: 'dan', role: 'read' })
    expect(backend.calls('PATCH /api/calendars/cal/groups/l1')[0]!.body).toEqual({ role: 'manage' })
    expect(backend.calls('POST /api/calendars/cal/groups')[0]!.body).toEqual({ group_id: 'g-new', role: 'read' })
    expect(backend.unhandled).toEqual([])
    expect(toastTexts()).toContain('Access settings saved.')
    // The other tabs hear that members changed.
    expect(sync().membersVersion.value).toBe(1)
    // What is shown afterwards is what the server has.
    expect(backend.calls('GET /api/calendars/cal/members')).toHaveLength(2)
    wrapper.unmount()
  })

  it('changes a role and removes a group link', async () => {
    backend.on('PATCH /api/calendars/cal/members/*', {})
    backend.on('DELETE /api/calendars/cal/groups/*', undefined)
    const { wrapper, sync } = render()
    await flushPromises()
    wrapper.findAllComponents(RoleSelect)[0]!.vm.$emit('update:modelValue', 'full')
    await flushPromises()
    const deletes = wrapper.findAll('button[aria-label="Delete"]')
    await deletes[1]!.trigger('click') // the group
    expect(wrapper.text()).not.toContain('Sales')

    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(backend.calls('PATCH /api/calendars/cal/members/bob')[0]!.body).toEqual({ role: 'full' })
    expect(backend.calls('DELETE /api/calendars/cal/groups/l1')).toHaveLength(1)
    expect(backend.calls('PATCH /api/calendars/cal')).toHaveLength(0)
    // A role change isn't a change of who is a member.
    expect(sync().membersVersion.value).toBe(0)
    wrapper.unmount()
  })

  it('takes back what was saved when someone removed is picked again', async () => {
    const { wrapper } = render()
    await flushPromises()
    await buttonNamed(wrapper, 'Delete').trigger('click')
    await wrapper.findAll('button[aria-label="Delete"]')[0]!.trigger('click') // the group
    const search = wrapper.findComponent(AccessGrantSearch)
    search.vm.$emit('pick', { kind: 'user', id: 'bob', label: 'Bob', subtitle: null })
    search.vm.$emit('pick', { kind: 'group', id: 'g-l1', label: 'Sales', subtitle: null })
    await flushPromises()
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(backend.requests.filter((r) => r.method !== 'GET')).toEqual([])
    expect(wrapper.text()).toContain('Bob')
    expect(wrapper.text()).toContain('Sales')
    wrapper.unmount()
  })

  it('links a group whose members cannot be loaded', async () => {
    backend.on('GET /api/groups/*', reply(500))
    const { wrapper } = render()
    await flushPromises()
    wrapper.findComponent(AccessGrantSearch).vm.$emit('pick', { kind: 'group', id: 'g-x', label: 'X', subtitle: null })
    await flushPromises()
    expect(wrapper.text()).toContain('No members')
    wrapper.unmount()
  })

  it('makes a public calendar private, without a role', async () => {
    backend.on('PATCH /api/calendars/cal', (req) => calendar(req.body as Partial<api.Calendar>))
    const { wrapper } = render({ calendar: calendar({ is_public: true, public_role: 'own' }) })
    await flushPromises()
    await wrapper.get('[role="switch"]').trigger('click')
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(backend.calls('PATCH /api/calendars/cal')[0]!.body).toEqual({ is_public: false })
    wrapper.unmount()
  })

  it('reports a failed save and shows what was saved', async () => {
    backend.on('DELETE /api/calendars/cal/members/*', reply(500))
    const { wrapper } = render()
    await flushPromises()
    await buttonNamed(wrapper, 'Delete').trigger('click')
    expect(wrapper.text()).not.toContain('Bob')
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(toastTexts()).toContain('Could not save the changes.')
    expect(wrapper.text()).toContain('Bob')
    wrapper.unmount()
  })
})
