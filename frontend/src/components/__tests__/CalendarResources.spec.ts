import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, KeepAlive, nextTick, ref } from 'vue'
import * as api from '@/api'
import { i18n } from '@/i18n'
import { provideCalendarSettingsSync } from '@/composables/useCalendarSettingsSync'
import CalendarResources from '../calendar-settings/CalendarResources.vue'

vi.mock('@/api', async (original) => ({
  ...(await original<typeof import('@/api')>()),
  listResources: vi.fn(),
  listCalendarApprovers: vi.fn(),
  searchEntities: vi.fn(),
}))

const approver = (id: string, name: string) => ({ user_id: id, display_name: name, email: `${id}@example.test` })
const resource = (approvers: ReturnType<typeof approver>[]) =>
  ({
    id: 'r1',
    calendar_id: 'c',
    name: 'Room',
    description: '',
    color: '#f59e0b',
    requires_approval: true,
    is_location: false,
    is_active: true,
    approvers,
  }) as api.Resource

/** The settings page: the resources tab and another one, kept alive, and the channel between them. */
function page() {
  let sync!: ReturnType<typeof provideCalendarSettingsSync>
  const showResources = ref(true)
  const Page = defineComponent({
    setup() {
      sync = provideCalendarSettingsSync()
      return () =>
        h(KeepAlive, null, {
          default: () =>
            showResources.value ? h(CalendarResources, { calendarId: 'c', canManage: true }) : h('p', 'other tab'),
        })
    },
  })
  const wrapper = mount(Page, { global: { plugins: [i18n] } })
  return { wrapper, showResources, sync: () => sync }
}

describe('resources tab and member changes', () => {
  beforeEach(() => {
    i18n.global.locale.value = 'en'
    vi.mocked(api.searchEntities).mockResolvedValue([])
    vi.mocked(api.listCalendarApprovers).mockResolvedValue([approver('kim', 'Kim')])
    vi.mocked(api.listResources).mockResolvedValue([resource([approver('kim', 'Kim')])])
  })

  afterEach(() => vi.clearAllMocks())

  it('loads again at once when members change while it is shown', async () => {
    const { wrapper, sync } = page()
    await flushPromises()
    expect(wrapper.text()).toContain('Kim')

    vi.mocked(api.listCalendarApprovers).mockResolvedValue([])
    vi.mocked(api.listResources).mockResolvedValue([resource([])])
    sync().membersChanged()
    await flushPromises()
    expect(api.listResources).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).not.toContain('Kim')
    wrapper.unmount()
  })

  it('waits until it is shown again when it is hidden at the time, and then loads once', async () => {
    const { wrapper, showResources, sync } = page()
    await flushPromises()
    showResources.value = false
    await nextTick()

    vi.mocked(api.listResources).mockResolvedValue([resource([])])
    vi.mocked(api.listCalendarApprovers).mockResolvedValue([])
    sync().membersChanged()
    sync().membersChanged()
    await flushPromises()
    expect(api.listResources).toHaveBeenCalledTimes(1)

    showResources.value = true
    await flushPromises()
    expect(api.listResources).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).not.toContain('Kim')
    // Switching back and forth without changes doesn't load again.
    showResources.value = false
    await nextTick()
    showResources.value = true
    await flushPromises()
    expect(api.listResources).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('keeps showing what it has when the reload fails, and tries again when shown next', async () => {
    const { wrapper, showResources, sync } = page()
    await flushPromises()
    vi.mocked(api.listResources).mockRejectedValueOnce(new Error('offline'))
    sync().membersChanged()
    await flushPromises()
    expect(wrapper.text()).toContain('Kim')

    showResources.value = false
    await nextTick()
    showResources.value = true
    await flushPromises()
    expect(api.listResources).toHaveBeenCalledTimes(3)
    wrapper.unmount()
  })
})
