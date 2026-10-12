<script setup lang="ts">
const model = defineModel<boolean>({ default: false })
defineProps<{ label: string; disabled?: boolean }>()
</script>

<template>
  <button
    type="button"
    role="switch"
    :aria-checked="model"
    :disabled="disabled"
    class="inline-flex items-center gap-2 rounded text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
    @click="model = !model"
  >
    <span
      class="relative h-5 w-9 shrink-0 rounded-full transition-colors"
      :class="model ? 'bg-blue-600' : 'bg-gray-400'"
      aria-hidden="true"
    >
      <span
        class="absolute left-0 top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-transform"
        :class="model ? 'translate-x-[1.125rem]' : 'translate-x-0.5'"
      />
    </span>
    {{ label }}
  </button>
</template>
