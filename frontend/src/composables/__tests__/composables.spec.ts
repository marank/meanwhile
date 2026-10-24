import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'
import { createMemoryHistory, createRouter, createWebHistory, type Router } from 'vue-router'
import { ApiError } from '@/api'
import { i18n } from '@/i18n'
import { toasts } from '@/services/toast'
import { useAction } from '../useAction'
import { useCalendarSettingsSync } from '../useCalendarSettingsSync'
import { useGoBack } from '../useGoBack'
import { useLoader } from '../useLoader'
import { useMediaQuery } from '../useMediaQuery'
import { useQueryTab } from '../useQueryTab'

/** Runs a composable inside a mounted component and hands back what it returned. */
function withSetup<T>(composable: () => T, plugins: unknown[] = []) {
  let result!: T
  const wrapper = mount(
    defineComponent({
      setup() {
        result = composable()
        return () => h('div')
      },
    }),
    { global: { plugins: [i18n, ...(plugins as never[])] } },
  )
  return { result, wrapper }
}

const shown = () => toasts.map((t) => `${t.tone}: ${t.message}`)

beforeEach(() => {
  i18n.global.locale.value = 'en'
  toasts.splice(0)
})

describe('useAction', () => {
  it('reports success, and runs one action at a time', async () => {
    const { busy, run } = useAction()
    let finish!: () => void
    const first = run(() => new Promise<void>((resolve) => (finish = resolve)), { success: () => 'Saved' })
    expect(busy.value).toBe(true)
    await expect(run(async () => {})).resolves.toBe(false)
    finish()
    await expect(first).resolves.toBe(true)
    expect(busy.value).toBe(false)
    expect(shown()).toEqual(['success: Saved'])
  })

  it('shows no toast for a quiet success', async () => {
    await expect(useAction().run(async () => {})).resolves.toBe(true)
    expect(toasts).toHaveLength(0)
  })

  it("explains a failure with the server's message, the given text, or a custom description", async () => {
    const { run } = useAction()
    await run(() => Promise.reject(new ApiError(400, { detail: 'Name taken' }, 'Bad Request')))
    await run(() => Promise.reject(new ApiError(500, null, 'Server Error')), { failure: 'Could not save' })
    await run(() => Promise.reject(new Error('conflict')), { describeError: () => 'Room is booked' })
    expect(shown()).toEqual(['error: Name taken', 'error: Could not save', 'error: Room is booked'])
  })
})

describe('useLoader', () => {
  it('loads on mount and reports when loading fails', async () => {
    const loader = vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValue(undefined)
    const { result } = withSetup(() => useLoader(loader))
    expect(result.loading.value).toBe(true)
    await flushPromises()
    expect(result.loading.value).toBe(false)
    expect(toasts.map((t) => t.tone)).toEqual(['error'])
    await expect(result.reload()).resolves.toBe(true)
  })

  it('waits to be asked when not immediate', async () => {
    const loader = vi.fn().mockResolvedValue(undefined)
    const { result } = withSetup(() => useLoader(loader, { immediate: false }))
    await flushPromises()
    expect(result.loading.value).toBe(false)
    expect(loader).not.toHaveBeenCalled()
  })
})

describe('useMediaQuery', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('follows the media query until unmounted', async () => {
    const listeners = new Set<(event: { matches: boolean }) => void>()
    vi.stubGlobal('matchMedia', () => ({
      matches: false,
      addEventListener: (_: string, l: (event: { matches: boolean }) => void) => listeners.add(l),
      removeEventListener: (_: string, l: (event: { matches: boolean }) => void) => listeners.delete(l),
    }))
    const { result, wrapper } = withSetup(() => useMediaQuery('(max-width: 600px)'))
    expect(result.value).toBe(false)
    listeners.forEach((l) => l({ matches: true }))
    expect(result.value).toBe(true)
    wrapper.unmount()
    expect(listeners.size).toBe(0)
  })

  it('never matches where the browser has no media queries', () => {
    vi.stubGlobal('matchMedia', undefined)
    expect(withSetup(() => useMediaQuery('(min-width: 1px)')).result.value).toBe(false)
  })
})

describe('useCalendarSettingsSync', () => {
  it('shares nothing outside the settings page', () => {
    const { result } = withSetup(() => useCalendarSettingsSync())
    result.membersChanged()
    expect(result.membersVersion.value).toBe(0)
  })
})

describe('router composables', () => {
  let router: Router

  beforeEach(async () => {
    const Page = { render: () => h('p') }
    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/calendar', component: Page },
        { path: '/settings', component: Page },
        { path: '/home', component: Page },
      ],
    })
    await router.push('/settings')
  })

  it('goes back to the fallback when the page was opened directly', async () => {
    const { result } = withSetup(() => useGoBack(), [router])
    result()
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/calendar')
  })

  it('goes back within the app when there is a previous page', async () => {
    // Only the browser history records where one came from.
    const web = createRouter({ history: createWebHistory(), routes: router.options.routes })
    await web.push('/home')
    await web.push('/settings')
    const back = vi.spyOn(web, 'back').mockImplementation(() => {})
    withSetup(() => useGoBack(), [web]).result()
    expect(back).toHaveBeenCalled()
  })

  it('keeps the tab in the query and corrects unknown tabs', async () => {
    const { result } = withSetup(() => useQueryTab(['general', 'access'] as const), [router])
    expect(result.tab.value).toBe('general')
    result.selectTab('access')
    await flushPromises()
    expect(router.currentRoute.value.query.tab).toBe('access')
    expect(result.tab.value).toBe('access')

    await router.replace({ query: { tab: 'nonsense' } })
    await nextTick()
    await flushPromises()
    expect(router.currentRoute.value.query.tab).toBe('general')
  })
})
