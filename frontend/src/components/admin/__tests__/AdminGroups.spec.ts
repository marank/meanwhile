import { beforeEach, describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import type * as api from '@/api'
import { i18n } from '@/i18n'
import SearchableSelect from '@/components/SearchableSelect.vue'
import { fakeBackend, reply, type FakeBackend } from '@/__tests__/fakeBackend'
import {
  answerConfirm,
  buttonNamed,
  clearToasts,
  searchResult,
  toastTexts,
} from '@/components/__tests__/settingsFixtures'
import AdminGroups from '../AdminGroups.vue'

const group = (id: string, name: string, description: string, count = 0): api.UserGroup => ({
  id,
  name,
  description,
  member_count: count,
})

let backend: FakeBackend

async function render() {
  const wrapper = mount(AdminGroups, { global: { plugins: [i18n] } })
  await flushPromises()
  return wrapper
}

/** Picks a user in the member search, as if found and chosen there. */
async function pickUser(wrapper: Awaited<ReturnType<typeof render>>, id: string, name: string) {
  const select = wrapper.findComponent(SearchableSelect)
  select.vm.$emit('update:modelValue', id)
  select.vm.$emit('select', id, searchResult(id, name, `${id}@example.test`))
  await flushPromises()
}

describe('admin groups', () => {
  beforeEach(() => {
    i18n.global.locale.value = 'en'
    clearToasts()
    backend = fakeBackend({
      'GET /api/groups': [group('g1', 'Sales', 'The sales team', 2), group('g2', 'Ops', '')],
      'GET /api/groups/g1': {
        ...group('g1', 'Sales', 'The sales team', 2),
        members: [{ id: 'bob', display_name: 'Bob', email: 'bob@example.test' }],
      },
      'GET /api/search': [],
    })
  })

  it('lists the groups with their member counts', async () => {
    const wrapper = await render()
    expect(wrapper.findAll('tbody tr').map((r) => r.text())).toEqual(['SalesThe sales team2', 'Ops—0'])
  })

  it('says so when there are none', async () => {
    backend.on('GET /api/groups', [])
    const wrapper = await render()
    expect(wrapper.text()).toContain('No groups yet.')
  })

  it('adds a group with members', async () => {
    backend.on('POST /api/groups', {})
    const wrapper = await render()
    await buttonNamed(wrapper, 'Add group').trigger('click')
    expect(wrapper.find('h2').text()).toBe('Add group')
    expect(wrapper.text()).toContain('No members yet.')
    const add = () => wrapper.get('button[aria-label="Add member"]')
    expect(add().attributes('disabled')).toBeDefined()

    await wrapper.get('input:not([type])').setValue('Leads')
    await pickUser(wrapper, 'kim', 'Kim')
    await add().trigger('click')
    // Someone in the group already isn't added twice.
    await pickUser(wrapper, 'kim', 'Kim')
    await add().trigger('click')
    await pickUser(wrapper, 'max', 'Max')
    await add().trigger('click')
    expect(wrapper.findAll('li').map((li) => li.text())).toEqual(['Kimkim@example.test', 'Maxmax@example.test'])
    await wrapper.findAll('li button[aria-label="Remove member"]')[1]!.trigger('click')

    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(backend.calls('POST /api/groups')[0]!.body).toEqual({
      name: 'Leads',
      description: '',
      member_ids: ['kim'],
    })
    expect(wrapper.find('table').exists()).toBe(true)
    expect(backend.calls('GET /api/groups')).toHaveLength(2)
  })

  it('edits a group with its current members', async () => {
    backend.on('PATCH /api/groups/*', {})
    const wrapper = await render()
    await wrapper.findAll('button[aria-label="Edit"]')[0]!.trigger('click')
    await flushPromises()
    expect(wrapper.find('h2').text()).toBe('Edit group')
    expect((wrapper.get('textarea').element as HTMLTextAreaElement).value).toBe('The sales team')
    expect(wrapper.text()).toContain('Bob')
    await wrapper.get('textarea').setValue('Sellers')
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(backend.calls('PATCH /api/groups/g1')[0]!.body).toEqual({
      name: 'Sales',
      description: 'Sellers',
      member_ids: ['bob'],
    })
  })

  it('stays on the list when a group cannot be loaded, and cancels editing', async () => {
    backend.on('GET /api/groups/g2', reply(500))
    const wrapper = await render()
    await wrapper.findAll('button[aria-label="Edit"]')[1]!.trigger('click')
    await flushPromises()
    expect(toastTexts()).toEqual(['Could not load the requested settings.'])
    expect(wrapper.find('table').exists()).toBe(true)

    await wrapper.findAll('button[aria-label="Edit"]')[0]!.trigger('click')
    await flushPromises()
    await buttonNamed(wrapper, 'Cancel').trigger('click')
    expect(wrapper.find('table').exists()).toBe(true)
  })

  it('keeps the form open when saving fails', async () => {
    backend.on('POST /api/groups', reply(400, { detail: 'Name taken' }))
    const wrapper = await render()
    await buttonNamed(wrapper, 'Add group').trigger('click')
    await wrapper.get('input:not([type])').setValue('Sales')
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(toastTexts()).toEqual(['Name taken'])
    expect(wrapper.find('h2').text()).toBe('Add group')
  })

  it('deletes a group once confirmed, and reports a failure', async () => {
    backend.on('DELETE /api/groups/*', undefined)
    const wrapper = await render()
    const remove = () => wrapper.findAll('button[aria-label="Delete"]')[1]!
    await remove().trigger('click')
    await answerConfirm(false)
    expect(backend.calls('DELETE /api/groups/*')).toHaveLength(0)
    await remove().trigger('click')
    await answerConfirm(true)
    expect(backend.calls('DELETE /api/groups/g2')).toHaveLength(1)

    backend.on('DELETE /api/groups/*', reply(500))
    await remove().trigger('click')
    await answerConfirm(true)
    expect(toastTexts()).toEqual(['Could not remove the item.'])
  })
})
