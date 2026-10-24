import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ResourceIcon from '../ResourceIcon.vue'

describe('ResourceIcon', () => {
  it('draws the named icon at the given size', () => {
    const svg = mount(ResourceIcon, { props: { name: 'door-open', size: 24 } }).get('svg')
    expect(svg.classes().join(' ')).toContain('door-open')
    expect(svg.attributes('width')).toBe('24')
    expect(svg.attributes('aria-hidden')).toBe('true')
  })

  it('draws nothing for an unknown or missing name', () => {
    expect(
      mount(ResourceIcon, { props: { name: 'constructor' } })
        .find('svg')
        .exists(),
    ).toBe(false)
    expect(mount(ResourceIcon).find('svg').exists()).toBe(false)
  })
})
