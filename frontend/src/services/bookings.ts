import type { Composer } from 'vue-i18n'

/** Readable message for a failed booking request; conflicts (409) get a translated text. */
export function bookingErrorMessage(error: unknown, t: Composer['t']): string {
  const e = error as { status?: number; message?: string; detail?: { detail?: unknown } }
  if (e?.status === 409) return t('booking.conflict')
  const detail = e?.detail?.detail
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object' && 'message' in detail) return String((detail as { message: unknown }).message)
  return e?.message || t('app.actionFailed')
}
