import { describe, expect, it } from 'vitest'
import { RESOURCE_ICON_NAMES, resourceIcon, resourceIconSvg } from '../resourceIcons'

describe('resource icons', () => {
  it('has only valid names, as the server checks them', () => {
    expect(RESOURCE_ICON_NAMES.length).toBeGreaterThan(40)
    for (const name of RESOURCE_ICON_NAMES) expect(name).toMatch(/^[a-z0-9]+(-[a-z0-9]+)*$/)
  })

  it('knows no icon for nothing or an unknown name', () => {
    expect(resourceIcon(null)).toBeUndefined()
    expect(resourceIcon('')).toBeUndefined()
    expect(resourceIcon('no-such-icon')).toBeUndefined()
    expect(resourceIcon('door-open')).toBeDefined()
    expect(resourceIconSvg('no-such-icon')).toBe('')
    expect(resourceIconSvg('')).toBe('')
    // Names of the object's prototype, which the server's name check lets through.
    expect(resourceIcon('constructor')).toBeUndefined()
    expect(resourceIconSvg('constructor')).toBe('')
  })

  it('renders an svg of the asked size, the same every time', () => {
    const svg = resourceIconSvg('projector', 14)
    expect(svg).toMatch(/^<svg[^>]*width="14"[^>]*height="14"/)
    expect(svg).toContain('aria-hidden="true"')
    expect(resourceIconSvg('projector', 14)).toBe(svg)
    expect(resourceIconSvg('projector', 20)).toContain('width="20"')
  })
})
