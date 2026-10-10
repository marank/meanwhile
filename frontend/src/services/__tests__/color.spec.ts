import { describe, expect, it } from 'vitest'
import { contrastColor, darkenForWhiteText, mixColor, shadeColor } from '../color'

function luminance(color: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const value = Number.parseInt(color.slice(i, i + 2), 16) / 255
    return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
  }) as [number, number, number]
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

describe('color helpers', () => {
  it('picks readable text colors', () => {
    expect(contrastColor('#ffffff')).toBe('#111827')
    expect(contrastColor('#000000')).toBe('#ffffff')
  })

  it('mixes towards black and white', () => {
    expect(mixColor('#808080', '#000000', 1)).toBe('#000000')
    expect(mixColor('#808080', '#ffffff', 0)).toBe('#808080')
    expect(mixColor('#000000', '#ffffff', 0.5)).toBe('#808080')
  })

  it('shades without changing gray into a color', () => {
    expect(shadeColor('#808080', 0.5, 0, 0)).toBe('#404040')
  })

  it('darkens until white text reaches 4.5:1 contrast', () => {
    for (const color of ['#cae7cd', '#ece4c5', '#cbe0fe']) {
      const result = darkenForWhiteText(color)
      expect(1.05 / (luminance(result) + 0.05)).toBeGreaterThanOrEqual(4.5)
    }
  })
})
