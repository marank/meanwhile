import { ref } from 'vue'
import * as api from '@/api'

/**
 * Whether a calendar has categories and resources (other than places) to choose for its events; the
 * event dialog leaves out the fields of those it has none of. Asked like the fields themselves do
 * (search), so what counts is what they would offer.
 */
export function useCalendarChoices() {
  const hasCategories = ref(false)
  const hasResources = ref(false)

  async function load(calendarId: string) {
    const any = (entity: api.SearchEntity) =>
      api.searchEntities(entity, '', { calendarId, limit: 1 }).then((found) => found.length > 0)
    try {
      ;[hasCategories.value, hasResources.value] = await Promise.all([any('categories'), any('resources')])
    } catch {
      // Not known: better a field too many than one missing.
      hasCategories.value = hasResources.value = true
    }
  }

  return { hasCategories, hasResources, load }
}
