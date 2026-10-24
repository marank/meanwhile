import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import type { SearchResult } from '@/api'
import OptionMark from '../OptionMark.vue'

const option = (overrides: Partial<SearchResult>) =>
  ({ id: 'x', type: 'user', label: 'X', meta: {}, ...overrides }) as SearchResult

describe('OptionMark', () => {
  it("shows a category's colour as a small square", () => {
    const wrapper = mount(OptionMark, { props: { option: option({ type: 'category', meta: { color: '#ff0000' } }) } })
    expect(wrapper.get('span').attributes('style')).toContain('background-color: rgb(255, 0, 0)')
  })

  it("shows a resource's icon", () => {
    const wrapper = mount(OptionMark, { props: { option: option({ type: 'resource', meta: { icon: 'door-open' } }) } })
    expect(wrapper.get('svg').classes().join(' ')).toContain('door-open')
  })

  it('shows nothing for other options', () => {
    const wrapper = mount(OptionMark, { props: { option: option({ type: 'user' }) } })
    expect(wrapper.find('span').exists()).toBe(false)
    expect(wrapper.find('svg').exists()).toBe(false)
  })
})
