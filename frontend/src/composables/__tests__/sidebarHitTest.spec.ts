import { describe, expect, it } from 'vitest'
import { findHit, type Dragged } from '../useSidebarDrag'

/**
 * jsdom has no layout, so the rows get fixed rectangles: 32 px high with 4 px between them,
 * a folder's entries 16 px further in; collapsed folders have no height.
 */
interface Spec {
  type: 'folder' | 'calendar'
  id: string
  collapsed?: boolean
  children?: Spec[]
}

const ROW = 32
const GAP = 4
const WIDTH = 240

function rect(left: number, top: number, width: number, height: number): DOMRect {
  return { left, top, width, height, right: left + width, bottom: top + height, x: left, y: top, toJSON: () => ({}) }
}

function build(root: Spec[]) {
  const container = document.createElement('div')
  const list = document.createElement('div')
  list.className = 'sidebar-list'
  container.append(list)
  const rects = new Map<Element, DOMRect>()
  let y = 8

  function place(specs: Spec[], parent: HTMLElement, left: number, hidden: boolean) {
    for (const spec of specs) {
      const el = document.createElement('div')
      el.className = 'sidebar-item'
      el.dataset.type = spec.type
      el.dataset.id = spec.id
      parent.append(el)
      const top = y
      const rowHeight = hidden ? 0 : ROW
      if (spec.type === 'folder') {
        const header = document.createElement('div')
        el.append(header)
        rects.set(header, rect(left, top, WIDTH - left, rowHeight))
        if (!hidden) y += ROW + GAP
        const children = document.createElement('div')
        children.dataset.folderId = spec.id
        el.append(children)
        const childrenTop = y
        place(spec.children ?? [], children, left + 16, hidden || !!spec.collapsed)
        rects.set(
          children,
          rect(left + 16, childrenTop, WIDTH - left - 16, hidden || spec.collapsed ? 0 : y - childrenTop),
        )
        rects.set(el, rect(left, top, WIDTH - left, hidden ? 0 : y - top - GAP))
      } else {
        rects.set(el, rect(left, top, WIDTH - left, rowHeight))
        if (!hidden) y += ROW + GAP
      }
    }
  }
  place(root, list, 8, false)
  rects.set(list, rect(8, 8, WIDTH, y - 8))
  rects.set(container, rect(0, 0, 260, 600))
  for (const [el, r] of rects) el.getBoundingClientRect = () => r
  const el = (id: string) => container.querySelector<HTMLElement>(`[data-id="${id}"]`)!
  const dragged = (id: string): Dragged => ({ type: el(id).dataset.type as Dragged['type'], id, el: el(id) })
  const header = (id: string) => (el(id).dataset.type === 'folder' ? (el(id).firstElementChild as HTMLElement) : el(id))
  /** The point `share` of the way down the row (header) of `id`. */
  const at = (id: string, share: number, x = 100) => {
    const r = header(id).getBoundingClientRect()
    return { x, y: r.top + r.height * share }
  }
  return { container, dragged, at, header }
}

// Rows from the top (y = 8): F1 (open: a, b, F3 (open: x)), F2 (closed: z), E (empty folder), c1, c2.
const tree: Spec[] = [
  {
    type: 'folder',
    id: 'F1',
    children: [
      { type: 'calendar', id: 'a' },
      { type: 'calendar', id: 'b' },
      { type: 'folder', id: 'F3', children: [{ type: 'calendar', id: 'x' }] },
    ],
  },
  { type: 'folder', id: 'F2', collapsed: true, children: [{ type: 'calendar', id: 'z' }] },
  { type: 'folder', id: 'E' },
  { type: 'calendar', id: 'c1' },
  { type: 'calendar', id: 'c2' },
]

const hit = (id: string, target: string, share: number, x?: number) => {
  const { container, dragged, at } = build(tree)
  return findHit(container, at(target, share, x), dragged(id))
}

describe('findHit', () => {
  it('sorts before or after a calendar row, by its upper and lower half', () => {
    expect(hit('c2', 'c1', 0.2)?.drop).toEqual({ type: 'calendar', id: 'c2', parentId: null, anchor: { before: 'c1' } })
    expect(hit('c1', 'c2', 0.8)?.drop).toEqual({ type: 'calendar', id: 'c1', parentId: null, anchor: { after: 'c2' } })
    expect(hit('c1', 'c2', 0.8)?.into).toBeNull()
  })

  it('places the line on the edge between rows, as wide as the list', () => {
    const above = hit('c2', 'c1', 0.2)!
    const { container, at } = build(tree)
    const row = container.querySelector<HTMLElement>('[data-id="c1"]')!.getBoundingClientRect()
    expect(above.line).toEqual({ x: row.left, y: row.top - 2, width: row.width })
    expect(at('c1', 0.5).y).toBeGreaterThan(row.top)
  })

  it('drops into a folder in the middle of its row, whatever is dragged', () => {
    for (const id of ['c1', 'F2']) {
      const result = hit(id, 'F1', 0.5)!
      expect(result.drop).toEqual({ type: id === 'c1' ? 'calendar' : 'folder', id, parentId: 'F1', anchor: 'end' })
      expect(result.into).toBe('F1')
      expect(result.line).toBeNull()
    }
    expect(hit('c1', 'E', 0.5)?.into).toBe('E')
  })

  it('sorts before or after a folder at the top and bottom edge, for calendars and folders alike', () => {
    expect(hit('c1', 'F2', 0.1)?.drop.anchor).toEqual({ before: 'F2' })
    expect(hit('c1', 'F2', 0.9)?.drop.anchor).toEqual({ after: 'F2' })
    expect(hit('E', 'F2', 0.9)?.drop.anchor).toEqual({ after: 'F2' })
    // The user's case: a calendar before the very first folder.
    expect(hit('c1', 'F1', 0.1)?.drop).toEqual({ type: 'calendar', id: 'c1', parentId: null, anchor: { before: 'F1' } })
  })

  it('goes first into an open folder with content when dropped on its bottom edge', () => {
    const result = hit('c1', 'F1', 0.9)!
    expect(result.drop).toEqual({ type: 'calendar', id: 'c1', parentId: 'F1', anchor: 'first' })
    // The line is indented to where the entries of the folder start.
    const { container } = build(tree)
    const header = (container.querySelector('[data-id="F1"]')!.firstElementChild as HTMLElement).getBoundingClientRect()
    expect(result.line).toEqual({ x: header.left + 16, y: header.bottom + 2, width: header.width - 16 })
  })

  it('treats the bottom edge of a closed or empty folder as "after it"', () => {
    expect(hit('c1', 'F2', 0.9)?.drop.anchor).toEqual({ after: 'F2' })
    expect(hit('c1', 'E', 0.9)?.drop.anchor).toEqual({ after: 'E' })
  })

  it('finds the parent folder of rows inside folders', () => {
    expect(hit('c1', 'b', 0.2)?.drop).toEqual({ type: 'calendar', id: 'c1', parentId: 'F1', anchor: { before: 'b' } })
    expect(hit('c1', 'x', 0.8)?.drop).toEqual({ type: 'calendar', id: 'c1', parentId: 'F3', anchor: { after: 'x' } })
    expect(hit('F2', 'x', 0.2)?.drop.parentId).toBe('F3')
  })

  it('skips rows inside a closed folder', () => {
    const { container, dragged } = build(tree)
    // Where z would be if F2 were open, the next visible row (E) is at the pointer.
    const f2 = container.querySelector<HTMLElement>('[data-id="F2"]')!.firstElementChild!.getBoundingClientRect()
    const result = findHit(container, { x: 100, y: f2.bottom + 10 }, dragged('c1'))
    expect(result?.drop.anchor).toEqual({ before: 'E' })
  })

  it('means "before the first row" above the first row', () => {
    const { container, dragged } = build(tree)
    expect(findHit(container, { x: 100, y: 3 }, dragged('c1'))?.drop.anchor).toEqual({ before: 'F1' })
  })

  it('means "the end of the root" below all rows', () => {
    const { container, dragged } = build(tree)
    const last = container.querySelector<HTMLElement>('[data-id="c2"]')!.getBoundingClientRect()
    const result = findHit(container, { x: 100, y: last.bottom + 80 }, dragged('F2'))!
    expect(result.drop).toEqual({ type: 'folder', id: 'F2', parentId: null, anchor: 'end' })
    expect(result.line?.y).toBeCloseTo(last.bottom + 2)
  })

  it('is no target on the dragged item itself, or on what is inside it', () => {
    const { container, dragged, at } = build(tree)
    expect(findHit(container, at('c1', 0.1), dragged('c1'))).toBeNull()
    expect(findHit(container, at('c1', 0.9), dragged('c1'))).toBeNull()
    // The gap just below the dragged row counts as the row.
    const c1 = container.querySelector<HTMLElement>('[data-id="c1"]')!.getBoundingClientRect()
    expect(findHit(container, { x: 100, y: c1.bottom + 1 }, dragged('c1'))).toBeNull()
    // A folder dragged over its own entries, even deep inside it.
    expect(findHit(container, at('a', 0.5), dragged('F1'))).toBeNull()
    expect(findHit(container, at('x', 0.5), dragged('F1'))).toBeNull()
    expect(findHit(container, at('F3', 0.5), dragged('F1'))).toBeNull()
  })

  it('is no target outside the list', () => {
    const { container, dragged, at } = build(tree)
    expect(findHit(container, at('c1', 0.5, 300), dragged('c2'))).toBeNull()
    expect(findHit(container, { x: 100, y: 700 }, dragged('c2'))).toBeNull()
  })

  it('never drops a calendar anywhere but between or into rows', () => {
    // Every pointer position in the list gives a valid target, or none (on the dragged row itself).
    const { container, dragged } = build(tree)
    const ids = new Set(['F1', 'a', 'b', 'F3', 'x', 'F2', 'E', 'c1', 'c2'])
    for (let y = 1; y < 400; y += 3) {
      const result = findHit(container, { x: 100, y }, dragged('c1'))
      if (!result) continue
      expect(result.drop.parentId === null || ids.has(result.drop.parentId)).toBe(true)
      const anchor = result.drop.anchor
      if (typeof anchor === 'object') expect(ids.has('before' in anchor ? anchor.before : anchor.after)).toBe(true)
    }
  })
})
