import { i18n } from '@/i18n'
import { useAuthStore } from '@/stores/auth'

function toDate(value: string | Date): Date {
  return value instanceof Date ? value : new Date(value)
}

export function hour12(): boolean | undefined {
  const pref = useAuthStore().user?.time_format ?? 'auto'
  if (pref === '12h') return true
  if (pref === '24h') return false
  return undefined
}

export function formatDate(value: string | Date): string {
  const date = toDate(value)
  const pref = useAuthStore().user?.date_format ?? 'auto'
  const day = String(date.getDate()).padStart(2, '0')
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const year = String(date.getFullYear())
  if (pref === 'dmy') return `${day}.${month}.${year}`
  if (pref === 'mdy') return `${month}/${day}/${year}`
  if (pref === 'ymd') return `${year}-${month}-${day}`
  return new Intl.DateTimeFormat(i18n.global.locale.value, {
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
  }).format(date)
}

export function formatTime(value: string | Date): string {
  return new Intl.DateTimeFormat(i18n.global.locale.value, {
    hour: 'numeric',
    minute: '2-digit',
    hour12: hour12(),
  }).format(toDate(value))
}

export function formatDateTime(value: string | Date): string {
  const date = toDate(value)
  return `${formatDate(date)} ${formatTime(date)}`
}
