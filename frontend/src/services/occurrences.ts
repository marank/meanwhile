import type { OccurrenceScope } from '@/api'
import { i18n } from '@/i18n'
import { choose } from './dialog'

/** One occurrence of a series as the calendar shows it; `recurrenceId` is its original start. */
export interface OccurrenceRef {
  recurrenceId: string
  start: string
  end: string
}

/**
 * Asks which occurrences of a series a change or deletion applies to; null when cancelled.
 * Without `allowThis` (e.g. when the recurrence itself changed) only whole parts of the series are offered.
 */
export function chooseScope(action: 'edit' | 'delete', allowThis = true): Promise<OccurrenceScope | null> {
  const t = i18n.global.t
  const scopes: OccurrenceScope[] = allowThis ? ['this', 'following', 'all'] : ['following', 'all']
  return choose(
    t(`series.${action}Message`),
    scopes.map((value) => ({ value, label: t(`series.${value}`) })),
    t(`series.${action}Title`),
  )
}
