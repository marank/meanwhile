import { ApiError } from '@/api'
import { i18n } from '@/i18n'

type ErrorDetail = {
  detail?: unknown
  message?: unknown
  errors?: Array<{ message?: string; code?: string }>
}

function detailMessage(detail: unknown): string | null {
  if (typeof detail === 'string') return detail || null
  if (!detail || typeof detail !== 'object') return null
  const value = detail as ErrorDetail
  if (typeof value.message === 'string') return value.message
  if (value.detail !== undefined) return detailMessage(value.detail)
  // django-allauth reports validation problems as a list.
  const errors = value.errors?.map((item) => item.message || item.code).filter(Boolean)
  return errors?.length ? errors.join(', ') : null
}

/** Readable message for a failed request: the server's explanation if it sent one, else the fallback. */
export function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return detailMessage(error.detail) ?? fallback
  if (error instanceof Error && error.message) return error.message
  return fallback
}

/** Like errorMessage, but booking conflicts (409) get a translated explanation. */
export function bookingErrorMessage(error: unknown): string {
  const { t } = i18n.global
  if (error instanceof ApiError && error.status === 409) return t('booking.conflict')
  return errorMessage(error, t('app.actionFailed'))
}
