import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { i18n } from '@/i18n'
import { useCalendarStore } from '@/stores/calendars'
import { useThemeStore } from '@/stores/theme'
import { collapsedFolders, dropTargetFolderId } from '@/services/sidebarState'
import FolderTreeItem from '../FolderTreeItem.vue'
import SidebarCalendarItem from '../SidebarCalendarItem.vue'
import { calendarItem, folder, stubMatchMedia } from '../calendar/__tests__/calendarFixtures'

describe('SidebarCalendarItem', () => {
  beforeEach(() => {
    localStorage.clear()
    stubMatchMedia()
    setActivePinia(createPinia())
    i18n.global.locale.value = 'en'
  })

  function render(selected = false) {
    const item = calendarItem('c1', { calendar: { name: 'Work' } })
    return { item, wrapper: mount(SidebarCalendarItem, { props: { item, selected }, global: { plugins: [i18n] } }) }
  }

  it('shows the calendar with its event color, and marks it when selected', async () => {
    const { wrapper } = render(true)
    expect(wrapper.text()).toBe('Work')
    expect(wrapper.attributes('aria-current')).toBe('true')
    expect(wrapper.attributes('data-id')).toBe('c1')
    expect(wrapper.find<HTMLElement>('span').element.style.backgroundColor).toBe('rgb(51, 102, 153)')

    useThemeStore().setPreference('dark')
    await wrapper.vm.$nextTick()
    expect(wrapper.find<HTMLElement>('span').element.style.backgroundColor).toBe('rgb(153, 187, 221)')
  })

  it('selects the calendar by click and by keyboard', async () => {
    const { wrapper } = render()
    expect(wrapper.attributes('aria-current')).toBeUndefined()
    await wrapper.trigger('click')
    await wrapper.trigger('keydown', { key: 'Enter' })
    await wrapper.trigger('keydown', { key: ' ' })
    expect(wrapper.emitted('select')).toEqual([['c1'], ['c1'], ['c1']])
  })

  it('selects the calendar and asks for its menu on a right click', async () => {
    const { item, wrapper } = render()
    await wrapper.trigger('contextmenu')
    expect(wrapper.emitted('select')).toEqual([['c1']])
    expect(wrapper.emitted('contextMenu')![0]![1]).toEqual(item)
  })
})

describe('FolderTreeItem', () => {
  beforeEach(() => {
    stubMatchMedia()
    setActivePinia(createPinia())
    i18n.global.locale.value = 'en'
    const store = useCalendarStore()
    store.folders = [folder('f1'), folder('f2', 'f1'), folder('empty')]
    store.items = [
      calendarItem('c1', { folderId: 'f1', calendar: { name: 'In folder' } }),
      calendarItem('c2', { folderId: 'f2', calendar: { name: 'Nested' } }),
    ]
  })

  afterEach(() => {
    collapsedFolders.clear()
    dropTargetFolderId.value = null
  })

  function render(id = 'f1') {
    const store = useCalendarStore()
    return mount(FolderTreeItem, {
      props: { folder: store.folders.find((f) => f.id === id)! },
      global: { plugins: [i18n] },
    })
  }

  const header = (wrapper: ReturnType<typeof render>) => wrapper.get('[role="button"]')

  it('shows the folder with what is in it, nested folders included', () => {
    const wrapper = render()
    expect(header(wrapper).text()).toContain('Folder f1')
    expect(wrapper.text()).toContain('Folder f2')
    expect(wrapper.text()).toContain('In folder')
    expect(wrapper.text()).toContain('Nested')
  })

  it('closes and opens with its arrow and with the arrow keys', async () => {
    const wrapper = render()
    const list = () => wrapper.get<HTMLElement>('[data-folder-id="f1"]').element
    const toggle = () => wrapper.get('button[aria-expanded]')
    expect(toggle().attributes('aria-label')).toBe('Collapse')

    await toggle().trigger('click')
    expect(list().style.display).toBe('none')
    expect(toggle().attributes('aria-label')).toBe('Expand')
    expect(collapsedFolders.has('f1')).toBe(true)
    // The arrow doesn't select the folder.
    expect(wrapper.emitted('select')).toBeUndefined()

    await header(wrapper).trigger('keydown', { key: 'ArrowRight' })
    expect(list().style.display).toBe('')
    await header(wrapper).trigger('keydown', { key: 'ArrowLeft' })
    expect(list().style.display).toBe('none')
  })

  it('has no arrow when it is empty', () => {
    expect(render('empty').find('button[aria-expanded]').exists()).toBe(false)
  })

  it('selects the folder, and passes on what is selected inside it', async () => {
    const wrapper = render()
    await header(wrapper).trigger('click')
    await header(wrapper).trigger('keydown', { key: 'Enter' })
    await wrapper.get('[data-id="c1"]').trigger('click')
    await wrapper.get('[data-id="c2"]').trigger('click')
    await wrapper.get('[data-id="f2"] [role="button"]').trigger('click')
    expect(wrapper.emitted('select')).toEqual([['f1'], ['f1'], ['c1'], ['c2'], ['f2']])
  })

  it('marks the selected folder and calendar, and the folder something would be dropped into', async () => {
    const store = useCalendarStore()
    store.select('f1')
    dropTargetFolderId.value = 'f1'
    const wrapper = render()
    expect(header(wrapper).attributes('aria-current')).toBe('true')
    expect(header(wrapper).classes()).toContain('ring-2')
    store.select('c1')
    await wrapper.vm.$nextTick()
    expect(wrapper.get('[data-id="c1"]').attributes('aria-current')).toBe('true')
  })

  it('asks for the menus of folders and calendars, its own and nested ones', async () => {
    const store = useCalendarStore()
    const wrapper = render()
    await header(wrapper).trigger('contextmenu')
    await wrapper.get('[data-id="f2"] [role="button"]').trigger('contextmenu')
    await wrapper.get('[data-id="c1"]').trigger('contextmenu')
    await wrapper.get('[data-id="c2"]').trigger('contextmenu')
    expect(wrapper.emitted('folderMenu')!.map((args) => args[1])).toEqual([store.folders[0], store.folders[1]])
    expect(wrapper.emitted('calendarMenu')!.map((args) => args[1])).toEqual([store.items[0], store.items[1]])
  })
})
