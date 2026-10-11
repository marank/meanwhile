<script setup lang="ts">
import { X } from 'lucide-vue-next'
import { useEscapeToClose } from '@/composables/useEscapeToClose'

const props = withDefaults(
  defineProps<{
    open: boolean
    title?: string
    size?: 'md' | 'xl' | '2xl'
    /** Close when the backdrop is clicked; turn off for forms that would lose their input. */
    dismissible?: boolean
    /** Stack above other open dialogs, e.g. for confirmations raised from within a dialog. */
    alwaysOnTop?: boolean
  }>(),
  { title: '', size: 'md', dismissible: true, alwaysOnTop: false },
)

const emit = defineEmits<{
  close: []
}>()

function onBackdropClick(event: MouseEvent) {
  if (props.dismissible && event.target === event.currentTarget) emit('close')
}

useEscapeToClose(
  () => props.open,
  () => emit('close'),
)
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm dark:bg-black/80"
      :class="alwaysOnTop ? 'z-[60]' : 'z-50'"
      @click="onBackdropClick"
    >
      <div
        class="flex max-h-[90vh] w-full flex-col overflow-hidden rounded-xl border border-transparent bg-surface shadow-2xl dark:border-zinc-600 dark:shadow-black/75"
        :class="{ md: 'max-w-md', xl: 'max-w-xl', '2xl': 'max-w-3xl' }[size]"
        role="dialog"
        aria-modal="true"
      >
        <div v-if="title || $slots.header" class="flex items-center justify-between border-b border-line px-6 py-4">
          <h3 v-if="title" class="text-lg font-semibold text-gray-800">{{ title }}</h3>
          <slot name="header" />
          <button
            type="button"
            class="text-gray-400 hover:text-gray-600"
            :aria-label="$t('app.close')"
            @click="emit('close')"
          >
            <X :size="20" />
          </button>
        </div>

        <div class="flex-1 overflow-y-auto px-6 py-4">
          <slot />
        </div>

        <div v-if="$slots.footer" class="border-t border-line bg-surface-muted px-6 py-4">
          <slot name="footer" />
        </div>
      </div>
    </div>
  </Teleport>
</template>
