import { onBeforeUnmount, onMounted, type Ref } from 'vue'
import { collapsedFolders, draggingId, dropIndicator, dropTargetFolderId } from '@/services/sidebarState'
import type { DropAnchor, NodeType } from '@/services/sidebarDrag'

/**
 * Drag and drop for the sidebar tree, built on pointer events.
 *
 * Nothing moves while dragging (the rows stay where they are, so the target under the pointer
 * stays put): a ghost follows the pointer, and the target is shown as a line between rows or an
 * outline around a folder. The move happens on release, from the data, not from the DOM.
 *
 *  - Over a folder row, the top and bottom quarter sort before or after it, the middle drops into it.
 *  - Over a calendar row, the upper and lower half sort before and after it.
 *  - Above the first row (including over "All calendars") means before the first row.
 *  Folders and calendars share one list per folder, so either can go before or after the other.
 */

export interface SidebarDrop {
  type: NodeType
  id: string
  parentId: string | null
  anchor: DropAnchor
}

/** Pixels the pointer moves before a mouse press turns into a drag. */
const DRAG_THRESHOLD = 5
/** Touch drags start after holding still for this long, so that scrolling the list keeps working. */
const LONG_PRESS_MS = 350
/** A dragged item resting on a closed folder opens it after this long. */
const OPEN_AFTER_MS = 700
/** Share of a folder row, from each edge, that sorts; the middle drops into it. */
const EDGE_SHARE = 0.25
/** The list scrolls while the pointer is this close to its top or bottom edge. */
const SCROLL_ZONE = 32
const SCROLL_STEP = 10
/** Space between two rows, which belongs to the row above it. */
const ROW_GAP = 2

export type DropZone = 'before' | 'into' | 'after'

/** Which part of a folder row (top to bottom) the pointer is on. */
export function dropZone(top: number, bottom: number, y: number): DropZone {
  const edge = (bottom - top) * EDGE_SHARE
  if (y < top + edge) return 'before'
  if (y > bottom - edge) return 'after'
  return 'into'
}

interface Row {
  el: HTMLElement
  type: NodeType
  id: string
  /** The row itself: for a folder its header, without the folders and calendars below it. */
  rect: DOMRect
}

export interface Dragged {
  type: NodeType
  id: string
  el: HTMLElement
}

export interface Hit {
  drop: SidebarDrop
  /** The folder to outline, if the item goes into it. */
  into: string | null
  /** Viewport position of the line between rows, if the item goes between them. */
  line: { x: number; y: number; width: number } | null
}

function typeOf(el: HTMLElement): NodeType | null {
  return el.dataset.type === 'folder' || el.dataset.type === 'calendar' ? el.dataset.type : null
}

function parentOf(el: HTMLElement): string | null {
  return (el.parentElement as HTMLElement | null)?.dataset.folderId ?? null
}

/** The rows on screen, top to bottom, without the dragged item and what is inside it. */
function visibleRows(container: HTMLElement, dragged: Dragged): Row[] {
  const rows: Row[] = []
  for (const el of container.querySelectorAll<HTMLElement>('.sidebar-item[data-type]')) {
    const type = typeOf(el)
    if (!type || !el.dataset.id || dragged.el.contains(el)) continue
    const header = type === 'folder' ? (el.firstElementChild as HTMLElement) : el
    const rect = header.getBoundingClientRect()
    if (rect.height > 0) rows.push({ el, type, id: el.dataset.id, rect })
  }
  return rows
}

function listOf(container: HTMLElement, parentId: string | null): HTMLElement | null {
  if (!parentId) return container.querySelector<HTMLElement>('.sidebar-list:not([data-folder-id])')
  return (
    [...container.querySelectorAll<HTMLElement>('[data-folder-id]')].find((el) => el.dataset.folderId === parentId) ??
    null
  )
}

/** At the end of everything under the parent; the line goes below the last entry. */
function endOfSiblings(container: HTMLElement, parentId: string | null, dragged: Dragged): Hit | null {
  const list = listOf(container, parentId)
  if (!list) return null
  const rect = list.getBoundingClientRect()
  const last = [...list.querySelectorAll<HTMLElement>(':scope > .sidebar-item')]
    .filter((el) => el !== dragged.el)
    .at(-1)
  const y = last ? last.getBoundingClientRect().bottom + 2 : rect.top
  return {
    drop: { type: dragged.type, id: dragged.id, parentId, anchor: 'end' },
    into: null,
    line: { x: rect.left, y, width: rect.width },
  }
}

export function findHit(container: HTMLElement, point: { x: number; y: number }, dragged: Dragged): Hit | null {
  const box = container.getBoundingClientRect()
  if (point.x < box.left || point.x > box.right || point.y < box.top || point.y > box.bottom) return null

  // On the dragged item itself (and the gap around it) the item stays where it is: without this, a
  // small movement while letting go would count as a drop on the row below or above it.
  const own = dragged.el.getBoundingClientRect()
  if (point.x >= own.left && point.x <= own.right && point.y >= own.top - ROW_GAP && point.y <= own.bottom + ROW_GAP) {
    return null
  }

  // The row at the pointer; the gap below a row counts for the row above it.
  const row = visibleRows(container, dragged).find((candidate) => point.y <= candidate.rect.bottom + ROW_GAP)
  if (!row) return endOfSiblings(container, null, dragged)

  const share = Math.max(0, Math.min(1, (point.y - row.rect.top) / row.rect.height))
  const item = { type: dragged.type, id: dragged.id }

  if (row.type === 'folder') {
    const zone = dropZone(row.rect.top, row.rect.bottom, point.y)
    if (zone === 'into') {
      return { drop: { ...item, parentId: row.id, anchor: 'end' }, into: row.id, line: null }
    }
    if (zone === 'before') {
      return {
        drop: { ...item, parentId: parentOf(row.el), anchor: { before: row.id } },
        into: null,
        line: { x: row.rect.left, y: row.rect.top - 2, width: row.rect.width },
      }
    }
    // Below an open folder with content comes its first entry.
    const children = listOf(container, row.id)
    if (children && children.getBoundingClientRect().height > 0) {
      return {
        drop: { ...item, parentId: row.id, anchor: 'first' },
        into: null,
        line: { x: row.rect.left + 16, y: row.rect.bottom + 2, width: row.rect.width - 16 },
      }
    }
    return {
      drop: { ...item, parentId: parentOf(row.el), anchor: { after: row.id } },
      into: null,
      line: { x: row.rect.left, y: row.rect.bottom + 2, width: row.rect.width },
    }
  }

  // A calendar row.
  const before = share < 0.5
  return {
    drop: { ...item, parentId: parentOf(row.el), anchor: before ? { before: row.id } : { after: row.id } },
    into: null,
    line: { x: row.rect.left, y: (before ? row.rect.top : row.rect.bottom) + (before ? -2 : 2), width: row.rect.width },
  }
}

/**
 * Makes the rows of the sidebar tree in `container` draggable (the scrolling element that holds
 * the tree); `onDrop` gets the move when an item is released on a valid target. On touch screens a
 * long press lifts the row; let go there without moving, `onHold` gets it (to open its menu, as iOS
 * has no right click and no context menu event), moved on, it is dragged.
 */
export function useSidebarDrag(
  container: Ref<HTMLElement | null>,
  onDrop: (drop: SidebarDrop) => void,
  onHold?: (item: { type: NodeType; id: string }, x: number, y: number) => void,
) {
  interface Press {
    dragged: Dragged
    pointerId: number
    pointerType: string
    startX: number
    startY: number
    offsetX: number
    offsetY: number
    rect: DOMRect
    timer?: ReturnType<typeof setTimeout>
    /** Whether the pointer moved away since the press, beyond what a finger wobbles. */
    moved: boolean
  }

  let press: Press | null = null
  let ghost: HTMLElement | null = null
  let active = false
  let point = { x: 0, y: 0 }
  let hit: Hit | null = null
  let openTimer: ReturnType<typeof setTimeout> | undefined
  let scrollFrame = 0

  function onPointerDown(event: PointerEvent) {
    if (press || active || event.button !== 0 || !event.isPrimary) return
    const target = event.target as HTMLElement
    if (target.closest('.sidebar-no-drag, button, input, textarea')) return
    const el = target.closest<HTMLElement>('.sidebar-item[data-type]')
    const type = el && typeOf(el)
    if (!el || !type || !el.dataset.id) return
    // The empty space inside an open folder belongs to the folder's list, not to the folder row.
    if (type === 'folder' && !el.firstElementChild?.contains(target)) return

    const header = type === 'folder' ? (el.firstElementChild as HTMLElement) : el
    const rect = header.getBoundingClientRect()
    press = {
      dragged: { type, id: el.dataset.id, el },
      pointerId: event.pointerId,
      pointerType: event.pointerType,
      startX: event.clientX,
      startY: event.clientY,
      offsetX: event.clientX - rect.left,
      offsetY: event.clientY - rect.top,
      rect,
      moved: false,
    }
    point = { x: event.clientX, y: event.clientY }
    document.addEventListener('pointermove', onPointerMove)
    document.addEventListener('pointerup', onPointerUp)
    document.addEventListener('pointercancel', onPointerCancel)
    if (event.pointerType === 'touch') press.timer = setTimeout(start, LONG_PRESS_MS)
  }

  function onPointerMove(event: PointerEvent) {
    // Only the pointer that started the drag counts; another finger or device is ignored.
    if (!press || event.pointerId !== press.pointerId) return
    point = { x: event.clientX, y: event.clientY }
    const moved = Math.hypot(point.x - press.startX, point.y - press.startY)
    if (moved > 8) press.moved = true
    if (!active && press) {
      if (press.pointerType === 'touch') {
        // Moving before the long press means scrolling.
        if (moved > 8) reset()
      } else if (moved >= DRAG_THRESHOLD) {
        start()
      }
      return
    }
    if (active) {
      moveGhost()
      update()
    }
  }

  function onPointerUp(event: PointerEvent) {
    if (!press || event.pointerId !== press.pointerId) return
    if (!active) return reset()
    const held = press.pointerType === 'touch' && !press.moved ? press.dragged : null
    const drop = hit?.drop
    reset()
    // The click that follows a drag or a long press must not open the row.
    const swallow = (event: Event) => event.stopPropagation()
    document.addEventListener('click', swallow, { capture: true, once: true })
    setTimeout(() => document.removeEventListener('click', swallow, true), 0)
    if (held) onHold?.({ type: held.type, id: held.id }, event.clientX, event.clientY)
    else if (drop) onDrop(drop)
  }

  function onPointerCancel(event?: Event) {
    // Another pointer's cancel doesn't end this drag; window and document events have no pointer.
    if (event instanceof PointerEvent && event.pointerId !== press?.pointerId) return
    reset()
  }

  function onKeyDown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      event.preventDefault()
      reset()
    }
  }

  // While dragging, a touch must not scroll the page.
  function onTouchMove(event: TouchEvent) {
    if (active) event.preventDefault()
  }

  function start() {
    if (!press || active) return
    clearTimeout(press.timer)
    active = true
    const { dragged, rect } = press
    draggingId.value = dragged.id

    const source = dragged.type === 'folder' ? (dragged.el.firstElementChild as HTMLElement) : dragged.el
    ghost = source.cloneNode(true) as HTMLElement
    for (const attribute of ['data-id', 'data-type', 'role', 'tabindex', 'aria-current'])
      ghost.removeAttribute(attribute)
    ghost.classList.remove('sidebar-item')
    Object.assign(ghost.style, {
      position: 'fixed',
      zIndex: '200',
      width: `${rect.width}px`,
      pointerEvents: 'none',
      opacity: '0.92',
      background: 'var(--app-surface)',
      boxShadow: '0 4px 14px rgb(0 0 0 / 0.25)',
    })
    document.body.appendChild(ghost)
    source.style.opacity = '0.4'
    document.body.style.cursor = 'grabbing'
    document.body.style.userSelect = 'none'
    document.addEventListener('keydown', onKeyDown)
    document.addEventListener('touchmove', onTouchMove, { passive: false })
    // A drag can't go on once the window loses the pointer (switching windows or tabs) or a menu opens.
    window.addEventListener('blur', onPointerCancel)
    document.addEventListener('visibilitychange', onPointerCancel)
    document.addEventListener('contextmenu', onPointerCancel, true)
    // Scrolling by wheel moves the rows under a resting pointer.
    container.value?.addEventListener('scroll', update)
    moveGhost()
    update()
    scrollLoop()
  }

  function moveGhost() {
    if (!ghost || !press) return
    ghost.style.left = `${point.x - press.offsetX}px`
    ghost.style.top = `${point.y - press.offsetY}px`
  }

  function update() {
    const el = container.value
    if (!el || !press) return
    hit = findHit(el, point, press.dragged)
    const box = el.getBoundingClientRect()
    dropIndicator.value = hit?.line
      ? {
          top: hit.line.y - box.top + el.scrollTop - 1,
          left: hit.line.x - box.left + el.scrollLeft,
          width: hit.line.width,
        }
      : null
    setIntoFolder(hit?.into ?? null)
  }

  function setIntoFolder(id: string | null) {
    if (dropTargetFolderId.value === id) return
    dropTargetFolderId.value = id
    clearTimeout(openTimer)
    if (id && collapsedFolders.has(id)) {
      // Opening shifts the rows below, so the target is looked up again afterwards.
      openTimer = setTimeout(() => {
        collapsedFolders.delete(id)
        requestAnimationFrame(() => active && update())
      }, OPEN_AFTER_MS)
    }
  }

  // Scrolls the list while the pointer is near its top or bottom edge.
  function scrollLoop() {
    const el = container.value
    if (!active || !el) return
    const box = el.getBoundingClientRect()
    let step = 0
    if (point.y < box.top + SCROLL_ZONE) step = -SCROLL_STEP
    else if (point.y > box.bottom - SCROLL_ZONE) step = SCROLL_STEP
    if (step) {
      const before = el.scrollTop
      el.scrollTop += step
      if (el.scrollTop !== before) update()
    }
    scrollFrame = requestAnimationFrame(scrollLoop)
  }

  function reset() {
    if (press) {
      clearTimeout(press.timer)
      const source =
        press.dragged.type === 'folder' ? (press.dragged.el.firstElementChild as HTMLElement | null) : press.dragged.el
      if (source) source.style.opacity = ''
    }
    press = null
    active = false
    hit = null
    ghost?.remove()
    ghost = null
    cancelAnimationFrame(scrollFrame)
    clearTimeout(openTimer)
    draggingId.value = null
    dropIndicator.value = null
    dropTargetFolderId.value = null
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
    document.removeEventListener('pointermove', onPointerMove)
    document.removeEventListener('pointerup', onPointerUp)
    document.removeEventListener('pointercancel', onPointerCancel)
    document.removeEventListener('keydown', onKeyDown)
    document.removeEventListener('touchmove', onTouchMove)
    window.removeEventListener('blur', onPointerCancel)
    document.removeEventListener('visibilitychange', onPointerCancel)
    document.removeEventListener('contextmenu', onPointerCancel, true)
    container.value?.removeEventListener('scroll', update)
  }

  onMounted(() => container.value?.addEventListener('pointerdown', onPointerDown))
  onBeforeUnmount(() => {
    container.value?.removeEventListener('pointerdown', onPointerDown)
    reset()
  })
}
