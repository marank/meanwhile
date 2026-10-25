import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { fakeBackend, reply, type FakeBackend } from '@/__tests__/fakeBackend'
import type { PublicSettings } from '@/api'
import { i18n } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { useSettingsStore } from '@/stores/settings'
import LoginView from '../LoginView.vue'
import { makeUser, stubBrowser } from './session'

let wrapper: VueWrapper
let router: Router
let backend: FakeBackend

const publicSettings = (allowRegistration = true): PublicSettings => ({
  app_name: 'Team Calendar',
  logo_url: '',
  favicon_url: '',
  default_first_weekday: 1,
  default_show_weekends: true,
  default_weekend_days: [0, 6],
  default_show_week_numbers: false,
  allow_registration: allowRegistration,
})

async function render(mode?: 'login' | 'register') {
  const page = { template: '<div />' }
  router = createRouter({
    history: createMemoryHistory(),
    routes: ['/login', '/register', '/forgot-password', '/calendar'].map((path) => ({ path, component: page })),
  })
  await router.push(mode === 'register' ? '/register' : '/login')
  // As App does on start.
  await useSettingsStore().load()
  wrapper = mount(LoginView, { props: { mode }, global: { plugins: [i18n, router] } })
}

async function fill(selector: string, value: string) {
  await wrapper.get(selector).setValue(value)
}

beforeEach(() => {
  i18n.global.locale.value = 'en'
  setActivePinia(createPinia())
  stubBrowser()
  backend = fakeBackend({ 'GET /api/settings': publicSettings() })
})

afterEach(() => {
  wrapper?.unmount()
  vi.restoreAllMocks()
})

describe('LoginView', () => {
  it('signs in with the address and password entered and shows the calendar', async () => {
    backend.on('POST /api/auth/v1/auth/login', { status: 200, data: { user: makeUser() } })
    await render()
    expect(wrapper.get('h2').text()).toBe('Login')
    expect(wrapper.findAll('input')).toHaveLength(2)
    await fill('input[type="email"]', 'alice@example.com')
    await fill('input[type="password"]', 'correct horse')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(backend.calls('POST /api/auth/v1/auth/login')[0]!.body).toEqual({
      email: 'alice@example.com',
      password: 'correct horse',
    })
    expect(useAuthStore().user?.email).toBe('alice@example.com')
    expect(router.currentRoute.value.path).toBe('/calendar')
  })

  it("shows the server's explanation when signing in fails", async () => {
    backend.on(
      'POST /api/auth/v1/auth/login',
      reply(400, {
        status: 400,
        errors: [{ message: 'The email address and/or password you specified are not correct.' }],
      }),
    )
    await render()
    await fill('input[type="email"]', 'alice@example.com')
    await fill('input[type="password"]', 'wrong pass')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('The email address and/or password you specified are not correct.')
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeUndefined()
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('falls back to a general message when the server gives none', async () => {
    backend.on('POST /api/auth/v1/auth/login', reply(500, null))
    await render()
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('The action could not be completed.')
  })

  it('links to registering and to resetting the password', async () => {
    await render()
    const links = wrapper.findAll('a').map((a) => [a.text(), a.attributes('href')])
    expect(links).toEqual([
      ['Forgot your password?', '/forgot-password'],
      ["Don't have an account? Register", '/register'],
    ])
  })

  it('registers with a display name and shows the calendar', async () => {
    backend.on('POST /api/auth/v1/auth/signup', { status: 200, data: { user: makeUser() } })
    await render('register')
    expect(wrapper.get('h2').text()).toBe('Register')
    await fill('input[type="email"]', 'alice@example.com')
    await fill('input[type="text"]', 'Alice Smith')
    await fill('input[type="password"]', 'correct horse')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(backend.calls('POST /api/auth/v1/auth/signup')[0]!.body).toEqual({
      email: 'alice@example.com',
      display_name: 'Alice Smith',
      password: 'correct horse',
    })
    expect(router.currentRoute.value.path).toBe('/calendar')
  })

  it('offers no registering where nobody may sign up', async () => {
    backend.on('GET /api/settings', publicSettings(false))
    await render()
    expect(wrapper.findAll('a').map((a) => a.attributes('href'))).toEqual(['/forgot-password'])
    await render('register')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('links back to signing in when registering', async () => {
    await render('register')
    expect(wrapper.findAll('a').map((a) => [a.text(), a.attributes('href')])).toEqual([
      ['Already have an account? Login', '/login'],
    ])
  })
})
