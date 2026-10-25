import { computed, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { createAvailabilityCache, loadAvailability, startOfDay } from '@/services/availability'
import { useAuthStore } from '@/stores/auth'

interface Person {
  user_id?: string | null
  display_name: string | null
  email: string
}

/** Whose availability the event dialog shows, and which resources: kept in a cache while it is open. */
export function useEventAvailability(options: {
  participants: Ref<readonly Person[]>
  resourceIds: Ref<string[]>
  slot: Ref<{ start: Date; end: Date }>
}) {
  const auth = useAuthStore()
  const { t } = useI18n()

  /** Whose availability is shown: oneself and the participants who have an account. */
  const people = computed(() => {
    const me = auth.user ? [{ id: auth.user.id, name: t('availability.me') }] : []
    const others = options.participants.value
      .filter((p) => p.user_id && p.user_id !== auth.user?.id)
      .map((p) => ({ id: p.user_id!, name: p.display_name || p.email }))
    return [...me, ...others]
  })
  const cache = createAvailabilityCache()

  /** The availability tab finds the event's day ready when it is opened. */
  function preload(eventId: string | undefined) {
    const userIds = people.value.map((p) => p.id)
    if (userIds.length || options.resourceIds.value.length) {
      loadAvailability(cache, startOfDay(options.slot.value.start), userIds, options.resourceIds.value, eventId)
    }
  }

  return { people, cache, preload }
}
