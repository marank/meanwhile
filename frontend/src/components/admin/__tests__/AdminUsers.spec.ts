import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type * as api from '@/api'
import { i18n } from '@/i18n'
import SearchableSelect from '@/components/SearchableSelect.vue'
import { dialog } from '@/services/dialog'
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
  has_password: true,
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

/** The dialog with a reset password is teleported to <body>. */
const dialogText = () => document.querySelector('[role="dialog"]')?.textContent ?? ''

/** Opens the "More actions" menu of the user in `row`; returns its entries. */
async function openMenu(wrapper: Wrapper, row: number) {
  await wrapper.findAll('tbody tr')[row]!.get('button[aria-label="More actions"]').trigger('click')
  return [...document.querySelectorAll<HTMLButtonElement>('[role="menuitem"]')]
}

async function chooseFromMenu(wrapper: Wrapper, row: number, label: string) {
  const entry = (await openMenu(wrapper, row)).find((item) => item.textContent.trim() === label)
  if (!entry) throw new Error(`No menu entry ${label}`)
  entry.click()
  await flushPromises()
}

const menuLabels = (items: HTMLElement[]) => items.map((item) => item.textContent.trim())

function closeDialog() {
  ;[...document.querySelectorAll<HTMLButtonElement>('[role="dialog"] button')]
    .find((b) => b.textContent.trim() === 'OK')!
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
        adminUser('ann', 'Ann', {
          is_admin: true,
          groups: [{ id: 'g1', name: 'Sales', description: '', member_count: 1 }],
        }),
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

    const more = rows[0]!.get('button[aria-label="More actions"]')
    expect(more.attributes('aria-expanded')).toBe('false')
    const own = await openMenu(wrapper, 0)
    expect(more.attributes('aria-expanded')).toBe('true')
    expect(menuLabels(own)).toEqual(['Send invitation', 'Reset password'])
    document.querySelector<HTMLElement>('[role="menu"]')!.parentElement!.click() // outside closes it
    await flushPromises()
    expect(more.attributes('aria-expanded')).toBe('false')

    const other = await openMenu(wrapper, 1)
    expect(menuLabels(other)).toEqual(['Send invitation', 'Reset password', 'Delete'])
    expect(other[2]!.dataset.tone).toBe('danger')
    wrapper.unmount()
  })

  it('sorts by name, then by the column whose header is clicked, and marks who has yet to accept', async () => {
    backend.on('GET /api/admin/users', [
      adminUser('zoe', 'Zoe', { email: 'a@example.test' }),
      adminUser('cy', 'Cy', { has_password: false }),
      adminUser('bob', 'Bob', { is_active: false }),
      adminUser('al', 'Al', { is_admin: true, email: 'z@example.test' }),
    ])
    const wrapper = await render()
    const names = () => wrapper.findAll('tbody tr td:first-child').map((td) => td.text())
    const header = (label: string) => wrapper.findAll('thead th').find((th) => th.text() === label)!
    const statuses = () => wrapper.findAll('[data-status]').map((s) => `${s.text()}:${s.attributes('data-status')}`)

    expect(names()).toEqual(['Al', 'Bob', 'Cy', 'Zoe'])
    expect(header('Name').attributes('aria-sort')).toBe('ascending')
    expect(header('Email').attributes('aria-sort')).toBe('none')
    // Without a password yet, an active user is still invited.
    expect(statuses()).toEqual(['Active:active', 'Inactive:inactive', 'Invited:invited', 'Active:active'])
    expect(wrapper.get('[data-status="invited"]').attributes('title')).toBe(
      "Hasn't chosen a password from the invitation yet",
    )

    await header('Name').get('button').trigger('click')
    expect(names()).toEqual(['Zoe', 'Cy', 'Bob', 'Al'])
    expect(header('Name').attributes('aria-sort')).toBe('descending')

    await header('Email').get('button').trigger('click')
    expect(names()).toEqual(['Zoe', 'Bob', 'Cy', 'Al'])
    await header('Status').get('button').trigger('click')
    expect(names()).toEqual(['Zoe', 'Al', 'Cy', 'Bob'])
    await header('Role').get('button').trigger('click')
    expect(names()[0]).toBe('Al')
    wrapper.unmount()
  })

  it('says so when there are none', async () => {
    backend.on('GET /api/admin/users', [])
    const wrapper = await render()
    expect(wrapper.text()).toContain('No users yet.')
    wrapper.unmount()
  })

  it('adds a user without a password and sends the invitation to choose one', async () => {
    backend.on('POST /api/admin/users', adminUser('cy', 'Cy', { email: 'cy@example.test', has_password: false }))
    backend.on('POST /api/admin/users/*/invite', { ok: true })
    const wrapper = await render()
    await buttonNamed(wrapper, 'Add user').trigger('click')
    expect(wrapper.find('h2').text()).toBe('Add user')
    expect(buttonNamed(wrapper, 'Save').attributes('disabled')).toBeDefined()
    const password = wrapper.get('input[placeholder="Leave empty to let the user choose one"]')
    expect(password.attributes('type')).toBe('password')
    await buttonNamed(wrapper, 'Show password').trigger('click')
    expect(password.attributes('type')).toBe('text')
    await buttonNamed(wrapper, 'Hide password').trigger('click')

    await wrapper.get('input:not([type])').setValue('Cy')
    await wrapper.get('input[type="email"]').setValue('cy@example.test')
    await wrapper.findAll('[role="switch"]')[0]!.trigger('click') // admin
    expect(wrapper.text()).toContain('No groups yet.')
    await pickGroup(wrapper, 'g1', 'Sales')
    await pickGroup(wrapper, 'g1', 'Sales')
    await pickGroup(wrapper, 'g2', 'Ops')
    expect(wrapper.findAll('li').map((li) => li.text())).toEqual(['Sales', 'Ops'])
    await wrapper.findAll('li button')[1]!.trigger('click')

    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(backend.calls('POST /api/admin/users')[0]!.body).toEqual({
      email: 'cy@example.test',
      display_name: 'Cy',
      is_admin: true,
      is_active: true,
      group_ids: ['g1'],
    })
    expect(wrapper.find('table').exists()).toBe(true)
    expect(dialog.title).toBe('Send invitation?')
    expect(dialog.message).toBe(
      "Cy gets an email at cy@example.test with a link to set a password. Until then, they can't sign in.",
    )
    await answerConfirm(true)
    expect(backend.calls('POST /api/admin/users/cy/invite')).toHaveLength(1)
    expect(toastTexts()).toEqual(['Invitation sent to cy@example.test.'])
    wrapper.unmount()
  })

  it('fills in a generated password to pass on, and sends no invitation unless wanted', async () => {
    backend.on('POST /api/admin/users', adminUser('cy', 'Cy', { email: 'cy@example.test' }))
    const wrapper = await render()
    await buttonNamed(wrapper, 'Add user').trigger('click')
    await wrapper.get('input:not([type])').setValue('Cy')
    await wrapper.get('input[type="email"]').setValue('cy@example.test')
    await buttonNamed(wrapper, 'Generate password').trigger('click')
    // Shown, so it can be passed on.
    const password = wrapper.get<HTMLInputElement>('input[type="text"]')
    expect(password.element.value).toMatch(/^[a-zA-Z0-9]{16}$/)
    await buttonNamed(wrapper, 'Generate password').trigger('click')
    const generated = password.element.value
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(backend.calls('POST /api/admin/users')[0]!.body).toMatchObject({ password: generated })
    expect(dialog.message).toContain("The password isn't in it")
    await answerConfirm(false)
    expect(backend.calls('POST /api/admin/users/*/invite')).toHaveLength(0)
    expect(document.querySelector('[role="dialog"]')).toBeNull()
    wrapper.unmount()
  })

  it('adds a user with a password of its own, and reports an invitation that failed', async () => {
    backend.on('POST /api/admin/users', adminUser('cy', 'Cy'))
    backend.on('POST /api/admin/users/*/invite', reply(500))
    const wrapper = await render()
    await buttonNamed(wrapper, 'Add user').trigger('click')
    await wrapper.get('input:not([type])').setValue('Cy')
    await wrapper.get('input[type="email"]').setValue('cy@example.test')
    await wrapper.get('input[type="password"]').setValue('chosen-secret')
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(backend.calls('POST /api/admin/users')[0]!.body).toMatchObject({ password: 'chosen-secret' })
    await answerConfirm(true)
    expect(toastTexts()).toEqual(['Could not send the invitation.'])
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
    await chooseFromMenu(wrapper, 1, 'Reset password')
    await answerConfirm(false)
    expect(backend.calls('POST /api/admin/users/*/reset-password')).toHaveLength(0)
    await chooseFromMenu(wrapper, 1, 'Reset password')
    await answerConfirm(true)
    expect(backend.calls('POST /api/admin/users/bob/reset-password')).toHaveLength(1)
    expect(dialogText()).toContain('fresh-pass')
    closeDialog()
    wrapper.unmount()
  })

  it('sends the invitation again once confirmed, worded by whether the user has a password', async () => {
    backend.on('GET /api/admin/users', [
      adminUser('ann', 'Ann'),
      adminUser('bob', 'Bob', { email: 'bob@example.test', has_password: false }),
    ])
    backend.on('POST /api/admin/users/*/invite', { ok: true })
    const wrapper = await render()
    const invite = (row: number) => chooseFromMenu(wrapper, row, 'Send invitation')

    await invite(1)
    expect(dialog.message).toContain('a link to set a password')
    await answerConfirm(false)
    expect(backend.calls('POST /api/admin/users/*/invite')).toHaveLength(0)
    await invite(1)
    await answerConfirm(true)
    expect(backend.calls('POST /api/admin/users/bob/invite')).toHaveLength(1)
    expect(toastTexts()).toEqual(['Invitation sent to bob@example.test.'])

    await invite(0)
    expect(dialog.message).toContain("The password isn't in it")
    await answerConfirm(true)
    expect(backend.calls('POST /api/admin/users/ann/invite')).toHaveLength(1)
    wrapper.unmount()
  })

  it('deletes a user once confirmed, and reports a failure', async () => {
    backend.on('DELETE /api/admin/users/*', undefined)
    const wrapper = await render()
    const remove = () => chooseFromMenu(wrapper, 1, 'Delete')
    await remove()
    await answerConfirm(false)
    expect(backend.calls('DELETE /api/admin/users/*')).toHaveLength(0)
    await remove()
    await answerConfirm(true)
    expect(backend.calls('DELETE /api/admin/users/bob')).toHaveLength(1)

    backend.on('DELETE /api/admin/users/*', reply(500))
    await remove()
    await answerConfirm(true)
    expect(toastTexts()).toEqual(['Could not remove the item.'])
    wrapper.unmount()
  })
})
