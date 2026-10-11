import { onMounted, onUnmounted, type Ref } from 'vue'
import type Sortable from 'sortablejs'
import { collapsedFolders, dropTargetFolderId } from '@/services/sidebarState'

/**
 * Called when a drag ends. `dropIntoFolderId` is set when the item was dropped *onto* a folder
 * (not between entries); Sortable then hasn't moved it, and the caller puts it into the folder.
 */
export type SidebarSortEnd = (event: Sortable.SortableEvent, dropIntoFolderId: string | null) => void

/** Share of a folder row, from each edge, that still sorts before or after it; the middle drops into it. */
const EDGE_SHARE = 0.25
/** How long a dragged item rests on a closed folder before it opens. */
const OPEN_AFTER_MS = 700

export type FolderDropZone = 'before' | 'into' | 'after'

/** Where on a folder row (top to bottom) the pointer is. */
export function folderDropZone(top: number, bottom: number, y: number): FolderDropZone | null {
  if (y < top || y > bottom) return null
  const edge = (bottom - top) * EDGE_SHARE
  if (y < top + edge) return 'before'
  if (y > bottom - edge) return 'after'
  return 'into'
}

// One drag at a time, across all lists of the sidebar.
let dragged: HTMLElement | null = null
let pointer = { x: 0, y: 0 }
let openTimer: ReturnType<typeof setTimeout> | undefined

/** The folder whose row has the pointer in its middle, other than the dragged folder and its contents. */
function folderUnder(x: number, y: number): string | null {
  for (const row of document.querySelectorAll<HTMLElement>('.sidebar-item[data-type="folder"]')) {
    if (dragged?.contains(row) || !row.dataset.id) continue
    const header = row.firstElementChild
    if (!header) continue
    const rect = header.getBoundingClientRect()
    if (x >= rect.left && x <= rect.right && folderDropZone(rect.top, rect.bottom, y) === 'into') return row.dataset.id
  }
  return null
}

function setTarget(id: string | null) {
  if (dropTargetFolderId.value === id) return
  dropTargetFolderId.value = id
  clearTimeout(openTimer)
  if (id && collapsedFolders.has(id)) openTimer = setTimeout(() => collapsedFolders.delete(id), OPEN_AFTER_MS)
}

function track(event: Event) {
  // Mouse, pointer and drag events carry the position themselves, touch events in their touches.
  const point = 'clientX' in event ? (event as MouseEvent) : (event as TouchEvent).touches?.[0]
  if (!point) return
  pointer = { x: point.clientX, y: point.clientY }
  setTarget(folderUnder(pointer.x, pointer.y))
}

function startTracking(item: HTMLElement) {
  dragged = item
  // Native drags report their pointer in dragover, touch drags (Sortable's fallback) in pointermove.
  // In the capture phase: Sortable stops dragover events from bubbling on its lists.
  document.addEventListener('dragover', track, true)
  document.addEventListener('pointermove', track, true)
}

/** Stops tracking and returns the folder the item was dropped onto, if any. */
function stopTracking(): string | null {
  document.removeEventListener('dragover', track, true)
  document.removeEventListener('pointermove', track, true)
  const target = folderUnder(pointer.x, pointer.y)
  dragged = null
  setTarget(null)
  return target
}

/** Makes the sidebar list in `element` sortable; all sidebar lists share one drag group. */
export function useSidebarSortable(element: Ref<HTMLElement | null>, onEnd: SidebarSortEnd) {
  let sortable: Sortable | null = null
  let unmounted = false

  onMounted(async () => {
    const { default: SortableJs } = await import('sortablejs')
    if (unmounted || !element.value) return
    sortable = SortableJs.create(element.value, {
      group: 'sidebar',
      animation: 150,
      draggable: '.sidebar-item',
      filter: '.sidebar-no-drag',
      preventOnFilter: false,
      onStart: (event) => startTracking(event.item),
      // With the pointer in the middle of a folder row, nothing moves aside: the item is dropped onto it.
      onMove: (_event, originalEvent) => {
        track(originalEvent)
        return dropTargetFolderId.value === null
      },
      onEnd: (event) => onEnd(event, stopTracking()),
    })
  })

  onUnmounted(() => {
    unmounted = true
    sortable?.destroy()
    sortable = null
  })
}
