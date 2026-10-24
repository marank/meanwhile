import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { fakeBackend, reply, type FakeBackend } from '@/__tests__/fakeBackend'
import { i18n } from '@/i18n'
import ResetPasswordView from '../ResetPasswordView.vue'

let wrapper: VueWrapper
let backend: FakeBackend

async function render(resetKey?: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:any(.*)', component: { template: '<div />' } }],
  })
  await router.push('/forgot-password')
  wrapper = mount(ResetPasswordView, { props: { resetKey }, global: { plugins: [i18n, router] } })
}

async function submit() {
  await wrapper.get('form').trigger('submit')
  await flushPromises()
}

beforeEach(() => {
  i18n.global.locale.value = 'en'
  setActivePinia(createPinia())
  backend = fakeBackend()
})

afterEach(() => wrapper?.unmount())

describe('ResetPasswordView', () => {
  describe('without a key', () => {
    it('asks for the link to be mailed to the address entered', async () => {
      backend.on('POST /api/auth/v1/auth/password/request', { status: 200 })
      await render()
      expect(wrapper.text()).toContain('Enter your email address.')
      expect(wrapper.get('button[type="submit"]').text()).toBe('Send link')
      await wrapper.get('#reset-email').setValue('alice@example.com')
      await submit()
      expect(backend.calls('POST /api/auth/v1/auth/password/request')[0]!.body).toEqual({
        email: 'alice@example.com',
      })
      expect(wrapper.get('[role="status"]').text()).toContain('a link to set a new password is on its way')
      expect(wrapper.find('form').exists()).toBe(false)
    })

    it('shows why the request failed', async () => {
      backend.on(
        'POST /api/auth/v1/auth/password/request',
        reply(400, { errors: [{ message: 'Enter a valid email.' }] }),
      )
      await render()
      await submit()
      expect(wrapper.text()).toContain('Enter a valid email.')
      expect(wrapper.find('form').exists()).toBe(true)
    })

    it('links back to the login', async () => {
      await render()
      expect(wrapper.get('a').attributes('href')).toBe('/login')
    })
  })

  describe('with the key from the link', () => {
    it('sets the new password, taking the answer "now sign in" as success', async () => {
      backend.on('POST /api/auth/v1/auth/password/reset', reply(401, { status: 401, flows: [] }))
      await render('abc-123')
      expect(wrapper.find('#reset-email').exists()).toBe(false)
      expect(wrapper.get('button[type="submit"]').text()).toBe('Set password')
      await wrapper.get('#new-password').setValue('a new secret')
      await submit()
      expect(backend.calls('POST /api/auth/v1/auth/password/reset')[0]!.body).toEqual({
        key: 'abc-123',
        password: 'a new secret',
      })
      expect(wrapper.get('[role="status"]').text()).toBe('Your password has been changed. You can sign in with it now.')
    })

    it('says so when the key is unknown, used or expired', async () => {
      backend.on(
        'POST /api/auth/v1/auth/password/reset',
        reply(400, { status: 400, errors: [{ message: 'Invalid key', code: 'invalid', param: 'key' }] }),
      )
      await render('stale')
      await submit()
      expect(wrapper.text()).toContain('This link is invalid, has been used or has expired. Request a new one.')
    })

    it('shows other problems as the server words them', async () => {
      backend.on(
        'POST /api/auth/v1/auth/password/reset',
        reply(400, { status: 400, errors: [{ message: 'This password is too common.', param: 'password' }] }),
      )
      await render('abc-123')
      await submit()
      expect(wrapper.text()).toContain('This password is too common.')
    })
  })
})
