import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

/**
 * The active tab of a page, kept in the `tab` query parameter; the first tab is the default.
 * Switching tabs replaces the history entry, so going back leaves the page instead of stepping through its tabs.
 */
export function useQueryTab<T extends string>(tabs: readonly T[]) {
  const route = useRoute()
  const router = useRouter()
  const isTab = (value: unknown): value is T => typeof value === 'string' && (tabs as readonly string[]).includes(value)

  const tab = computed<T>(() => (isTab(route.query.tab) ? route.query.tab : tabs[0]!))

  watch(
    () => route.query.tab,
    (value) => {
      if (value !== undefined && !isTab(value)) void router.replace({ query: { ...route.query, tab: tabs[0] } })
    },
  )

  function selectTab(id: T) {
    void router.replace({ query: { ...route.query, tab: id } })
  }

  return { tab, selectTab }
}
