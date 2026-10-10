<script setup lang="ts" generic="T extends string | number | boolean">
defineProps<{
  options: Array<{ value: T; label: string }>
  label: string
}>()

const model = defineModel<T>({ required: true })
</script>

<template>
  <div class="inline-flex rounded-lg border border-line p-0.5 text-sm" role="radiogroup" :aria-label="label">
    <button
      v-for="option in options"
      :key="String(option.value)"
      type="button"
      role="radio"
      :aria-checked="model === option.value"
      class="rounded-md px-3 py-1.5 font-medium transition-colors"
      :class="model === option.value ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-hover'"
      @click="model = option.value"
    >
      {{ option.label }}
    </button>
  </div>
</template>
