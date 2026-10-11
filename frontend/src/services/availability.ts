import * as api from '@/api'

interface Entry {
  promise: Promise<api.Availability>
  /** Set once loaded, so a view can show it right away instead of waiting a tick. */
  value?: api.Availability
}

/**
 * Availability already asked for, by day, people and resources. One dialog keeps one cache:
 * switching tabs or days back and forth asks the server only once, and other people or
 * resources are simply another entry.
 */
export type AvailabilityCache = Map<string, Entry>

export function createAvailabilityCache(): AvailabilityCache {
  return new Map()
}

export function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}

function cacheKey(day: Date, userIds: string[], resourceIds: string[], excludeEventId?: string | null) {
  return [day.getTime(), [...userIds].sort().join(','), [...resourceIds].sort().join(','), excludeEventId ?? ''].join(
    '|',
  )
}

/** The day's entry, loading it if it isn't cached yet. */
export function loadAvailability(
  cache: AvailabilityCache,
  day: Date,
  userIds: string[],
  resourceIds: string[],
  excludeEventId?: string | null,
): Entry {
  const key = cacheKey(day, userIds, resourceIds, excludeEventId)
  let entry = cache.get(key)
  if (!entry) {
    const end = new Date(day)
    end.setDate(end.getDate() + 1)
    const created: Entry = {
      promise: api.getAvailability(day.toISOString(), end.toISOString(), userIds, resourceIds, excludeEventId),
    }
    created.promise.then(
      (value) => (created.value = value),
      // A failed request is asked again next time.
      () => cache.delete(key),
    )
    cache.set(key, created)
    entry = created
  }
  return entry
}
