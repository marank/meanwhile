import { reactive, ref } from 'vue'

type DialogKind = 'alert' | 'confirm' | 'prompt' | 'choice'

export interface DialogChoice {
  value: string
  label: string
}

interface DialogState {
  open: boolean
  kind: DialogKind
  title: string
  message: string
  /** The answers offered by choose(). */
  choices: DialogChoice[]
  resolve: ((value: unknown) => void) | null
}

export const dialog = reactive<DialogState>({
  open: false,
  kind: 'alert',
  title: '',
  message: '',
  choices: [],
  resolve: null,
})

export const inputValue = ref('')

function openDialog<T>(
  kind: DialogKind,
  message: string,
  title: string,
  defaultValue = '',
  choices: DialogChoice[] = [],
): Promise<T> {
  return new Promise<T>((resolve) => {
    dialog.kind = kind
    dialog.title = title
    dialog.message = message
    dialog.choices = choices
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

/** Asks to pick one of `choices`; resolves with its value, or null when cancelled. */
export function choose<T extends string>(
  message: string,
  choices: { value: T; label: string }[],
  title = '',
): Promise<T | null> {
  return openDialog<T | null>('choice', message, title, '', choices)
}

/** Closes the dialog with the answer for the promise returned by alert/confirm/prompt. */
export function submitDialog(value?: unknown) {
  dialog.resolve?.(value)
  dialog.open = false
  dialog.resolve = null
}
