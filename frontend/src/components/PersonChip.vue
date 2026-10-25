<script setup lang="ts">
import { X } from '@lucide/vue'

withDefaults(
  defineProps<{
    name: string
    email: string
    removable?: boolean
    disabled?: boolean
  }>(),
  {
    removable: false,
    disabled: false,
  },
)

const emit = defineEmits<{
  remove: []
}>()
</script>

<template>
  <li class="inline-flex items-center gap-2 rounded-full border border-line py-1 pl-1 pr-2 text-sm" :title="email">
    <span
      class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-100 text-xs font-semibold text-blue-700 dark:bg-blue-900 dark:text-blue-200"
      aria-hidden="true"
    >
      {{ (name || email).charAt(0).toUpperCase() }}
    </span>
    <span class="font-medium text-gray-800">{{ name }}</span>
    <button
      v-if="removable"
      type="button"
      :disabled="disabled"
      class="rounded-full p-0.5 text-gray-400 hover:bg-hover hover:text-gray-700 disabled:opacity-50"
      :aria-label="$t('app.delete')"
      @click="emit('remove')"
    >
      <X :size="14" />
    </button>
  </li>
</template>
