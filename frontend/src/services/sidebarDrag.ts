import type { LayoutItem } from '@/api'

export type NodeType = 'folder' | 'calendar'

/** A folder or calendar of the user's sidebar tree. */
export interface TreeNode {
  id: string
  parentId: string | null
  position: number
  name: string
}

export interface SidebarTree {
  folders: TreeNode[]
  calendars: TreeNode[]
}

/** Where among the entries of the new parent an item goes. */
export type DropAnchor = { before: string } | { after: string } | 'first' | 'end'

function nodes(tree: SidebarTree, type: NodeType): TreeNode[] {
  return type === 'folder' ? tree.folders : tree.calendars
}

/** Folders and calendars of a parent form one list; at the same position, folders come first. */
const TYPE_RANK: Record<NodeType, number> = { folder: 0, calendar: 1 }

export function compareSiblings(
  a: { position: number; type: NodeType; name: string },
  b: { position: number; type: NodeType; name: string },
): number {
  return a.position - b.position || TYPE_RANK[a.type] - TYPE_RANK[b.type] || a.name.localeCompare(b.name)
}

interface Sibling {
  id: string
  type: NodeType
}

/** Everything directly under a parent, folders and calendars together, in display order. */
function siblings(tree: SidebarTree, parentId: string | null, excludeId?: string): Sibling[] {
  return [
    ...tree.folders.map((node) => ({ ...node, type: 'folder' as const })),
    ...tree.calendars.map((node) => ({ ...node, type: 'calendar' as const })),
  ]
    .filter((node) => node.parentId === parentId && node.id !== excludeId)
    .sort(compareSiblings)
    .map(({ id, type }) => ({ id, type }))
}

/** Ids of what is directly under a parent, in the order the sidebar shows them. */
export function siblingIds(tree: SidebarTree, parentId: string | null, excludeId?: string): string[] {
  return siblings(tree, parentId, excludeId).map((node) => node.id)
}

function descendantFolderIds(tree: SidebarTree, folderId: string): Set<string> {
  const found = new Set<string>()
  const pending = [folderId]
  while (pending.length) {
    const current = pending.pop()!
    for (const folder of tree.folders) {
      if (folder.parentId === current && !found.has(folder.id) && folder.id !== folderId) {
        found.add(folder.id)
        pending.push(folder.id)
      }
    }
  }
  return found
}

/** A folder can't go into itself or one of its own subfolders; everything else can go anywhere. */
export function canDropInto(tree: SidebarTree, type: NodeType, id: string, parentId: string | null): boolean {
  if (type !== 'folder' || parentId === null) return true
  return parentId !== id && !descendantFolderIds(tree, id).has(parentId)
}

/**
 * The position updates that move an item: it goes to `anchor` among everything under `parentId`
 * (folders and calendars alike), and those entries are numbered anew. Empty if nothing would change.
 */
export function planMove(
  tree: SidebarTree,
  type: NodeType,
  id: string,
  parentId: string | null,
  anchor: DropAnchor,
): LayoutItem[] {
  // Gone meanwhile (deleted in another tab, say), or not allowed.
  const current = nodes(tree, type).find((node) => node.id === id)
  if (!current || !canDropInto(tree, type, id, parentId)) return []
  const others = siblings(tree, parentId, id)
  let index = others.length
  if (anchor === 'first') index = 0
  else if (anchor !== 'end') {
    const reference = 'before' in anchor ? anchor.before : anchor.after
    const found = others.findIndex((node) => node.id === reference)
    if (found !== -1) index = 'before' in anchor ? found : found + 1
  }
  const ordered = [...others.slice(0, index), { id, type }, ...others.slice(index)]

  const unchanged =
    current.parentId === parentId && siblingIds(tree, parentId).join() === ordered.map((node) => node.id).join()
  if (unchanged) return []
  return ordered.map((node, position) => ({ type: node.type, id: node.id, parent_id: parentId, position }))
}
