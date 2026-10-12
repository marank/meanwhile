import { inject, provide, ref, type InjectionKey, type Ref } from 'vue'

/**
 * Lets the tabs of the calendar settings tell each other what changed. The tabs stay alive while
 * one switches between them, so a change in one (e.g. a member removed) must reach the others by
 * itself: they used to reload whenever they were opened.
 */
interface CalendarSettingsSync {
  /** Counts up whenever members were added or removed. */
  membersVersion: Ref<number>
  membersChanged(): void
}

const key: InjectionKey<CalendarSettingsSync> = Symbol('calendarSettingsSync')

/** Called by the page that holds the tabs. */
export function provideCalendarSettingsSync(): CalendarSettingsSync {
  const membersVersion = ref(0)
  const sync = { membersVersion, membersChanged: () => membersVersion.value++ }
  provide(key, sync)
  return sync
}

/** Called by a tab; without a page around it (e.g. in a test) nothing is shared. */
export function useCalendarSettingsSync(): CalendarSettingsSync {
  return inject(key, () => ({ membersVersion: ref(0), membersChanged: () => {} }), true)
}
