import { reactive, ref } from 'vue'

/** Folders the user closed; kept here so that reloading the tree doesn't open them again. */
export const collapsedFolders = reactive(new Set<string>())

/** The folder a dragged calendar or folder would be dropped into, while dragging. */
export const dropTargetFolderId = ref<string | null>(null)
