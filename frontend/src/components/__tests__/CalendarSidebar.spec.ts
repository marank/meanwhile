import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import type { Layout } from '@/api'
import { i18n } from '@/i18n'
import { dialog, submitDialog } from '@/services/dialog'
import { realtime } from '@/services/realtime'
import { collapsedFolders, sidebarDrawerOpen } from '@/services/sidebarState'
import { toasts } from '@/services/toast'
import { fakeBackend, reply, type FakeBackend } from '@/__tests__/fakeBackend'
import CalendarSidebar from '../CalendarSidebar.vue'
import { calendar, calendarItem, folder, stubMatchMedia } from '../calendar/__tests__/calendarFixtures'

const Page = { template: '<div />' }

function layout(): Layout {
  return {
    folders: [folder('f1', null, 0), folder('f2', 'f1', 0)],
    calendars: [
      calendarItem('mine', { position: 1, calendar: { name: 'Mine', url_path: 'team/mine' } }),
      calendarItem('managed', { role: 'manage', folderId: 'f1', position: 1, calendar: { name: 'Managed' } }),
      calendarItem('shared', { role: 'full', position: 2, calendar: { name: 'Shared' } }),
      calendarItem('holidays', { role: 'read', access: 'public', position: 3, calendar: { name: 'Holidays' } }),
    ],
  }
}

let backend: FakeBackend
let router: Router

async function render() {
  router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/calendar/folder/:folderId', component: Page },
      { path: '/calendar/:calendarId(.*)?', component: Page },
      { path: '/calendar/:calendarId/settings', component: Page },
    ],
  })
  await router.push('/calendar')
  const wrapper = mount(CalendarSidebar, {
    global: { plugins: [i18n, router], stubs: { teleport: true } },
    attachTo: document.body,
  })
  await flushPromises()
  return wrapper
}

type Wrapper = Awaited<ReturnType<typeof render>>

/** Answers the prompt or confirmation that is open, as the user would. */
async function answer(value: unknown) {
  await flushPromises()
  expect(dialog.open).toBe(true)
  submitDialog(value)
  await flushPromises()
}

const row = (wrapper: Wrapper, id: string) => wrapper.get(`[data-id="${id}"]`)
const folderRow = (wrapper: Wrapper, id: string) => wrapper.get(`[data-id="${id}"] [role="button"]`)
const menuEntries = (wrapper: Wrapper) => wrapper.findAll('[role="menuitem"]').map((item) => item.text())

async function choose(wrapper: Wrapper, label: string) {
  await wrapper
    .findAll('[role="menuitem"]')
    .find((item) => item.text() === label)!
    .trigger('click')
}

describe('CalendarSidebar', () => {
  beforeEach(() => {
    localStorage.clear()
    stubMatchMedia()
    setActivePinia(createPinia())
    i18n.global.locale.value = 'en'
    vi.spyOn(realtime, 'setCalendars').mockImplementation(() => {})
    toasts.splice(0)
    backend = fakeBackend({ 'GET /api/layout': layout() })
  })

  afterEach(() => {
    if (dialog.open) submitDialog(null)
    sidebarDrawerOpen.value = false
    collapsedFolders.clear()
    vi.restoreAllMocks()
    document.body.innerHTML = ''
  })

  it('shows the folders and calendars of the layout', async () => {
    const wrapper = await render()
    expect(backend.calls('GET /api/layout')).toHaveLength(1)
    const names = wrapper.findAll('.sidebar-item [role="button"], [role="button"].sidebar-item').map((el) => el.text())
    expect(names).toEqual(['Folder f1', 'Folder f2', 'Managed', 'Mine', 'Shared', 'Holidays'])
    expect(wrapper.get('[aria-current="true"]').text()).toBe('All calendars')
  })

  it('opens what is clicked: all calendars, a calendar by its readable path, or a folder', async () => {
    const wrapper = await render()
    await row(wrapper, 'mine').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/calendar/team/mine')

    await folderRow(wrapper, 'f1').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/calendar/folder/f1')

    await row(wrapper, 'managed').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/calendar/managed')

    await wrapper
      .findAll('[role="button"]')
      .find((el) => el.text() === 'All calendars')!
      .trigger('keydown', {
        key: 'Enter',
      })
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/calendar')
  })

  it('creates a calendar and opens it', async () => {
    backend.on('POST /api/calendars', calendar('new', { name: 'Fresh' }))
    const wrapper = await render()
    backend.on('GET /api/layout', { ...layout(), calendars: [...layout().calendars, calendarItem('new')] })
    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'New calendar')!
      .trigger('click')
    expect(dialog.kind).toBe('prompt')
    expect(dialog.title).toBe('New calendar')
    await answer('Fresh')
    expect(backend.calls('POST /api/calendars')[0]!.body).toMatchObject({ name: 'Fresh' })
    expect(router.currentRoute.value.fullPath).toBe('/calendar/new')
  })

  it('creates nothing when the name prompt is cancelled', async () => {
    const wrapper = await render()
    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'New calendar')!
      .trigger('click')
    await answer(null)
    expect(backend.calls('POST /api/calendars')).toHaveLength(0)
  })

  it('offers the owner of a calendar to rename it, delete it or open its settings', async () => {
    backend.on('PATCH /api/calendars/mine', calendar('mine', { name: 'Renamed', url_path: 'team/mine' }))
    backend.on('DELETE /api/calendars/mine', undefined)
    const wrapper = await render()

    await row(wrapper, 'mine').trigger('contextmenu', { clientX: 40, clientY: 50 })
    // A right click selects the calendar too.
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/calendar/team/mine')
    expect(menuEntries(wrapper)).toEqual(['Rename', 'Delete', 'Settings'])
    expect(wrapper.get<HTMLElement>('[role="menu"]').element.style.left).toBe('40px')

    await choose(wrapper, 'Rename')
    expect(dialog.message).toBe('Enter a name for the new calendar.')
    await answer('Renamed')
    expect(backend.calls('PATCH /api/calendars/mine')[0]!.body).toEqual({ name: 'Renamed' })
    expect(row(wrapper, 'mine').text()).toBe('Renamed')

    await row(wrapper, 'mine').trigger('contextmenu', { clientX: 40, clientY: 50 })
    await choose(wrapper, 'Delete')
    expect(dialog.title).toBe('Delete calendar?')
    await answer(false)
    expect(backend.calls('DELETE /api/calendars/mine')).toHaveLength(0)

    await row(wrapper, 'mine').trigger('contextmenu', { clientX: 40, clientY: 50 })
    await choose(wrapper, 'Delete')
    await answer(true)
    expect(backend.calls('DELETE /api/calendars/mine')).toHaveLength(1)
    expect(backend.calls('GET /api/layout')).toHaveLength(2)

    await row(wrapper, 'mine').trigger('contextmenu', { clientX: 40, clientY: 50 })
    await choose(wrapper, 'Settings')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/calendar/mine/settings')
  })

  it('lets managers change a calendar but not delete it, and gives others no menu', async () => {
    const wrapper = await render()
    await row(wrapper, 'managed').trigger('contextmenu', { clientX: 1, clientY: 1 })
    expect(menuEntries(wrapper)).toEqual(['Rename', 'Settings'])
    await wrapper.get('.fixed.inset-0').trigger('click')

    await row(wrapper, 'shared').trigger('contextmenu', { clientX: 1, clientY: 1 })
    expect(wrapper.find('[role="menu"]').exists()).toBe(false)
  })

  it('takes an added public calendar out of the sidebar', async () => {
    backend.on('DELETE /api/calendars/holidays/subscription', undefined)
    const wrapper = await render()
    await row(wrapper, 'holidays').trigger('contextmenu', { clientX: 1, clientY: 1 })
    expect(menuEntries(wrapper)).toEqual(['Remove from sidebar'])
    await choose(wrapper, 'Remove from sidebar')
    await flushPromises()
    expect(backend.calls('DELETE /api/calendars/holidays/subscription')).toHaveLength(1)
    expect(backend.calls('GET /api/layout')).toHaveLength(2)
  })

  it('creates, renames and deletes folders from their menu', async () => {
    backend.on('POST /api/layout/folders', folder('f3', 'f1'))
    backend.on('PATCH /api/layout/folders/*', folder('f1'))
    backend.on('DELETE /api/layout/folders/*', undefined)
    const wrapper = await render()

    await folderRow(wrapper, 'f1').trigger('contextmenu', { clientX: 1, clientY: 1 })
    expect(menuEntries(wrapper)).toEqual(['Create folder', 'Rename', 'Delete'])
    await choose(wrapper, 'Create folder')
    await answer('Sub')
    expect(backend.calls('POST /api/layout/folders')[0]!.body).toEqual({ name: 'Sub', parent_id: 'f1' })

    await folderRow(wrapper, 'f2').trigger('contextmenu', { clientX: 1, clientY: 1 })
    await choose(wrapper, 'Rename')
    expect(dialog.message).toBe('Enter a name for the new folder.')
    await answer('Inner')
    expect(backend.calls('PATCH /api/layout/folders/f2')[0]!.body).toEqual({ name: 'Inner' })

    await folderRow(wrapper, 'f1').trigger('contextmenu', { clientX: 1, clientY: 1 })
    await choose(wrapper, 'Delete')
    expect(dialog.title).toBe('Delete folder?')
    await answer(true)
    expect(backend.calls('DELETE /api/layout/folders/f1')).toHaveLength(1)
    expect(backend.unhandled).toEqual([])
  })

  it('reports a failed action', async () => {
    backend.on('POST /api/layout/folders', reply(400, { detail: 'Name taken' }))
    const wrapper = await render()
    await folderRow(wrapper, 'f1').trigger('contextmenu', { clientX: 1, clientY: 1 })
    await choose(wrapper, 'Create folder')
    await answer('Sub')
    expect(toasts.map((toast) => toast.message)).toEqual(['Name taken'])
  })

  it('offers a top-level folder and the public calendars on the empty list and from the button', async () => {
    backend.on('POST /api/layout/folders', folder('f9'))
    backend.on('GET /api/calendars/public', [])
    const wrapper = await render()

    await wrapper.get('.overflow-y-auto').trigger('contextmenu', { clientX: 5, clientY: 5 })
    expect(menuEntries(wrapper)).toEqual(['Create folder', 'Public calendars'])
    await choose(wrapper, 'Create folder')
    await answer('Top')
    expect(backend.calls('POST /api/layout/folders')[0]!.body).toEqual({ name: 'Top', parent_id: null })

    await wrapper.get('button[aria-label="More actions"]').trigger('click')
    expect(menuEntries(wrapper)).toEqual(['Create folder', 'Public calendars'])
    await choose(wrapper, 'Public calendars')
    await flushPromises()
    expect(backend.calls('GET /api/calendars/public')).toHaveLength(1)
    expect(wrapper.text()).toContain('There are no other public calendars.')

    await wrapper.get('[role="dialog"] button[aria-label]').trigger('click')
    expect(wrapper.text()).not.toContain('There are no other public calendars.')
  })

  it('opens the menu below the row when it is asked for from the keyboard', async () => {
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
      left: 30,
      top: 100,
      right: 230,
      bottom: 132,
      width: 200,
      height: 32,
      x: 30,
      y: 100,
      toJSON: () => ({}),
    })
    const wrapper = await render()
    await row(wrapper, 'mine').trigger('contextmenu')
    await flushPromises()
    const menu = wrapper.get<HTMLElement>('[role="menu"]').element
    expect(menu.style.left).toBe('46px')
    expect(menu.style.top).toBe('132px')
  })

  it('moves a calendar into a folder dropped on it, and opens the folder', async () => {
    backend.on('PATCH /api/layout/items', undefined)
    // jsdom has no layout: the rows get 32 px each, from the top, in the order shown.
    const tops: Record<string, number> = { f1: 0, f2: 36, managed: 72, mine: 108, shared: 144, holidays: 180 }
    vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function (this: Element) {
      const el = this as HTMLElement
      const id = el.dataset.id ?? (el.parentElement?.dataset.type === 'folder' ? el.parentElement.dataset.id : '')
      const top = id ? tops[id] : undefined
      const [y, height] = top === undefined ? [0, el.classList.contains('overflow-y-auto') ? 400 : 0] : [top, 32]
      return { left: 0, top: y, right: 240, bottom: y + height, width: 240, height, x: 0, y, toJSON: () => ({}) }
    })
    const wrapper = await render()
    collapsedFolders.add('f1')
    const pointer = (type: string, y: number) =>
      new PointerEvent(type, { bubbles: true, button: 0, isPrimary: true, pointerId: 1, clientX: 20, clientY: y })
    row(wrapper, 'shared').element.dispatchEvent(pointer('pointerdown', 150))
    document.dispatchEvent(pointer('pointermove', 16))
    document.dispatchEvent(pointer('pointerup', 16))
    await flushPromises()
    expect(backend.calls('PATCH /api/layout/items')[0]!.body).toEqual({
      items: expect.arrayContaining([expect.objectContaining({ type: 'calendar', id: 'shared', parent_id: 'f1' })]),
    })
    expect(collapsedFolders.has('f1')).toBe(false)
  })

  it('is a drawer on small screens that closes from its backdrop, with Escape, or once something is opened', async () => {
    const wrapper = await render()
    const aside = () => wrapper.get('aside')
    expect(aside().attributes('data-state')).toBe('closed')
    expect(wrapper.find('[data-drawer-backdrop]').exists()).toBe(false)

    sidebarDrawerOpen.value = true
    await flushPromises()
    expect(aside().attributes('data-state')).toBe('open')
    await wrapper.get('[data-drawer-backdrop]').trigger('click')
    expect(sidebarDrawerOpen.value).toBe(false)

    sidebarDrawerOpen.value = true
    await flushPromises()
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', cancelable: true }))
    expect(sidebarDrawerOpen.value).toBe(false)

    sidebarDrawerOpen.value = true
    await flushPromises()
    await row(wrapper, 'shared').trigger('click')
    await flushPromises()
    expect(sidebarDrawerOpen.value).toBe(false)
  })

  it('keeps the drawer open while a right click selects a calendar for its menu', async () => {
    const wrapper = await render()
    sidebarDrawerOpen.value = true
    await flushPromises()
    await row(wrapper, 'mine').trigger('contextmenu', { clientX: 1, clientY: 1 })
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/calendar/team/mine')
    expect(sidebarDrawerOpen.value).toBe(true)
  })

  it('is resized by dragging its edge, within limits, and remembers the width', async () => {
    localStorage.setItem('sidebar-width', '300')
    const wrapper = await render()
    const width = () => wrapper.get<HTMLElement>('aside').element.style.getPropertyValue('--sidebar-width')
    expect(width()).toBe('300px')

    await wrapper.get('.cursor-col-resize').trigger('mousedown', { clientX: 300 })
    expect(document.body.style.userSelect).toBe('none')
    window.dispatchEvent(new MouseEvent('mousemove', { clientX: 350 }))
    await flushPromises()
    expect(width()).toBe('350px')
    window.dispatchEvent(new MouseEvent('mousemove', { clientX: 1000 }))
    await flushPromises()
    expect(width()).toBe('500px')
    window.dispatchEvent(new MouseEvent('mousemove', { clientX: 0 }))
    await flushPromises()
    expect(width()).toBe('180px')
    window.dispatchEvent(new MouseEvent('mouseup'))
    expect(localStorage.getItem('sidebar-width')).toBe('180')
    expect(document.body.style.userSelect).toBe('')

    // Released, moving the mouse changes nothing.
    window.dispatchEvent(new MouseEvent('mousemove', { clientX: 400 }))
    await flushPromises()
    expect(width()).toBe('180px')
  })

  it('starts at the default width without a stored one', async () => {
    const wrapper = await render()
    expect(wrapper.get<HTMLElement>('aside').element.style.getPropertyValue('--sidebar-width')).toBe('256px')
  })
})
