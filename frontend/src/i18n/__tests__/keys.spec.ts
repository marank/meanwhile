import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { calendarColorPalettes, colorRoles } from '@/services/calendarColors'
import de from '../locales/de'
import deInformal, { changes as informal } from '../locales/de-informal'
import en from '../locales/en'

type Messages = { [key: string]: string | Messages }

function keysOf(messages: Messages, prefix = ''): string[] {
  return Object.entries(messages).flatMap(([key, value]) =>
    typeof value === 'string' ? [prefix + key] : keysOf(value, `${prefix}${key}.`),
  )
}

function textsOf(messages: Messages, prefix = ''): Array<[string, string]> {
  return Object.entries(messages).flatMap(([key, value]): Array<[string, string]> =>
    typeof value === 'string' ? [[prefix + key, value]] : textsOf(value, `${prefix}${key}.`),
  )
}

// How the formal German addresses the reader; the informal one says "du" instead.
const FORMAL = /\b(Sie|Ihnen|Ihre?[mnrs]?)\b/
// Where "Sie" starts a sentence about something else ("she", "they"), not the reader.
const NOT_THE_READER = new Set(['rsvp.notFound'])

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

  it('exist in the informal German, which changes only keys the others have', () => {
    expect(new Set(keysOf(deInformal))).toEqual(english)
    expect(keysOf(informal).filter((key) => !english.has(key))).toEqual([])
  })

  it('say du in the informal German wherever the formal one says Sie', () => {
    const changed = new Set(keysOf(informal))
    const formal = textsOf(de).filter(([key, text]) => FORMAL.test(text) && !NOT_THE_READER.has(key))
    expect(formal.map(([key]) => key).filter((key) => !changed.has(key))).toEqual([])
    expect(textsOf(informal).filter(([, text]) => FORMAL.test(text))).toEqual([])
  })

  it('cover every key the code refers to literally', () => {
    const sections = Object.keys(en).join('|')
    const pattern = new RegExp(`['"\`]((?:${sections})\\.[A-Za-z_.]+)['"\`]`, 'g')
    const missing = sourceFiles(join(__dirname, '../..')).flatMap((file) =>
      [...readFileSync(file, 'utf8').matchAll(pattern)]
        .map((match) => match[1]!)
        // Template expressions like "auth.isAdmin" share the quote style but aren't keys, nor are
        // live update message types like "notifications.changed".
        .filter((key) => !english.has(key) && !/^(auth|notifications)\.(is|items|changed$)/.test(key))
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
