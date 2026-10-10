import { onMounted, onUnmounted, type Ref } from 'vue'
import type Sortable from 'sortablejs'

/** Makes the sidebar list in `element` sortable; all sidebar lists share one drag group. */
export function useSidebarSortable(element: Ref<HTMLElement | null>, onEnd: (event: Sortable.SortableEvent) => void) {
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
      onEnd,
    })
  })

  onUnmounted(() => {
    unmounted = true
    sortable?.destroy()
    sortable = null
  })
}
