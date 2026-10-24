import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { i18n } from '@/i18n'
import { MAX_REMINDERS } from '@/services/reminders'
import EventRemindersTab from '../event/EventRemindersTab.vue'

function render(minutes: number[], allDay = false) {
  i18n.global.locale.value = 'de'
  return mount(EventRemindersTab, {
    props: { modelValue: minutes, allDay },
    global: { plugins: [i18n] },
    attachTo: document.body,
  })
}

function lastValue(wrapper: ReturnType<typeof render>, event = 'update:modelValue') {
  const emitted = wrapper.emitted(event)!
  return emitted[emitted.length - 1]![0]
}

describe('EventRemindersTab', () => {
  it('shows each reminder in its largest unit', () => {
    const wrapper = render([15, 120])
    const amounts = wrapper.findAll('input[type="number"]').map((input) => (input.element as HTMLInputElement).value)
    expect(amounts).toEqual(['15', '2'])
    wrapper.unmount()
  })

  it('offers no more reminders than the server keeps', () => {
    const wrapper = render(Array.from({ length: MAX_REMINDERS }, (_, i) => (i + 1) * 5))
    const add = wrapper.findAll('button').find((b) => b.text() === i18n.global.t('reminders.add'))!
    expect(add.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).not.toContain(i18n.global.t('reminders.quick'))
    wrapper.unmount()
  })

  it('adds, changes and removes reminders', async () => {
    const wrapper = render([15])
    await wrapper.get('input[type="number"]').setValue(30)
    expect(lastValue(wrapper)).toEqual([30])

    const quick = wrapper.findAll('button').find((b) => b.text() === '1 Stunde vorher')!
    await quick.trigger('click')
    expect(lastValue(wrapper)).toEqual([30, 60])

    await wrapper.get('button[aria-label="Erinnerung entfernen"]').trigger('click')
    expect(lastValue(wrapper)).toEqual([60])
    wrapper.unmount()
  })

  it('reports invalid reminders and leaves them out', async () => {
    const wrapper = render([900], true)
    const [days, time] = [wrapper.get('input[type="number"]'), wrapper.get('input[type="time"]')]
    expect(wrapper.text()).toContain('Am Vortag um 09:00')
    await days.setValue(0)
    await time.setValue('10:00')
    await nextTick()
    expect(lastValue(wrapper, 'update:valid')).toBe(false)
    expect(lastValue(wrapper)).toEqual([])
    expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    wrapper.unmount()
  })
})
