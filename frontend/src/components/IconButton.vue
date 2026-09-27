<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    label: string
    tone?: 'muted' | 'primary' | 'danger'
    bordered?: boolean
  }>(),
  { tone: 'muted', bordered: false },
)

const toneClass = computed(() => ({
  muted: 'text-gray-500 hover:text-gray-800',
  primary: 'text-blue-600 hover:text-blue-500',
  danger: 'text-red-600 hover:text-red-500',
}[props.tone]))
</script>

<template>
  <button
    type="button"
    class="group/icon inline-flex items-center justify-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
    :class="[toneClass, bordered ? 'border border-gray-300 rounded-lg p-2' : 'p-1']"
    :title="label"
    :aria-label="label"
  >
    <span class="inline-flex transition duration-150 group-hover/icon:scale-110 group-hover/icon:drop-shadow-sm group-focus-visible/icon:scale-110">
      <slot />
    </span>
  </button>
</template>
