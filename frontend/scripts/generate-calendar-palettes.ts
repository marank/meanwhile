/**
 * Generates src/services/calendarPalettes.ts from the hand-picked colors below.
 * Each preset is defined by its day, today and weekend colors; event and border colors are derived here once,
 * so the app only reads finished values.
 *
 * Run with: pnpm generate:palettes
 */
import { writeFileSync } from 'node:fs'
import { darkenForWhiteText, mixColor, shadeColor } from '../src/services/color.ts'

/** Day, today and weekend colors; event and border colors are derived unless given explicitly. */
type Source = {
  base: string
  today: string
  weekend: string
  event?: string
  border?: string
  outerBorder?: string
}

const sources: Array<{ id: string; light: Source; dark: Source }> = [
  // Matches the app's own neutral surfaces and blue accent; the default for "All calendars".
  {
    id: 'app',
    light: {
      base: '#f6f6f7',
      weekend: '#ededef',
      today: '#dce6fa',
      event: '#2261dd',
      border: '#d4d4d8',
      outerBorder: '#a1a1aa',
    },
    dark: {
      base: '#18181b',
      weekend: '#202024',
      today: '#1c2a47',
      event: '#2261dd',
      border: '#3f3f46',
      outerBorder: '#52525b',
    },
  },
  {
    id: 'blue',
    light: { base: '#cbe0fe', today: '#80b3fe', weekend: '#bed1ed' },
    dark: { base: '#15253d', today: '#2b528b', weekend: '#22334c' },
  },
  {
    id: 'sky',
    light: { base: '#c2e4f8', today: '#53bdf5', weekend: '#b7d4e7' },
    dark: { base: '#0b2838', today: '#025a7e', weekend: '#1a3647' },
  },
  {
    id: 'cyan',
    light: { base: '#c0e6ec', today: '#44c5d6', weekend: '#b5d6dc' },
    dark: { base: '#072b2f', today: '#005e68', weekend: '#17393d' },
  },
  {
    id: 'teal',
    light: { base: '#c3e7e1', today: '#55c7ba', weekend: '#b8d7d2' },
    dark: { base: '#0b2b28', today: '#036058', weekend: '#1a3935' },
  },
  {
    id: 'emerald',
    light: { base: '#c6e7d5', today: '#61c99a', weekend: '#bad8c8' },
    dark: { base: '#0f2c1f', today: '#126143', weekend: '#1d3a2c' },
  },
  {
    id: 'green',
    light: { base: '#cae7cd', today: '#71c880', weekend: '#bdd8c0' },
    dark: { base: '#142b18', today: '#246131', weekend: '#213a25' },
  },
  {
    id: 'sage',
    light: { base: '#d4e2d6', today: '#95bd9c', weekend: '#c7d3c8' },
    dark: { base: '#1d281f', today: '#405a45', weekend: '#2b362d' },
  },
  {
    id: 'lime',
    light: { base: '#d7e4c4', today: '#9fbf62', weekend: '#c9d4b8' },
    dark: { base: '#20290f', today: '#475b19', weekend: '#2e371d' },
  },
  {
    id: 'olive',
    light: { base: '#dfe0cd', today: '#b3b582', weekend: '#d0d1c0' },
    dark: { base: '#26261c', today: '#54553b', weekend: '#333429' },
  },
  {
    id: 'yellow',
    light: { base: '#ece4c5', today: '#d4bc5c', weekend: '#ddd5ba' },
    dark: { base: '#2a2513', today: '#5e5223', weekend: '#383320' },
  },
  {
    id: 'amber',
    light: { base: '#edd9bb', today: '#d9a346', weekend: '#dccbb0' },
    dark: { base: '#2e2312', today: '#684d20', weekend: '#3c311f' },
  },
  {
    id: 'orange',
    light: { base: '#f9d6bf', today: '#f49752', weekend: '#e8c8b4' },
    dark: { base: '#381e0b', today: '#7d4007', weekend: '#462c19' },
  },
  {
    id: 'terracotta',
    light: { base: '#f3d7cc', today: '#e69c80', weekend: '#e2c9c0' },
    dark: { base: '#341f18', today: '#744431', weekend: '#422d25' },
  },
  {
    id: 'coral',
    light: { base: '#fcd3cc', today: '#fa8f7e', weekend: '#eac6bf' },
    dark: { base: '#391c17', today: '#813a30', weekend: '#482924' },
  },
  {
    id: 'red',
    light: { base: '#fed2cd', today: '#fe8b83', weekend: '#ecc5c1' },
    dark: { base: '#3a1b19', today: '#833734', weekend: '#492826' },
  },
  {
    id: 'rose',
    light: { base: '#fdd1d6', today: '#fc899d', weekend: '#ebc4c9' },
    dark: { base: '#3a1a20', today: '#813645', weekend: '#49282d' },
  },
  {
    id: 'pink',
    light: { base: '#fad1e0', today: '#f589b6', weekend: '#e9c4d1' },
    dark: { base: '#381a26', today: '#7e3655', weekend: '#472834' },
  },
  {
    id: 'fuchsia',
    light: { base: '#f2d3ee', today: '#e38fdb', weekend: '#e1c5de' },
    dark: { base: '#331c31', today: '#723b6e', weekend: '#41293f' },
  },
  {
    id: 'plum',
    light: { base: '#ead6f0', today: '#cf9adf', weekend: '#dac8df' },
    dark: { base: '#2d1f32', today: '#664370', weekend: '#3b2c40' },
  },
  {
    id: 'purple',
    light: { base: '#e3d7fb', today: '#bf9bfc', weekend: '#d3c9e9' },
    dark: { base: '#291f3a', today: '#5c4383', weekend: '#372d49' },
  },
  {
    id: 'lavender',
    light: { base: '#dbdbf8', today: '#aaa7f6', weekend: '#cccde7' },
    dark: { base: '#232238', today: '#4e4b7f', weekend: '#313047' },
  },
  {
    id: 'indigo',
    light: { base: '#d2ddff', today: '#96acff', weekend: '#c5ceee' },
    dark: { base: '#1d233d', today: '#3f4d8c', weekend: '#2a314c' },
  },
  {
    id: 'mocha',
    light: { base: '#e8dbd1', today: '#cca98e', weekend: '#d9cdc4' },
    dark: { base: '#2b241e', today: '#604f41', weekend: '#39312b' },
  },
  {
    id: 'stone',
    light: { base: '#e2ddd6', today: '#bcaf9c', weekend: '#d3cfc8' },
    dark: { base: '#272521', today: '#585248', weekend: '#35322e' },
  },
  {
    id: 'slate',
    light: { base: '#d6dfea', today: '#9db3d0', weekend: '#c9d0da' },
    dark: { base: '#20262e', today: '#455467', weekend: '#2d333c' },
  },
  {
    id: 'graphite',
    light: { base: '#dcdee3', today: '#abb1be', weekend: '#cdcfd4' },
    dark: { base: '#232529', today: '#4e535b', weekend: '#313337' },
  },
  // Bolder presets: today and events use a second, contrasting hue.
  {
    id: 'midnight',
    light: { base: '#dfe3f0', today: '#f2c94c', weekend: '#d0d6e8', event: '#1f2a5a' },
    dark: { base: '#0d1226', today: '#5c4a12', weekend: '#141a33', event: '#e0b43a' },
  },
  {
    id: 'sunset',
    light: { base: '#fde4d6', today: '#f59ab3', weekend: '#f6d2c8', event: '#c2410c' },
    dark: { base: '#2a1612', today: '#5e2038', weekend: '#331b18', event: '#e0703a' },
  },
  {
    id: 'aurora',
    light: { base: '#d9f2ec', today: '#c4b5fd', weekend: '#cfe6ea', event: '#0f766e' },
    dark: { base: '#0b2420', today: '#3b2a6e', weekend: '#10282f', event: '#34d399' },
  },
  {
    id: 'cherry',
    light: { base: '#fbe3ea', today: '#f8a5c2', weekend: '#f3d6df', event: '#9d174d' },
    dark: { base: '#2b141c', today: '#6d2440', weekend: '#331a23', event: '#f472b6' },
  },
  {
    id: 'desert',
    light: { base: '#f3e6cf', today: '#e9a23b', weekend: '#ead8bb', event: '#8a4b14' },
    dark: { base: '#2a2116', today: '#6a4a14', weekend: '#31271a', event: '#d9963a' },
  },
  {
    id: 'deepSea',
    light: { base: '#d6eef5', today: '#5ec8d8', weekend: '#c8e2ec', event: '#0c4a6e' },
    dark: { base: '#061a24', today: '#0e4a5c', weekend: '#0a2230', event: '#38bdf8' },
  },
  {
    id: 'forest',
    light: { base: '#dde8d5', today: '#a3c585', weekend: '#d0dcc6', event: '#2f5d2b' },
    dark: { base: '#121c10', today: '#2f4a24', weekend: '#172315', event: '#6aa84f' },
  },
  {
    id: 'neon',
    light: { base: '#f4f0ff', today: '#c6ff6b', weekend: '#ebe5ff', event: '#7c3aed' },
    dark: { base: '#0f0a1f', today: '#3d5c00', weekend: '#160f2b', event: '#a855f7' },
  },
  {
    id: 'retro',
    light: { base: '#f6efd9', today: '#e07a5f', weekend: '#eee4c7', event: '#3d405b' },
    dark: { base: '#22201a', today: '#6b3a2c', weekend: '#29261e', event: '#81b29a' },
  },
  {
    id: 'monochrome',
    light: { base: '#f2f2f2', today: '#c9c9c9', weekend: '#e6e6e6', event: '#333333' },
    dark: { base: '#141414', today: '#3a3a3a', weekend: '#1c1c1c', event: '#d4d4d4' },
  },
]

function derive(source: Source, dark: boolean) {
  return {
    base: source.base,
    weekend: source.weekend,
    today: source.today,
    // Events need to stand out from the day background: deeper with white text in light mode,
    // lifted in dark mode where the day colors are near black.
    event:
      source.event ??
      (dark ? shadeColor(source.base, 2.6, 0.2, 0.8) : darkenForWhiteText(shadeColor(source.base, 0.6, 0.15, 0.6))),
    border: source.border ?? mixColor(source.base, dark ? '#ffffff' : '#000000', dark ? 0.14 : 0.16),
    outerBorder: source.outerBorder ?? shadeColor(source.base, dark ? 0.7 : 0.36, dark ? 0.35 : 0.2),
  }
}

function format(colors: ReturnType<typeof derive>): string {
  return `{ ${Object.entries(colors)
    .map(([role, color]) => `${role}: '${color}'`)
    .join(', ')} }`
}

const entries = sources
  .map(
    (source) =>
      `  {\n    id: '${source.id}',\n    light: ${format(derive(source.light, false))},\n    dark: ${format(derive(source.dark, true))},\n  },`,
  )
  .join('\n')

const output = `// Generated by scripts/generate-calendar-palettes.ts – edit the sources there and regenerate.
import type { CalendarColorPalette } from './calendarColors'

export const calendarColorPalettes: CalendarColorPalette[] = [
${entries}
]
`

writeFileSync(new URL('../src/services/calendarPalettes.ts', import.meta.url), output)
console.log(`Wrote ${sources.length} palettes.`)
