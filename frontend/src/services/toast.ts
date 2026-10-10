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
