<script setup lang="ts">
import { X } from 'lucide-vue-next'
import { nextTick, onBeforeUnmount, ref, useId, watch } from 'vue'
import { useEscapeToClose } from '@/composables/useEscapeToClose'
import { useScrollFade } from '@/composables/useScrollFade'

const props = withDefaults(
  defineProps<{
    open: boolean
    title?: string
    size?: 'md' | 'xl' | '2xl'
    /**
     * Close when the backdrop is clicked or Escape is pressed; turn off for forms that would lose their
     * input (they then need a button of their own to close).
     */
    dismissible?: boolean
    /** Stack above other open dialogs, e.g. for confirmations raised from within a dialog. */
    alwaysOnTop?: boolean
    /** On phones, fill the screen below the navbar like a page instead of floating as a dialog. */
    fullscreenOnPhone?: boolean
  }>(),
  { title: '', size: 'md', dismissible: true, alwaysOnTop: false, fullscreenOnPhone: false },
)

const emit = defineEmits<{
  close: []
}>()

function onBackdropClick(event: MouseEvent) {
  if (props.dismissible && event.target === event.currentTarget) emit('close')
}

// Scrolled content fades out at the edges, like the tabs in a TabBar.
const body = ref<HTMLElement | null>(null)
const bodyContent = ref<HTMLElement | null>(null)
const { style: bodyFade } = useScrollFade(body, 'y', bodyContent)

useEscapeToClose(
  () => props.open,
  () => {
    if (props.dismissible) emit('close')
  },
)

// Focus moves into the dialog when it opens, stays inside while Tab cycles through it, and returns to
// where it was (e.g. the button that opened it) when the dialog closes.
const titleId = useId()
const panel = ref<HTMLElement | null>(null)
let returnFocusTo: HTMLElement | null = null

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]'

function focusable(): HTMLElement[] {
  return [...(panel.value?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? [])].filter((el) => el.tabIndex >= 0)
}

function restoreFocus() {
  if (returnFocusTo?.isConnected) returnFocusTo.focus()
  returnFocusTo = null
}

watch(
  () => props.open,
  async (open) => {
    if (!open) return restoreFocus()
    returnFocusTo = document.activeElement instanceof HTMLElement ? document.activeElement : null
    await nextTick()
    if (!panel.value || panel.value.contains(document.activeElement)) return
    // The content rather than the close button in the header comes first, e.g. a prompt's input.
    const elements = focusable()
    const target = elements.find((el) => !el.closest('[data-modal-header]')) ?? elements[0] ?? panel.value
    target.focus()
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  if (props.open) restoreFocus()
})

function trapFocus(event: KeyboardEvent) {
  if (event.key !== 'Tab') return
  const elements = focusable()
  const first = elements[0]
  const last = elements[elements.length - 1]
  const active = document.activeElement
  if (!first || !last) {
    event.preventDefault()
  } else if (event.shiftKey && (active === first || active === panel.value)) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && active === last) {
    event.preventDefault()
    first.focus()
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 flex items-center justify-center bg-black/50 p-2 backdrop-blur-sm sm:p-4 dark:bg-black/80"
      :class="[
        alwaysOnTop ? 'z-[60]' : 'z-50',
        { 'app-modal-fullscreen max-sm:top-[var(--navbar-height,0px)] max-sm:p-0': fullscreenOnPhone },
      ]"
      @click="onBackdropClick"
    >
      <div
        ref="panel"
        class="flex max-h-[calc(100dvh-1rem)] w-full outline-none flex-col sm:max-h-[90vh] overflow-hidden rounded-xl border border-transparent bg-surface shadow-2xl dark:border-zinc-600 dark:shadow-black/75"
        :class="[
          { md: 'max-w-md', xl: 'max-w-xl', '2xl': 'max-w-3xl' }[size],
          {
            'max-sm:h-full max-sm:max-h-none max-sm:max-w-none max-sm:rounded-none max-sm:border-0 max-sm:shadow-none':
              fullscreenOnPhone,
          },
        ]"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="title ? titleId : undefined"
        tabindex="-1"
        @keydown="trapFocus"
      >
        <div
          v-if="title || $slots.header"
          data-modal-header
          class="flex items-center justify-between border-b border-line px-4 py-3 sm:px-6 sm:py-4"
          :class="{ 'max-sm:py-2': fullscreenOnPhone }"
        >
          <div class="flex min-w-0 items-baseline gap-2">
            <h3 v-if="title" :id="titleId" class="text-lg font-semibold text-gray-800">{{ title }}</h3>
            <slot name="header" />
          </div>
          <button
            type="button"
            class="text-gray-400 hover:text-gray-600"
            :aria-label="$t('app.close')"
            @click="emit('close')"
          >
            <X :size="20" />
          </button>
        </div>

        <div
          ref="body"
          class="flex-1 overflow-y-auto px-4 py-4 sm:px-6"
          :class="{ 'max-sm:py-3': fullscreenOnPhone }"
          :style="bodyFade"
        >
          <div ref="bodyContent">
            <slot />
          </div>
        </div>

        <div
          v-if="$slots.footer"
          class="border-t border-line bg-surface-muted px-4 py-3 sm:px-6 sm:py-4"
          :class="{ 'max-sm:py-2': fullscreenOnPhone }"
        >
          <slot name="footer" />
        </div>
      </div>
    </div>
  </Teleport>
</template>
