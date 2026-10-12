import { describe, expect, it } from 'vitest'
import { canDropInto, compareSiblings, planMove, siblingIds, type SidebarTree } from '../sidebarDrag'

const node = (id: string, parentId: string | null, position: number) => ({ id, parentId, position, name: id })

// Under the root: folders F1 (0) and F2 (1), calendars c1 (2) and c2 (3).
// F1 holds calendars a (0) and b (1) and the folder F3 (2).
const tree: SidebarTree = {
  folders: [node('F1', null, 0), node('F2', null, 1), node('F3', 'F1', 2)],
  calendars: [node('c1', null, 2), node('c2', null, 3), node('a', 'F1', 0), node('b', 'F1', 1)],
}

const summary = (updates: ReturnType<typeof planMove>) =>
  updates.map((u) => `${u.type[0]}:${u.id}@${u.parent_id}:${u.position}`)

describe('siblingIds', () => {
  it('lists folders and calendars together in display order', () => {
    expect(siblingIds(tree, null)).toEqual(['F1', 'F2', 'c1', 'c2'])
    expect(siblingIds(tree, 'F1')).toEqual(['a', 'b', 'F3'])
    expect(siblingIds(tree, 'F1', 'a')).toEqual(['b', 'F3'])
  })

  it('puts folders first at the same position, then orders by name', () => {
    const same: SidebarTree = {
      folders: [node('f', null, 0)],
      calendars: [node('b', null, 0), node('a', null, 0)],
    }
    expect(siblingIds(same, null)).toEqual(['f', 'a', 'b'])
    expect(
      compareSiblings({ position: 0, type: 'calendar', name: 'a' }, { position: 0, type: 'folder', name: 'z' }),
    ).toBeGreaterThan(0)
  })
})

describe('planMove', () => {
  it('puts a calendar before the first folder', () => {
    expect(summary(planMove(tree, 'calendar', 'c1', null, { before: 'F1' }))).toEqual([
      'c:c1@null:0',
      'f:F1@null:1',
      'f:F2@null:2',
      'c:c2@null:3',
    ])
  })

  it('puts a folder after a calendar', () => {
    expect(summary(planMove(tree, 'folder', 'F1', null, { after: 'c2' }))).toEqual([
      'f:F2@null:0',
      'c:c1@null:1',
      'c:c2@null:2',
      'f:F1@null:3',
    ])
  })

  it('moves an item into a folder, last or first', () => {
    expect(summary(planMove(tree, 'calendar', 'c1', 'F1', 'end'))).toEqual([
      'c:a@F1:0',
      'c:b@F1:1',
      'f:F3@F1:2',
      'c:c1@F1:3',
    ])
    expect(summary(planMove(tree, 'calendar', 'c1', 'F1', 'first'))).toEqual([
      'c:c1@F1:0',
      'c:a@F1:1',
      'c:b@F1:2',
      'f:F3@F1:3',
    ])
  })

  it('moves an item between two siblings of another list', () => {
    expect(summary(planMove(tree, 'calendar', 'c1', 'F1', { before: 'b' }))).toEqual([
      'c:a@F1:0',
      'c:c1@F1:1',
      'c:b@F1:2',
      'f:F3@F1:3',
    ])
    expect(summary(planMove(tree, 'folder', 'F2', 'F1', { before: 'a' }))).toEqual([
      'f:F2@F1:0',
      'c:a@F1:1',
      'c:b@F1:2',
      'f:F3@F1:3',
    ])
  })

  it('moves a folder out to the root, and onto the end', () => {
    expect(summary(planMove(tree, 'folder', 'F3', null, 'end'))).toEqual([
      'f:F1@null:0',
      'f:F2@null:1',
      'c:c1@null:2',
      'c:c2@null:3',
      'f:F3@null:4',
    ])
  })

  it('does nothing when the item would stay where it is', () => {
    expect(planMove(tree, 'calendar', 'c1', null, { before: 'c2' })).toEqual([])
    expect(planMove(tree, 'calendar', 'c2', null, { after: 'c1' })).toEqual([])
    expect(planMove(tree, 'calendar', 'c2', null, 'end')).toEqual([])
    expect(planMove(tree, 'calendar', 'a', 'F1', 'first')).toEqual([])
    expect(planMove(tree, 'folder', 'F1', null, 'first')).toEqual([])
    expect(planMove(tree, 'folder', 'F2', null, { after: 'F1' })).toEqual([])
  })

  it('puts an unknown anchor at the end', () => {
    expect(summary(planMove(tree, 'calendar', 'c1', 'F1', { after: 'gone' }))).toEqual([
      'c:a@F1:0',
      'c:b@F1:1',
      'f:F3@F1:2',
      'c:c1@F1:3',
    ])
  })

  it('does nothing for an item that is gone', () => {
    expect(planMove(tree, 'calendar', 'deleted', null, 'end')).toEqual([])
    expect(planMove(tree, 'folder', 'deleted', 'F1', 'first')).toEqual([])
  })

  it('refuses to put a folder into itself or its own subfolders', () => {
    expect(planMove(tree, 'folder', 'F1', 'F1', 'end')).toEqual([])
    expect(planMove(tree, 'folder', 'F1', 'F3', 'end')).toEqual([])
    expect(canDropInto(tree, 'folder', 'F1', 'F3')).toBe(false)
    expect(canDropInto(tree, 'folder', 'F3', 'F2')).toBe(true)
    expect(canDropInto(tree, 'calendar', 'a', 'F3')).toBe(true)
  })
})
