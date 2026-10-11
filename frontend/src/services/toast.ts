import { reactive } from 'vue'

export type ToastTone = 'success' | 'error' | 'info'

export interface ToastMessage {
  id: number
  message: string
  tone: ToastTone
}

export const toasts = reactive<ToastMessage[]>([])
let nextId = 1

export function dismissToast(id: number) {
  const index = toasts.findIndex((toast) => toast.id === id)
  if (index !== -1) toasts.splice(index, 1)
}

function showToast(message: string, tone: ToastTone, durationMs = 5000) {
  const id = nextId++
  toasts.push({ id, message, tone })
  window.setTimeout(() => dismissToast(id), durationMs)
}

export const toast = {
  success: (message: string) => showToast(message, 'success'),
  error: (message: string) => showToast(message, 'error'),
  /** Stays longer: e.g. a reminder that may come while one looks elsewhere. */
  info: (message: string) => showToast(message, 'info', 15000),
}
