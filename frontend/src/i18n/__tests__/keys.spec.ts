import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { calendarColorPalettes, colorRoles } from '@/services/calendarColors'
import de from '../locales/de'
import en from '../locales/en'

type Messages = { [key: string]: string | Messages }

function keysOf(messages: Messages, prefix = ''): string[] {
  return Object.entries(messages).flatMap(([key, value]) =>
    typeof value === 'string' ? [prefix + key] : keysOf(value, `${prefix}${key}.`),
  )
}

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return name === '__tests__' || name === 'i18n' ? [] : sourceFiles(path)
    return /\.(vue|ts)$/.test(name) ? [path] : []
  })
}

describe('translations', () => {
  const english = new Set(keysOf(en))

  it('exist in both languages', () => {
    expect(new Set(keysOf(de))).toEqual(english)
  })

  it('cover every key the code refers to literally', () => {
    const sections = Object.keys(en).join('|')
    const pattern = new RegExp(`['"\`]((?:${sections})\\.[A-Za-z_.]+)['"\`]`, 'g')
    const missing = sourceFiles(join(__dirname, '../..')).flatMap((file) =>
      [...readFileSync(file, 'utf8').matchAll(pattern)]
        .map((match) => match[1]!)
        // Template expressions like "auth.isAdmin" share the quote style but aren't keys.
        .filter((key) => !english.has(key) && !/^(auth|notifications)\.(is|items)/.test(key))
        .map((key) => `${key} (${file})`),
    )
    expect(missing).toEqual([])
  })
  it('cover the keys the code builds from data', () => {
    const built = [
      ...colorRoles.map((role) => `colorRole.${role}`),
      ...calendarColorPalettes.map((palette) => `palette.${palette.id}`),
    ]
    expect(built.filter((key) => !english.has(key))).toEqual([])
  })
})
