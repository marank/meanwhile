<script setup lang="ts">
withDefaults(
  defineProps<{
    open: boolean
    title?: string
  }>(),
  { title: '' },
)

const emit = defineEmits<{
  (e: 'close'): void
}>()

function onBackdropClick(event: MouseEvent) {
  if (event.target === event.currentTarget) {
    emit('close')
  }
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    emit('close')
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="modal-backdrop fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
      @click="onBackdropClick"
      @keydown="onKeydown"
      tabindex="-1"
    >
      <div
        class="modal-panel bg-white border border-transparent rounded-xl shadow-2xl w-full max-w-md overflow-hidden"
        role="dialog"
        aria-modal="true"
      >
        <div v-if="title || $slots.header" class="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h3 v-if="title" class="text-lg font-semibold text-gray-800">{{ title }}</h3>
          <slot name="header" />
          <button
            @click="emit('close')"
            class="text-gray-400 hover:text-gray-600 text-xl leading-none"
            aria-label="Close"
          >
            &times;
          </button>
        </div>

        <div class="px-6 py-4">
          <slot />
        </div>

        <div v-if="$slots.footer" class="px-6 py-4 border-t border-gray-100 bg-gray-50">
          <slot name="footer" />
        </div>
      </div>
    </div>
  </Teleport>
</template>
