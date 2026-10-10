// Color helpers for hex colors in the form #rrggbb.

type Rgb = [number, number, number]

function channels(color: string): Rgb {
  const value = color.replace('#', '')
  return [
    Number.parseInt(value.slice(0, 2), 16),
    Number.parseInt(value.slice(2, 4), 16),
    Number.parseInt(value.slice(4, 6), 16),
  ]
}

function toHex(rgb: number[]): string {
  return `#${rgb.map((channel) => Math.round(channel).toString(16).padStart(2, '0')).join('')}`
}

function toHsl(color: string): Rgb {
  const [red, green, blue] = channels(color).map((channel) => channel / 255) as Rgb
  const max = Math.max(red, green, blue)
  const min = Math.min(red, green, blue)
  const lightness = (max + min) / 2
  if (max === min) return [0, 0, lightness]
  const delta = max - min
  const saturation = lightness > 0.5 ? delta / (2 - max - min) : delta / (max + min)
  const hue =
    max === red
      ? (green - blue) / delta + (green < blue ? 6 : 0)
      : max === green
        ? (blue - red) / delta + 2
        : (red - green) / delta + 4
  return [hue * 60, saturation, lightness]
}

function fromHsl(hue: number, saturation: number, lightness: number): string {
  const amount = saturation * Math.min(lightness, 1 - lightness)
  const channel = (n: number) => {
    const k = (n + hue / 30) % 12
    return (lightness - amount * Math.max(-1, Math.min(k - 3, 9 - k, 1))) * 255
  }
  return toHex([channel(0), channel(8), channel(4)])
}

function relativeLuminance(color: string): number {
  const [red, green, blue] = channels(color).map((channel) => {
    const value = channel / 255
    return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
  }) as Rgb
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue
}

/** Dark or white text, whichever reads better on `color`. */
export function contrastColor(color: string): string {
  const [red, green, blue] = channels(color)
  return (red * 299 + green * 587 + blue * 114) / 1000 > 150 ? '#111827' : '#ffffff'
}

/**
 * Darkens a color while keeping its hue, adding saturation so pastel palette colors stay vivid.
 * Saturation is capped so already saturated hues (indigo, lavender, purple) don't turn garish.
 */
export function shadeColor(
  color: string,
  lightnessFactor: number,
  saturationBoost = 0.15,
  maxSaturation = 0.65,
): string {
  const [hue, saturation, lightness] = toHsl(color)
  return fromHsl(hue, Math.min(maxSaturation, saturation + saturationBoost), lightness * lightnessFactor)
}

/** Keeps darkening until white text reaches WCAG AA contrast (4.5:1); green and yellow hues need more. */
export function darkenForWhiteText(color: string): string {
  let result = color
  for (let step = 0; step < 20 && 1.05 / (relativeLuminance(result) + 0.05) < 4.5; step++) {
    const [hue, saturation, lightness] = toHsl(result)
    result = fromHsl(hue, saturation, lightness * 0.93)
  }
  return result
}

/** Moves `color` towards black or white by `amount` (0–1). */
export function mixColor(color: string, target: '#000000' | '#ffffff', amount: number): string {
  const destination = channels(target)
  return toHex(channels(color).map((channel, index) => channel + (destination[index]! - channel) * amount))
}
