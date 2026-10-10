import { reactive, ref } from 'vue'

type DialogKind = 'alert' | 'confirm' | 'prompt'

interface DialogState {
  open: boolean
  kind: DialogKind
  title: string
  message: string
  resolve: ((value: unknown) => void) | null
}

export const dialog = reactive<DialogState>({
  open: false,
  kind: 'alert',
  title: '',
  message: '',
  resolve: null,
})

export const inputValue = ref('')

function openDialog<T>(kind: DialogKind, message: string, title: string, defaultValue = ''): Promise<T> {
  return new Promise<T>((resolve) => {
    dialog.kind = kind
    dialog.title = title
    dialog.message = message
    inputValue.value = defaultValue
    dialog.resolve = resolve as (value: unknown) => void
    dialog.open = true
  })
}

export function alert(message: string, title = ''): Promise<void> {
  return openDialog<void>('alert', message, title)
}

export function confirm(message: string, title = ''): Promise<boolean> {
  return openDialog<boolean>('confirm', message, title)
}

export function prompt(message: string, defaultValue = '', title = ''): Promise<string | null> {
  return openDialog<string | null>('prompt', message, title, defaultValue)
}

/** Closes the dialog with the answer for the promise returned by alert/confirm/prompt. */
export function submitDialog(value?: unknown) {
  dialog.resolve?.(value)
  dialog.open = false
  dialog.resolve = null
}
