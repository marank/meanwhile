import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type * as api from '@/api'
import { i18n } from '@/i18n'
import SearchableSelect from '@/components/SearchableSelect.vue'
import { realtime } from '@/services/realtime'
import { useAuthStore } from '@/stores/auth'
import { fakeBackend, reply, type FakeBackend } from '@/__tests__/fakeBackend'
import {
  answerConfirm,
  buttonNamed,
  clearToasts,
  searchResult,
  toastTexts,
  user,
} from '@/components/__tests__/settingsFixtures'
import AdminUsers from '../AdminUsers.vue'

const adminUser = (id: string, name: string, overrides: Partial<api.AdminUser> = {}): api.AdminUser => ({
  id,
  email: `${id}@example.test`,
  display_name: name,
  is_admin: false,
  is_active: true,
  groups: [],
  created_at: '',
  updated_at: '',
  ...overrides,
})

let backend: FakeBackend

async function render() {
  const wrapper = mount(AdminUsers, { global: { plugins: [i18n] }, attachTo: document.body })
  await flushPromises()
  return wrapper
}

type Wrapper = Awaited<ReturnType<typeof render>>

async function pickGroup(wrapper: Wrapper, id: string, name: string) {
  const select = wrapper.findComponent(SearchableSelect)
  select.vm.$emit('update:modelValue', id)
  select.vm.$emit('select', id, searchResult(id, name))
  await flushPromises()
}

/** The dialog with a new password is teleported to <body>. */
const dialogText = () => document.querySelector('[role="dialog"]')?.textContent ?? ''

function closeDialog() {
  ;[...document.querySelectorAll<HTMLButtonElement>('[role="dialog"] button')]
    .find((b) => b.textContent!.trim() === 'OK')!
    .click()
}

describe('admin users', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    i18n.global.locale.value = 'en'
    clearToasts()
    vi.spyOn(realtime, 'start').mockImplementation(() => {})
    vi.spyOn(realtime, 'stop').mockImplementation(() => {})
    useAuthStore().user = user({ id: 'ann' })
    backend = fakeBackend({
      'GET /api/admin/users': [
        adminUser('ann', 'Ann', { is_admin: true, groups: [{ id: 'g1', name: 'Sales', description: null }] }),
        adminUser('bob', 'Bob', { is_active: false }),
      ],
      'GET /api/search': [],
    })
  })

  afterEach(() => vi.restoreAllMocks())

  it('lists the users with role and status, and lets nobody delete themselves', async () => {
    const wrapper = await render()
    const rows = wrapper.findAll('tbody tr')
    expect(rows[0]!.text()).toContain('Admin')
    expect(rows[0]!.text()).toContain('Active')
    expect(rows[1]!.text()).toContain('—')
    expect(rows[1]!.text()).toContain('Inactive')
    expect(rows[0]!.find('button[aria-label="Delete"]').exists()).toBe(false)
    expect(rows[1]!.find('button[aria-label="Delete"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('says so when there are none', async () => {
    backend.on('GET /api/admin/users', [])
    const wrapper = await render()
    expect(wrapper.text()).toContain('No users yet.')
    wrapper.unmount()
  })

  it('adds a user with a generated password and shows it once', async () => {
    backend.on('POST /api/admin/users', {})
    const wrapper = await render()
    await buttonNamed(wrapper, 'Add user').trigger('click')
    expect(wrapper.find('h2').text()).toBe('Add user')
    expect(buttonNamed(wrapper, 'Save').attributes('disabled')).toBeDefined()
    const password = wrapper.get('input[placeholder="Leave empty to generate a password"]')
    expect(password.attributes('type')).toBe('password')
    await buttonNamed(wrapper, 'Show password').trigger('click')
    expect(password.attributes('type')).toBe('text')
    await buttonNamed(wrapper, 'Hide password').trigger('click')

    await wrapper.get('input:not([type])').setValue('Cy')
    await wrapper.get('input[type="email"]').setValue('cy@example.test')
    await wrapper.findAll('[role="switch"]')[0]!.trigger('click') // admin
    expect(wrapper.text()).toContain('No groups yet.')
    await pickGroup(wrapper, 'g1', 'Sales')
    await buttonNamed(wrapper, 'Add group').trigger('click')
    await pickGroup(wrapper, 'g1', 'Sales')
    await buttonNamed(wrapper, 'Add group').trigger('click')
    await pickGroup(wrapper, 'g2', 'Ops')
    await buttonNamed(wrapper, 'Add group').trigger('click')
    expect(wrapper.findAll('li').map((li) => li.text())).toEqual(['Sales', 'Ops'])
    await wrapper.findAll('li button')[1]!.trigger('click')

    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    const body = backend.calls('POST /api/admin/users')[0]!.body as api.AdminUserCreate
    expect(body).toMatchObject({
      email: 'cy@example.test',
      display_name: 'Cy',
      is_admin: true,
      is_active: true,
      group_ids: ['g1'],
    })
    expect(body.password).toMatch(/^[a-zA-Z0-9]{16}$/)
    expect(dialogText()).toContain(body.password)
    closeDialog()
    await flushPromises()
    expect(document.querySelector('[role="dialog"]')).toBeNull()
    expect(wrapper.find('table').exists()).toBe(true)
    wrapper.unmount()
  })

  it('adds a user with a password of its own, without showing it', async () => {
    backend.on('POST /api/admin/users', {})
    const wrapper = await render()
    await buttonNamed(wrapper, 'Add user').trigger('click')
    await wrapper.get('input:not([type])').setValue('Cy')
    await wrapper.get('input[type="email"]').setValue('cy@example.test')
    await wrapper.get('input[type="password"]').setValue('chosen-secret')
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(backend.calls('POST /api/admin/users')[0]!.body).toMatchObject({ password: 'chosen-secret' })
    expect(document.querySelector('[role="dialog"]')).toBeNull()
    wrapper.unmount()
  })

  it('edits a user, sending a password only when one was typed', async () => {
    backend.on('PATCH /api/admin/users/*', {})
    const wrapper = await render()
    await wrapper.findAll('button[aria-label="Edit"]')[0]!.trigger('click')
    expect(wrapper.find('h2').text()).toBe('Edit user')
    expect(wrapper.text()).toContain('Sales')
    await wrapper.findAll('[role="switch"]')[1]!.trigger('click') // inactive
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(backend.calls('PATCH /api/admin/users/ann')[0]!.body).toEqual({
      email: 'ann@example.test',
      display_name: 'Ann',
      is_admin: true,
      is_active: false,
      group_ids: ['g1'],
    })

    await wrapper.findAll('button[aria-label="Edit"]')[1]!.trigger('click')
    await wrapper.get('input[type="password"]').setValue('new-secret')
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(backend.calls('PATCH /api/admin/users/bob')[0]!.body).toMatchObject({ password: 'new-secret' })
    wrapper.unmount()
  })

  it('cancels editing, and keeps the form open when saving fails', async () => {
    backend.on('PATCH /api/admin/users/*', reply(400, { detail: 'Email taken' }))
    const wrapper = await render()
    await wrapper.findAll('button[aria-label="Edit"]')[1]!.trigger('click')
    await buttonNamed(wrapper, 'Cancel').trigger('click')
    expect(wrapper.find('table').exists()).toBe(true)

    await wrapper.findAll('button[aria-label="Edit"]')[1]!.trigger('click')
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(toastTexts()).toEqual(['Email taken'])
    expect(wrapper.find('h2').text()).toBe('Edit user')
    wrapper.unmount()
  })

  it('resets a password once confirmed and shows the new one', async () => {
    backend.on('POST /api/admin/users/*/reset-password', { password: 'fresh-pass' })
    const wrapper = await render()
    const reset = () => wrapper.findAll('button[aria-label="Reset password"]')[1]!
    await reset().trigger('click')
    await answerConfirm(false)
    expect(backend.calls('POST /api/admin/users/*/reset-password')).toHaveLength(0)
    await reset().trigger('click')
    await answerConfirm(true)
    expect(backend.calls('POST /api/admin/users/bob/reset-password')).toHaveLength(1)
    expect(dialogText()).toContain('fresh-pass')
    closeDialog()
    wrapper.unmount()
  })

  it('deletes a user once confirmed, and reports a failure', async () => {
    backend.on('DELETE /api/admin/users/*', undefined)
    const wrapper = await render()
    const remove = () => wrapper.get('button[aria-label="Delete"]')
    await remove().trigger('click')
    await answerConfirm(false)
    expect(backend.calls('DELETE /api/admin/users/*')).toHaveLength(0)
    await remove().trigger('click')
    await answerConfirm(true)
    expect(backend.calls('DELETE /api/admin/users/bob')).toHaveLength(1)

    backend.on('DELETE /api/admin/users/*', reply(500))
    await remove().trigger('click')
    await answerConfirm(true)
    expect(toastTexts()).toEqual(['Could not remove the item.'])
    wrapper.unmount()
  })
})
