import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import TabBar from '../TabBar.vue'

const tabs = [
  { id: 'one', label: 'One' },
  { id: 'two', label: 'Two' },
  { id: 'three', label: 'Three' },
]

describe('TabBar', () => {
  it('keeps only the active tab in the tab order', () => {
    const wrapper = mount(TabBar, { props: { tabs, active: 'two' } })
    expect(wrapper.findAll('[role="tab"]').map((tab) => tab.attributes('tabindex'))).toEqual(['-1', '0', '-1'])
  })

  it('moves between tabs with the arrow keys, Home and End', async () => {
    const wrapper = mount(TabBar, { props: { tabs, active: 'three' } })
    const list = wrapper.get('[role="tablist"]')
    await list.trigger('keydown', { key: 'ArrowRight' })
    await list.trigger('keydown', { key: 'ArrowLeft' })
    await list.trigger('keydown', { key: 'Home' })
    await list.trigger('keydown', { key: 'End' })
    expect(wrapper.emitted('select')).toEqual([['one'], ['two'], ['one'], ['three']])
  })
})
