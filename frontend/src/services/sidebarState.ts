import { reactive, ref } from 'vue'

/** Folders the user closed; kept here so that reloading the tree doesn't open them again. */
export const collapsedFolders = reactive(new Set<string>())

/** The folder a dragged calendar or folder would be dropped into, while dragging. */
export const dropTargetFolderId = ref<string | null>(null)

/** The calendar or folder being dragged. */
export const draggingId = ref<string | null>(null)

/** The line showing where a dragged item would go between rows, relative to the scrolling list. */
export const dropIndicator = ref<{ top: number; left: number; width: number } | null>(null)

/** Below the desktop breakpoint the sidebar is a drawer over the page; whether it is open. */
export const sidebarDrawerOpen = ref(false)
