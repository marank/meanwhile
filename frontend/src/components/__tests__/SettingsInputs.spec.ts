import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { i18n } from '@/i18n'
import AppSwitch from '../AppSwitch.vue'
import ColorPaletteSelect from '../ColorPaletteSelect.vue'
import NumberListInput from '../NumberListInput.vue'
import ResourceIconPicker from '../ResourceIconPicker.vue'
import RoleSelect from '../RoleSelect.vue'
import SegmentedControl from '../SegmentedControl.vue'
import SettingsToggle from '../SettingsToggle.vue'
import WeekLayoutFields from '../WeekLayoutFields.vue'

// The lists of selects are teleported to <body>.
function optionTexts(): string[] {
  return [...document.querySelectorAll('[role="option"]')].map((option) => option.textContent!.trim())
}

function clickOption(text: string) {
  const option = [...document.querySelectorAll<HTMLElement>('[role="option"]')].find(
    (o) => o.textContent!.trim() === text,
  )
  if (!option) throw new Error(`No option ${text}`)
  option.click()
}

let wrapper: VueWrapper | undefined

beforeEach(() => {
  i18n.global.locale.value = 'en'
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
})

describe('SettingsToggle', () => {
  it('shows its title and description and switches on click', async () => {
    wrapper = mount(SettingsToggle, { props: { title: 'Weekends', description: 'Show them', modelValue: false } })
    expect(wrapper.text()).toContain('Weekends')
    expect(wrapper.text()).toContain('Show them')
    expect(wrapper.attributes('aria-checked')).toBe('false')
    await wrapper.trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([[true]])
  })

  it('does nothing while disabled', async () => {
    wrapper = mount(SettingsToggle, { props: { title: 'Weekends', modelValue: true, disabled: true } })
    expect(wrapper.find('.text-xs').exists()).toBe(false) // no description line
    // A disabled button gets no clicks in a browser; the handler must not switch either.
    wrapper.vm.$el.dispatchEvent(new MouseEvent('click'))
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })
})

describe('AppSwitch', () => {
  it('turns on and off with its label as the name', async () => {
    wrapper = mount(AppSwitch, { props: { label: 'Busy', modelValue: false } })
    expect(wrapper.text()).toBe('Busy')
    await wrapper.trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([[true]])
    await wrapper.setProps({ modelValue: true })
    expect(wrapper.attributes('aria-checked')).toBe('true')
    await wrapper.trigger('click')
    expect(wrapper.emitted('update:modelValue')![1]).toEqual([false])
  })
})

describe('SegmentedControl', () => {
  it('marks the chosen option and picks another on click', async () => {
    wrapper = mount(SegmentedControl, {
      props: {
        label: 'Mode',
        modelValue: 'a',
        options: [
          { value: 'a', label: 'Simple' },
          { value: 'b', label: 'Advanced' },
        ],
      },
    })
    expect(wrapper.get('[role="radiogroup"]').attributes('aria-label')).toBe('Mode')
    const [simple, advanced] = wrapper.findAll('[role="radio"]')
    expect(simple!.attributes('aria-checked')).toBe('true')
    expect(advanced!.attributes('aria-checked')).toBe('false')
    await advanced!.trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([['b']])
  })
})

describe('RoleSelect', () => {
  it('offers all grantable roles and picks one', async () => {
    wrapper = mount(RoleSelect, { props: { modelValue: 'read' }, global: { plugins: [i18n] }, attachTo: document.body })
    expect(wrapper.text()).toBe('Read only')
    await wrapper.get('[role="combobox"]').trigger('click')
    expect(optionTexts()).toEqual(['Read only', 'Own events', 'All events', 'Manage'])
    clickOption('All events')
    expect(wrapper.emitted('update:modelValue')).toEqual([['full']])
  })

  it('leaves out managing for the public role', async () => {
    wrapper = mount(RoleSelect, {
      props: { modelValue: 'read', publicAccess: true, compact: true, label: 'Role' },
      global: { plugins: [i18n] },
      attachTo: document.body,
    })
    const field = wrapper.get('[role="combobox"]')
    expect(field.attributes('aria-label')).toBe('Role')
    await field.trigger('click')
    expect(optionTexts()).toEqual(['Read only', 'Own events', 'All events'])
  })
})

describe('ResourceIconPicker', () => {
  it('picks an icon, and no icon again', async () => {
    wrapper = mount(ResourceIconPicker, { props: { modelValue: '' }, global: { plugins: [i18n] } })
    const none = wrapper.get('button[aria-label="No icon"]')
    expect(none.attributes('aria-pressed')).toBe('true')
    const buttons = wrapper.findAll('button')
    expect(buttons.length).toBeGreaterThan(2)
    const icon = buttons[1]!
    await icon.trigger('click')
    const name = icon.attributes('aria-label')
    expect(wrapper.emitted('update:modelValue')).toEqual([[name]])

    await wrapper.setProps({ modelValue: name })
    expect(icon.attributes('aria-pressed')).toBe('true')
    expect(none.attributes('aria-pressed')).toBe('false')
    await none.trigger('click')
    expect(wrapper.emitted('update:modelValue')![1]).toEqual([''])
  })
})

describe('NumberListInput', () => {
  function render(modelValue: number[], allowLast = true) {
    wrapper = mount(NumberListInput, {
      props: {
        modelValue,
        min: 1,
        max: 31,
        allowLast,
        label: 'Days',
        'onUpdate:modelValue': (value: number[]) => wrapper!.setProps({ modelValue: value }),
      },
    })
    return wrapper.get('input')
  }

  it('shows the numbers sorted, with the last one as "+"', () => {
    const input = render([15, -1, 1])
    expect(input.element.value).toBe('1, 15, +')
    expect(input.attributes('aria-label')).toBe('Days')
  })

  it('takes valid input as typed and marks invalid input', async () => {
    const input = render([1])
    await input.setValue('3 2')
    expect(wrapper!.emitted('update:modelValue')).toEqual([[[2, 3]]])
    // The user's own typing stays as typed.
    expect(input.element.value).toBe('3 2')
    expect(input.attributes('aria-invalid')).toBe('false')

    await input.setValue('2, 40')
    expect(input.attributes('aria-invalid')).toBe('true')
    expect(wrapper!.emitted('update:modelValue')).toHaveLength(1)
  })

  it('drops invalid input when leaving the field', async () => {
    const input = render([5])
    await input.setValue('x')
    await input.trigger('blur')
    expect(input.element.value).toBe('5')
    expect(input.attributes('aria-invalid')).toBe('false')
  })

  it('shows new numbers set from outside', async () => {
    const input = render([5], false)
    await wrapper!.setProps({ modelValue: [7, 8] })
    expect(input.element.value).toBe('7, 8')
  })
})

describe('ColorPaletteSelect', () => {
  const options = [
    { id: 'sea', label: 'Sea', colors: ['#001122', '#003344'] },
    { id: 'sun', label: 'Sun', colors: ['#ffcc00'] },
  ]

  it('shows the chosen palette with its colors and picks another', async () => {
    wrapper = mount(ColorPaletteSelect, {
      props: { modelValue: 'sea', options, placeholder: 'Custom', label: 'Palette' },
      attachTo: document.body,
    })
    expect(wrapper.text()).toContain('Palette')
    expect(wrapper.text()).toContain('Sea')
    expect(wrapper.findAll('[role="combobox"] [style]')).toHaveLength(2)

    await wrapper.get('[role="combobox"]').trigger('click')
    expect(optionTexts()).toEqual(['Sea', 'Sun'])
    clickOption('Sun')
    expect(wrapper.emitted('update:modelValue')).toEqual([['sun']])
  })

  it('shows the placeholder while no palette matches', () => {
    wrapper = mount(ColorPaletteSelect, { props: { modelValue: null, options, placeholder: 'Custom' } })
    expect(wrapper.text()).toBe('Custom')
    expect(wrapper.findAll('[role="combobox"] [style]')).toHaveLength(0)
  })
})

describe('WeekLayoutFields', () => {
  function render(props: Record<string, unknown> = {}) {
    wrapper = mount(WeekLayoutFields, {
      props: { firstWeekday: 1, weekendDays: [0, 6], showWeekends: true, showWeekNumbers: false, ...props },
      global: { plugins: [i18n] },
      attachTo: document.body,
    })
    return wrapper
  }

  const dayButtons = () => wrapper!.findAll('button:not([role])')

  it('lists the weekdays from the first weekday on', async () => {
    render()
    expect(dayButtons().map((b) => b.text())).toEqual([
      'Monday',
      'Tuesday',
      'Wednesday',
      'Thursday',
      'Friday',
      'Saturday',
      'Sunday',
    ])
    await wrapper!.setProps({ firstWeekday: 0 })
    expect(dayButtons()[0]!.text()).toBe('Sunday')
  })

  it('changes the first weekday', async () => {
    render()
    await wrapper!.get('[role="combobox"]').trigger('click')
    clickOption('Sunday')
    expect(wrapper!.emitted('update:firstWeekday')).toEqual([[0]])
  })

  it('adds and removes weekend days, kept in order', async () => {
    render()
    await dayButtons()[4]!.trigger('click') // Friday
    expect(wrapper!.emitted('update:weekendDays')).toEqual([[[0, 5, 6]]])
    await dayButtons()[6]!.trigger('click') // Sunday
    expect(wrapper!.emitted('update:weekendDays')![1]).toEqual([[5, 6]])
  })

  it('switches weekends and week numbers', async () => {
    render()
    const [weekends, weekNumbers] = wrapper!.findAll('[role="switch"]')
    await weekends!.trigger('click')
    await weekNumbers!.trigger('click')
    expect(wrapper!.emitted('update:showWeekends')).toEqual([[false]])
    expect(wrapper!.emitted('update:showWeekNumbers')).toEqual([[true]])
  })

  it('disables everything when asked to', () => {
    render({ disabled: true })
    expect(wrapper!.findAll('button').every((b) => b.attributes('disabled') !== undefined)).toBe(true)
  })
})
