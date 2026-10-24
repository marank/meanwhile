import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { defineComponent, h, nextTick, ref } from 'vue'
import { i18n } from '@/i18n'
import { buildRrule, parseRrule, recurrenceDefaults, type RecurrenceRule } from '@/services/rrule'
import EventRecurrenceTab from '../EventRecurrenceTab.vue'
import { signIn } from './helpers'

// 10 March 2026 is a Tuesday.
const START = '2026-03-10'

/** The dialog's side of the tab: it owns the rule and writes it as an RRULE. */
const Dialog = defineComponent({
  props: { rrule: { type: String, default: null }, foreign: { type: String, default: null } },
  setup(props) {
    const rule = ref<RecurrenceRule | null>(parseRrule(props.rrule, recurrenceDefaults(new Date(`${START}T00:00:00`))))
    const foreign = ref<string | null>(props.foreign)
    const showCount = ref(false)
    return () =>
      h('div', [
        h(EventRecurrenceTab, {
          start: START,
          rule: rule.value,
          'onUpdate:rule': (value: RecurrenceRule | null) => (rule.value = value),
          foreign: foreign.value,
          'onUpdate:foreign': (value: string | null) => (foreign.value = value),
          showCount: showCount.value,
          'onUpdate:showCount': (value: boolean) => (showCount.value = value),
        }),
        h('output', { 'data-rrule': '' }, foreign.value ?? buildRrule(rule.value) ?? 'none'),
        h('output', { 'data-count': '' }, String(showCount.value)),
      ])
  },
})

let wrapper: VueWrapper

function render(props: { rrule?: string; foreign?: string } = {}) {
  wrapper = mount(Dialog, { props, global: { plugins: [i18n] }, attachTo: document.body })
  return wrapper
}

const rrule = () => wrapper.get('[data-rrule]').text()
const combobox = (label?: string) =>
  label ? wrapper.get(`[role="combobox"][aria-label="${label}"]`) : wrapper.findAll('[role="combobox"]')[0]!

/** The options of a select, which lives in <body>. */
function options(field: ReturnType<typeof combobox>) {
  const list = document.getElementById(field.attributes('aria-controls')!)!
  return [...list.querySelectorAll<HTMLElement>('[role="option"]')]
}

async function pick(field: ReturnType<typeof combobox>, label: string) {
  await field.trigger('click')
  options(field)
    .find((option) => option.textContent!.trim() === label)!
    .click()
  await nextTick()
}

const button = (text: string) => wrapper.findAll('button').find((b) => b.text() === text)!

describe('EventRecurrenceTab', () => {
  beforeEach(() => signIn())
  afterEach(() => {
    wrapper?.unmount()
    vi.restoreAllMocks()
  })

  it('offers patterns based on the start date', async () => {
    render()
    expect(combobox().text()).toBe('Does not repeat')
    await combobox().trigger('click')
    expect(options(combobox()).map((o) => o.textContent!.trim())).toEqual([
      'Does not repeat',
      'Daily',
      'Every weekday (Mon–Fri)',
      'Weekly on Tuesday',
      'Every two weeks on Tuesday',
      'Monthly on day 10',
      'Monthly on the second Tuesday',
      'Yearly on March 10',
      'Custom…',
    ])
    // Without a recurrence there is nothing more to set.
    expect(wrapper.text()).not.toContain('Ends')
  })

  it('repeats by a pattern and keeps how the series ends when switching', async () => {
    render()
    await pick(combobox(), 'Weekly on Tuesday')
    expect(rrule()).toBe('FREQ=WEEKLY;BYDAY=TU')
    await button('After').trigger('click')
    await wrapper.get('input[aria-label="After"]').setValue(5)
    expect(rrule()).toBe('FREQ=WEEKLY;BYDAY=TU;COUNT=5')
    expect(wrapper.text()).toContain('occurrences')

    await pick(combobox(), 'Monthly on the second Tuesday')
    expect(rrule()).toBe('FREQ=MONTHLY;BYDAY=2TU;COUNT=5')
    await button('On date').trigger('click')
    const until = wrapper.get('input[type="date"]')
    expect(until.attributes('min')).toBe(START)
    await until.setValue('2026-12-31')
    expect(rrule()).toBe('FREQ=MONTHLY;BYDAY=2TU;UNTIL=20261231')

    await wrapper.get('input[type="checkbox"]').setValue(true)
    expect(wrapper.get('[data-count]').text()).toBe('true')

    await pick(combobox(), 'Does not repeat')
    expect(rrule()).toBe('none')
  })

  it('recognises a preset in a loaded rule', () => {
    render({ rrule: 'FREQ=YEARLY;BYMONTH=3;BYMONTHDAY=10' })
    expect(combobox().text()).toBe('Yearly on March 10')
  })

  it('edits a custom weekly rule', async () => {
    render()
    await pick(combobox(), 'Custom…')
    // A new custom rule starts weekly on the start's weekday …
    expect(rrule()).toBe('FREQ=WEEKLY;BYDAY=TU')
    // … and stays custom, though it matches a preset.
    expect(combobox().text()).toBe('Custom…')

    await wrapper.get('input[aria-label="Every"]').setValue(3)
    const day = (name: string) => wrapper.get(`[role="group"] button[title="${name}"]`)
    await day('Thursday').trigger('click')
    expect(day('Thursday').attributes('aria-pressed')).toBe('true')
    expect(rrule()).toBe('FREQ=WEEKLY;INTERVAL=3;BYDAY=TU,TH')
    await day('Tuesday').trigger('click')
    await day('Thursday').trigger('click')
    // The last day stays: a weekly rule needs one.
    expect(rrule()).toBe('FREQ=WEEKLY;INTERVAL=3;BYDAY=TH')
    expect(combobox('Repeat').text()).toBe('weeks')
  })

  it('shows a loaded rule that matches no preset in the custom editor', () => {
    render({ rrule: 'FREQ=MONTHLY;BYMONTHDAY=1,15' })
    expect(combobox().text()).toBe('Custom…')
    expect((wrapper.get('input[aria-label="Days of the month"]').element as HTMLInputElement).value).toBe('1, 15')
  })

  it('edits a custom monthly rule by date or by weekday', async () => {
    render()
    await pick(combobox(), 'Custom…')
    await pick(combobox('Repeat'), 'month')
    expect(wrapper.text()).toContain('Separate several values with commas')
    await wrapper.get('input[aria-label="Days of the month"]').setValue('1, +')
    expect(rrule()).toBe('FREQ=MONTHLY;BYMONTHDAY=1,-1')

    // Opened explicitly, the editor stays open while the rule matches a preset.
    await button('Weekday').trigger('click')
    expect(rrule()).toBe('FREQ=MONTHLY;BYDAY=2TU')
    await wrapper.get('input[aria-label="Positions in the month"]').setValue('1, 3')
    await pick(combobox('Days of the week'), 'Friday')
    expect(rrule()).toBe('FREQ=MONTHLY;BYDAY=1FR,3FR')
  })

  it('edits a custom yearly rule', async () => {
    render()
    await pick(combobox(), 'Custom…')
    await pick(combobox('Repeat'), 'year')
    await wrapper.get('input[aria-label="Months"]').setValue('3, 10')
    expect(rrule()).toBe('FREQ=YEARLY;BYMONTH=3,10;BYMONTHDAY=10')
  })

  it('keeps a rule it cannot show unless another one is chosen', async () => {
    render({ foreign: 'FREQ=HOURLY' })
    expect(combobox().text()).toBe('Keep as is')
    await pick(combobox(), 'Keep as is')
    expect(rrule()).toBe('FREQ=HOURLY')
    await pick(combobox(), 'Daily')
    expect(rrule()).toBe('FREQ=DAILY')
    expect(combobox().text()).toBe('Daily')
  })
})
