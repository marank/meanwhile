import { describe, expect, it } from 'vitest'
import type { SearchResult } from '@/api'
import { optionMark } from '../optionMark'

const option = (type: string, meta: Record<string, unknown> | null): SearchResult => ({
  id: '1',
  type,
  label: 'x',
  subtitle: null,
  meta,
})

describe('optionMark', () => {
  it('shows a category by its color', () => {
    expect(optionMark(option('category', { color: '#ff0000' }))).toEqual({ kind: 'color', color: '#ff0000' })
  })

  it('shows a resource by its icon, if it has one this client knows', () => {
    expect(optionMark(option('resource', { icon: 'projector', color: '#f59e0b' }))).toEqual({
      kind: 'icon',
      icon: 'projector',
    })
    expect(optionMark(option('resource', { icon: '' }))).toBeNull()
    expect(optionMark(option('resource', { icon: 'from-a-newer-server' }))).toBeNull()
  })

  it('shows nothing for the rest', () => {
    expect(optionMark(option('user', null))).toBeNull()
    expect(optionMark(option('category', null))).toBeNull()
    expect(optionMark(option('group', { color: '#fff000' }))).toBeNull()
  })
})
