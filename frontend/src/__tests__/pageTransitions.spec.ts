import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, h, nextTick, ref } from 'vue'
import { createRouter, createWebHistory, type Router } from 'vue-router'
import { fakeBackend } from '@/__tests__/fakeBackend'
import App from '@/App.vue'
import { stubMatchMedia } from '@/components/calendar/__tests__/calendarFixtures'
import { i18n } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { makeUser, sessionRoutes, stubBrowser } from '@/views/__tests__/session'

const PHONE = '(width < 40rem)'
const REDUCED_MOTION = '(prefers-reduced-motion: reduce)'
const HOME_SCREEN_APP = '(display-mode: standalone)'
const WIDTH = 375

let wrapper: VueWrapper
let router: Router

// A page that counts what was typed into it, to tell whether it is still the same one.
const typed = ref(0)
const page = (name: string) =>
  defineComponent({
    name,
    __name: name,
    setup: () => () => h('section', { 'data-page': name }, [h('input', { onInput: () => typed.value++ })]),
  })

async function render(path = '/calendar') {
  fakeBackend({
    ...sessionRoutes(makeUser()),
    'GET /api/settings': { app_name: 'Meanwhile', logo_url: '', favicon_url: '' },
    'GET /api/notifications/counts': { unread: 0, approvals: 0, invitations: 0 },
  })
  await useAuthStore().init()
  router = createRouter({
    // The browser's history: it knows whether there is a page to go back to.
    history: createWebHistory(),
    routes: [
      { path: '/calendar', component: page('Calendar'), meta: { layer: 0 } },
      { path: '/account', component: page('Account'), meta: { layer: 1 } },
      { path: '/admin', component: page('Admin'), meta: { layer: 1 } },
      { path: '/login', component: page('Login') },
    ],
  })
  await router.push(path)
  wrapper = mount(App, {
    global: {
      plugins: [i18n, router],
      // The transitions themselves are what is tested here.
      stubs: { CalendarSidebar: defineComponent(() => () => h('aside')), transition: false },
    },
    attachTo: document.body,
  })
  await flushPromises()
}

const pages = () => wrapper.findAll('main > [data-page]')
const main = () => wrapper.get('main').element

/** Resolves when the router has gone to another page (going back in the browser's history takes a while). */
function navigated() {
  return new Promise<void>((resolve) => {
    const stop = router.afterEach(() => {
      stop()
      resolve()
    })
  })
}

/** Waits for the frames a transition takes, which jsdom, without styles, ends right away. */
async function settled() {
  for (let i = 0; i < 4; i++) await new Promise((resolve) => requestAnimationFrame(resolve))
  await flushPromises()
}

/** Goes to `path` and tells the transition each page got, while both are shown. */
async function go(path: string, how: 'push' | 'back' = 'push') {
  const done = navigated()
  if (how === 'push') void router.push(path)
  else router.back()
  await done
  await nextTick()
  return pages().map((el) => `${el.attributes('data-page')}: ${el.classes().find((c) => c.endsWith('-active')) ?? '-'}`)
}

/** A touch at (x, y), `time` ms into the swipe: how fast the finger moves decides too. */
function touch(type: string, x: number, y = 300, time = 0) {
  const event = new PointerEvent(type, { bubbles: true, pointerId: 1, pointerType: 'touch', clientX: x, clientY: y })
  Object.defineProperty(event, 'timeStamp', { value: time })
  return event
}

/** Puts a finger down at x and moves it, slowly, right to each of `to`, on the current page. */
function swipe(x: number, to: number[]) {
  const target = wrapper.get('main [data-page]').element
  target.dispatchEvent(touch('pointerdown', x))
  to.forEach((point, i) => main().dispatchEvent(touch('pointermove', point, 300, (i + 1) * 200)))
  return { release: () => main().dispatchEvent(touch('pointerup', to.at(-1)!, 300, (to.length + 1) * 200)) }
}

const cover = () => document.querySelector('[data-back-swipe-cover]')

/** Waits until a released swipe has settled (it takes 250ms). */
const letGo = () => new Promise((resolve) => setTimeout(resolve, 300))

describe('page transitions', () => {
  let media: ReturnType<typeof stubMatchMedia>

  beforeEach(() => {
    i18n.global.locale.value = 'en'
    setActivePinia(createPinia())
    stubBrowser()
    media = stubMatchMedia([PHONE])
    typed.value = 0
  })

  afterEach(() => {
    wrapper.unmount()
    vi.restoreAllMocks()
  })

  it('slides a deeper page in over the one below on phones, and out again going back', async () => {
    await render()
    expect(await go('/account')).toEqual(['Calendar: page-push-leave-active', 'Account: page-push-enter-active'])
    await settled()
    expect(await go('/calendar', 'back')).toEqual(['Account: page-pop-leave-active', 'Calendar: page-pop-enter-active'])
  })

  it('cross-fades pages on the same layer', async () => {
    await render('/account')
    expect(await go('/admin')).toEqual(['Account: page-fade-leave-active', 'Admin: page-fade-enter-active'])
  })

  it('lets pages rise in on larger screens', async () => {
    media.set(PHONE, false)
    await render()
    expect(await go('/account')).toEqual(['Calendar: page-rise-leave-active', 'Account: page-rise-enter-active'])
  })

  it('changes pages at once with reduced motion, and to pages without a layer', async () => {
    media.set(REDUCED_MOTION, true)
    await render()
    expect(await go('/account')).toEqual(['Account: -'])
    media.set(REDUCED_MOTION, false)
    await settled()
    expect(await go('/login')).toEqual(['Login: -'])
  })

  it('keeps the page leaving where it was on the screen, and starts the new one at the top', async () => {
    await render()
    await router.push('/account')
    await settled()
    const leaving = wrapper.get('[data-page="Account"]').element as HTMLElement
    vi.spyOn(leaving, 'offsetTop', 'get').mockReturnValue(4)
    main().scrollTop = 300
    await go('/calendar', 'back')
    expect(leaving.style.position).toBe('absolute')
    expect(leaving.style.top).toBe('-296px')
    expect(main().scrollTop).toBe(0)
  })

  describe('swiping back from the left edge', () => {
    beforeEach(() => {
      media.set(HOME_SCREEN_APP, true)
      vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
        top: 0,
        left: 0,
        width: WIDTH,
        height: 700,
      } as DOMRect)
    })

    async function onAccount() {
      await render()
      await router.push('/account')
      await settled()
    }

    it('uncovers the page below while the finger moves, and goes back when let go far enough', async () => {
      await onAccount()
      const back = navigated()
      const finger = swipe(10, [30, 200])
      await back
      // The page below is already there; a copy of the one going away follows the finger.
      expect(router.currentRoute.value.path).toBe('/calendar')
      expect(cover()?.querySelector('[data-page="Account"]')).not.toBeNull()
      expect(parseFloat((cover() as HTMLElement).style.translate)).toBeCloseTo(190)

      finger.release()
      await letGo()
      await settled()
      expect(cover()).toBeNull()
      expect(router.currentRoute.value.path).toBe('/calendar')
      expect(pages().map((el) => el.attributes('data-page'))).toEqual(['Calendar'])
    })

    it('returns to the very same page when the swipe is taken back', async () => {
      await onAccount()
      await wrapper.get('input').trigger('input')
      const back = navigated()
      const finger = swipe(10, [30, 60])
      await back
      const forward = navigated()
      finger.release()
      await letGo()
      await forward
      await flushPromises()
      await settled()

      expect(router.currentRoute.value.path).toBe('/account')
      expect(cover()).toBeNull()
      expect(pages().map((el) => el.attributes('data-page'))).toEqual(['Account'])
      // Not a new page: what happened on it is still there.
      await wrapper.get('input').trigger('input')
      expect(typed.value).toBe(2)
      expect(main().style.translate).toBe('')
    })

    it('needs the swipe to start at the edge', async () => {
      await onAccount()
      swipe(80, [100, 300]).release()
      await flushPromises()
      expect(router.currentRoute.value.path).toBe('/account')
      expect(cover()).toBeNull()
    })

    it('leaves swipes up and down alone', async () => {
      await onAccount()
      const target = wrapper.get('main [data-page]').element
      target.dispatchEvent(touch('pointerdown', 10, 300))
      main().dispatchEvent(touch('pointermove', 12, 200))
      main().dispatchEvent(touch('pointerup', 12, 200))
      await flushPromises()
      expect(router.currentRoute.value.path).toBe('/account')
    })

    it('does nothing on the bottom layer or in the browser, which has its own', async () => {
      await render()
      swipe(10, [30, 300]).release()
      await flushPromises()
      expect(cover()).toBeNull()

      media.set(HOME_SCREEN_APP, false)
      await router.push('/account')
      await settled()
      swipe(10, [30, 300]).release()
      await flushPromises()
      expect(router.currentRoute.value.path).toBe('/account')
    })
  })
})
