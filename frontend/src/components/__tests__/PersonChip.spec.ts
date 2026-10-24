import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { i18n } from '@/i18n'
import PersonChip from '../PersonChip.vue'

const render = (props: Record<string, unknown>) =>
  mount(PersonChip, { props: { name: 'alice', email: 'alice@example.com', ...props }, global: { plugins: [i18n] } })

beforeEach(() => {
  i18n.global.locale.value = 'en'
})

describe('PersonChip', () => {
  it('shows the name with its initial and the address as a tooltip', () => {
    const wrapper = render({})
    expect(wrapper.findAll('span').map((span) => span.text())).toEqual(['A', 'alice'])
    expect(wrapper.attributes('title')).toBe('alice@example.com')
    expect(wrapper.find('button').exists()).toBe(false)
  })

  it("takes the initial from the address when there's no name", () => {
    expect(render({ name: '' }).get('span').text()).toBe('A')
  })

  it('asks to be removed when its button is clicked', async () => {
    const wrapper = render({ removable: true })
    await wrapper.get('button[aria-label="Delete"]').trigger('click')
    expect(wrapper.emitted('remove')).toHaveLength(1)
  })

  it('disables the remove button when disabled', () => {
    expect(render({ removable: true, disabled: true }).get('button').attributes('disabled')).toBeDefined()
  })
})
