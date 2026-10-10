import { onBeforeUnmount, watch } from 'vue'

// Open dialogs in the order they were opened; Escape only closes the topmost one.
const stack: symbol[] = []

function removeFromStack(id: symbol) {
  const index = stack.indexOf(id)
  if (index !== -1) stack.splice(index, 1)
}

/**
 * Closes a dialog on Escape while it is open. Nested widgets that handle Escape themselves
 * (dropdowns, comboboxes) call preventDefault, which leaves the dialog open.
 */
export function useEscapeToClose(isOpen: () => boolean, onClose: () => void) {
  const id = Symbol('dialog')

  function onKeydown(event: KeyboardEvent) {
    if (event.key !== 'Escape' || event.defaultPrevented) return
    if (stack[stack.length - 1] !== id) return
    event.preventDefault()
    onClose()
  }

  watch(
    isOpen,
    (open) => {
      removeFromStack(id)
      window.removeEventListener('keydown', onKeydown)
      if (open) {
        stack.push(id)
        window.addEventListener('keydown', onKeydown)
      }
    },
    { immediate: true },
  )

  onBeforeUnmount(() => {
    removeFromStack(id)
    window.removeEventListener('keydown', onKeydown)
  })
}
