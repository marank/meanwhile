import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { i18n } from '@/i18n'
import { toast, toasts } from '@/services/toast'
import ToastHost from '../ToastHost.vue'

const render = () => mount(ToastHost, { global: { plugins: [i18n] } })

beforeEach(() => {
  i18n.global.locale.value = 'en'
  vi.useFakeTimers()
  toasts.splice(0)
})

afterEach(() => {
  vi.useRealTimers()
})

describe('ToastHost', () => {
  it('shows each message with an icon for its tone', async () => {
    const wrapper = render()
    toast.success('Saved')
    toast.error('Failed')
    toast.info('Starts soon')
    await wrapper.vm.$nextTick()
    const items = wrapper.findAll('[role="status"]')
    expect(items.map((item) => item.text())).toEqual(['Saved', 'Failed', 'Starts soon'])
    expect(items[0]!.classes()).toContain('text-green-800')
    expect(items[0]!.find('svg').classes().join(' ')).toContain('circle-check')
    expect(items[1]!.classes()).toContain('text-red-800')
    expect(items[1]!.find('svg').classes().join(' ')).toContain('circle-x')
    expect(items[2]!.classes()).toContain('text-blue-800')
    expect(items[2]!.find('svg').classes().join(' ')).toContain('bell')
  })

  it('removes a message when its close button is clicked', async () => {
    const wrapper = render()
    toast.success('Saved')
    toast.success('Also saved')
    await wrapper.vm.$nextTick()
    await wrapper.get('button[aria-label="Close"]').trigger('click')
    expect(toasts.map((t) => t.message)).toEqual(['Also saved'])
  })
})
