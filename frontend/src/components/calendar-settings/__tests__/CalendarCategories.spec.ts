import { beforeEach, describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import type * as api from '@/api'
import { i18n } from '@/i18n'
import { fakeBackend, reply, type FakeBackend } from '@/__tests__/fakeBackend'
import { answerConfirm, buttonNamed, clearToasts, toastTexts } from '@/components/__tests__/settingsFixtures'
import CalendarCategories from '../CalendarCategories.vue'

const category = (id: string, name: string, description = ''): api.Category => ({
  id,
  calendar_id: 'cal',
  name,
  description,
  color: '#22c55e',
  created_at: '',
  updated_at: '',
})

let backend: FakeBackend

async function render(canManage = true) {
  const wrapper = mount(CalendarCategories, { props: { calendarId: 'cal', canManage }, global: { plugins: [i18n] } })
  await flushPromises()
  return wrapper
}

describe('calendar categories', () => {
  beforeEach(() => {
    i18n.global.locale.value = 'en'
    clearToasts()
    backend = fakeBackend({
      'GET /api/calendars/cal/categories': [category('c1', 'Holiday', 'Days off'), category('c2', 'Meeting')],
    })
  })

  it('lists the categories', async () => {
    const wrapper = await render()
    const rows = wrapper.findAll('tbody tr')
    expect(rows.map((r) => r.text())).toEqual(['HolidayDays off', 'Meeting—'])
  })

  it('offers no changes to those who cannot manage the calendar', async () => {
    const wrapper = await render(false)
    expect(wrapper.findAll('button')).toHaveLength(0)
  })

  it('says so when there are none', async () => {
    backend.on('GET /api/calendars/cal/categories', [])
    const wrapper = await render()
    expect(wrapper.text()).toContain('No categories yet.')
  })

  it('adds a category', async () => {
    backend.on('POST /api/calendars/cal/categories', (req) => category('c3', (req.body as api.CategoryInput).name))
    const wrapper = await render()
    await buttonNamed(wrapper, 'Add').trigger('click')
    expect(wrapper.text()).toContain('Add category')
    expect(buttonNamed(wrapper, 'Save').attributes('disabled')).toBeDefined()

    await wrapper.get('input:not([type])').setValue('Travel')
    await wrapper.get('textarea').setValue('On the road')
    await wrapper.get('input[type="color"]').setValue('#ff0000')
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(backend.calls('POST /api/calendars/cal/categories')[0]!.body).toEqual({
      name: 'Travel',
      description: 'On the road',
      color: '#ff0000',
    })
    // Back to the list, loaded afresh.
    expect(wrapper.find('table').exists()).toBe(true)
    expect(backend.calls('GET /api/calendars/cal/categories')).toHaveLength(2)
  })

  it('edits a category, and cancels without saving', async () => {
    backend.on('PATCH /api/calendars/cal/categories/*', {})
    const wrapper = await render()
    await wrapper.findAll('button[aria-label="Edit"]')[1]!.trigger('click')
    expect(wrapper.text()).toContain('Edit category')
    expect((wrapper.get('input:not([type])').element as HTMLInputElement).value).toBe('Meeting')
    await buttonNamed(wrapper, 'Cancel').trigger('click')
    expect(wrapper.find('table').exists()).toBe(true)

    await wrapper.findAll('button[aria-label="Edit"]')[0]!.trigger('click')
    await wrapper.get('textarea').setValue('')
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(backend.calls('PATCH /api/calendars/cal/categories/c1')[0]!.body).toEqual({
      name: 'Holiday',
      description: '',
      color: '#22c55e',
    })
  })

  it('keeps the form open when saving fails', async () => {
    backend.on('POST /api/calendars/cal/categories', reply(400, { detail: 'Name taken' }))
    const wrapper = await render()
    await buttonNamed(wrapper, 'Add').trigger('click')
    await wrapper.get('input:not([type])').setValue('Holiday')
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(toastTexts()).toEqual(['Name taken'])
    expect(wrapper.text()).toContain('Add category')
  })

  it('deletes a category once confirmed', async () => {
    backend.on('DELETE /api/calendars/cal/categories/*', undefined)
    const wrapper = await render()
    await wrapper.findAll('button[aria-label="Delete"]')[0]!.trigger('click')
    await answerConfirm(false)
    expect(backend.calls('DELETE /api/calendars/cal/categories/*')).toHaveLength(0)

    await wrapper.findAll('button[aria-label="Delete"]')[0]!.trigger('click')
    await answerConfirm(true)
    expect(backend.calls('DELETE /api/calendars/cal/categories/c1')).toHaveLength(1)
    expect(backend.calls('GET /api/calendars/cal/categories')).toHaveLength(2)
  })

  it('reports a failed delete', async () => {
    backend.on('DELETE /api/calendars/cal/categories/*', reply(500))
    const wrapper = await render()
    await wrapper.findAll('button[aria-label="Delete"]')[0]!.trigger('click')
    await answerConfirm(true)
    expect(toastTexts()).toEqual(['Could not remove the item.'])
  })
})
