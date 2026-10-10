<script setup lang="ts">
const props = withDefaults(defineProps<{
  modelValue?: boolean
  title: string
  description?: string
  disabled?: boolean
}>(), {
  modelValue: false,
  description: '',
  disabled: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

function toggle() {
  if (!props.disabled) emit('update:modelValue', !props.modelValue)
}
</script>

<template>
  <button
    type="button"
    role="switch"
    :aria-checked="modelValue"
    :disabled="disabled"
    class="flex w-full items-center justify-between gap-5 rounded-lg border border-gray-200 px-4 py-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
    @click="toggle"
  >
    <span class="min-w-0">
      <span class="block text-sm font-medium text-gray-800">{{ title }}</span>
      <span v-if="description" class="mt-0.5 block text-xs leading-5 text-gray-500">{{ description }}</span>
    </span>
    <span
      class="relative h-6 w-11 shrink-0 rounded-full transition-colors"
      :class="modelValue ? 'bg-blue-600' : 'bg-gray-300'"
      aria-hidden="true"
    >
      <span
        class="absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform"
        :class="modelValue ? 'translate-x-5' : 'translate-x-0.5'"
      />
    </span>
  </button>
</template>
