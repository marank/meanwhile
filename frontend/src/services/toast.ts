import { reactive } from 'vue'

export type ToastTone = 'success' | 'error'

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

function showToast(message: string, tone: ToastTone) {
  const id = nextId++
  toasts.push({ id, message, tone })
  window.setTimeout(() => dismissToast(id), 5000)
}

export const toast = {
  success: (message: string) => showToast(message, 'success'),
  error: (message: string) => showToast(message, 'error'),
}

export function errorMessage(error: unknown, fallback: string): string {
  const value = error as {
    detail?: string | { detail?: string; errors?: Array<{ message?: string }> }
    message?: string
  }
  if (typeof value.detail === 'string') return value.detail
  if (typeof value.detail?.detail === 'string') return value.detail.detail
  const errors = value.detail?.errors?.map((item) => item.message).filter(Boolean)
  if (errors?.length) return errors.join(', ')
  return value.message || fallback
}
