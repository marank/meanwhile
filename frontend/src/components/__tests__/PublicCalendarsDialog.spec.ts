import { beforeEach, describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type { PublicCalendar } from '@/api'
import { i18n } from '@/i18n'
import { toasts } from '@/services/toast'
import { useCalendarStore } from '@/stores/calendars'
import { fakeBackend, reply } from '@/__tests__/fakeBackend'
import PublicCalendarsDialog from '../PublicCalendarsDialog.vue'
import { calendarItem } from '../calendar/__tests__/calendarFixtures'

function publicCalendar(id: string, overrides: Partial<PublicCalendar> = {}): PublicCalendar {
  return { id, name: `Public ${id}`, description: '', owner_name: 'Alice', added: false, ...overrides }
}

async function render() {
  const wrapper = mount(PublicCalendarsDialog, { global: { plugins: [i18n], stubs: { teleport: true } } })
  await flushPromises()
  return wrapper
}

const rows = (wrapper: Awaited<ReturnType<typeof render>>) => wrapper.findAll('li')

describe('PublicCalendarsDialog', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    i18n.global.locale.value = 'en'
    toasts.splice(0)
  })

  it('lists the public calendars with their owners and descriptions', async () => {
    fakeBackend({
      'GET /api/calendars/public': [
        publicCalendar('a', { name: 'Holidays', description: 'Bank holidays' }),
        publicCalendar('b', { name: 'Football', owner_name: 'Bob', added: true }),
      ],
    })
    const wrapper = await render()
    expect(wrapper.text()).toContain('Public calendars')
    const [holidays, football] = rows(wrapper)
    expect(holidays!.text()).toContain('Holidays')
    expect(holidays!.text().replace(/\s+/g, ' ')).toContain('by Alice · Bank holidays')
    expect(holidays!.get('button').text()).toBe('Add')
    expect(football!.text()).toContain('by Bob')
    expect(football!.text()).not.toContain('·')
    expect(football!.get('button').text()).toBe('Remove from sidebar')
  })

  it('says so while loading and when there are none', async () => {
    fakeBackend({ 'GET /api/calendars/public': [] })
    const wrapper = mount(PublicCalendarsDialog, { global: { plugins: [i18n], stubs: { teleport: true } } })
    expect(wrapper.text()).toContain('Loading…')
    await flushPromises()
    expect(wrapper.text()).toContain('There are no other public calendars.')
    expect(wrapper.find('input[type="search"]').exists()).toBe(false)
  })

  it('finds calendars by name, description or owner', async () => {
    fakeBackend({
      'GET /api/calendars/public': [
        publicCalendar('a', { name: 'Holidays', description: 'Bank holidays' }),
        publicCalendar('b', { name: 'Football', owner_name: 'Bob' }),
      ],
    })
    const wrapper = await render()
    const search = wrapper.get('input[type="search"]')
    await search.setValue('bank')
    expect(rows(wrapper).map((row) => row.find('.font-medium').text())).toEqual(['Holidays'])
    await search.setValue('BOB')
    expect(rows(wrapper).map((row) => row.find('.font-medium').text())).toEqual(['Football'])
    await search.setValue('tennis')
    expect(wrapper.text()).toContain('No matching calendars found.')
  })

  it('adds a calendar to the sidebar and takes it out again', async () => {
    const backend = fakeBackend({
      'GET /api/calendars/public': [publicCalendar('a')],
      'PUT /api/calendars/*/subscription': undefined,
      'DELETE /api/calendars/*/subscription': undefined,
      'GET /api/layout': { folders: [], calendars: [calendarItem('a', { access: 'public', role: 'read' })] },
    })
    const wrapper = await render()
    await wrapper.get('li button').trigger('click')
    await flushPromises()
    expect(backend.calls('PUT /api/calendars/a/subscription')).toHaveLength(1)
    expect(useCalendarStore().items.map((item) => item.calendar.id)).toEqual(['a'])
    expect(wrapper.get('li button').text()).toBe('Remove from sidebar')

    await wrapper.get('li button').trigger('click')
    await flushPromises()
    expect(backend.calls('DELETE /api/calendars/a/subscription')).toHaveLength(1)
    expect(wrapper.get('li button').text()).toBe('Add')
    expect(backend.unhandled).toEqual([])
  })

  it('reports a failed change and leaves the calendar as it was', async () => {
    fakeBackend({
      'GET /api/calendars/public': [publicCalendar('a')],
      'PUT /api/calendars/*/subscription': reply(403, { detail: 'Not allowed' }),
    })
    const wrapper = await render()
    await wrapper.get('li button').trigger('click')
    await flushPromises()
    expect(wrapper.get('li button').text()).toBe('Add')
    expect(toasts.map((toast) => toast.message)).toEqual(['Not allowed'])
  })

  it('closes', async () => {
    fakeBackend({ 'GET /api/calendars/public': [] })
    const wrapper = await render()
    await wrapper.get('button[aria-label]').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })
})
