<script setup lang="ts">
import type { GrantableRole } from '@/api'

withDefaults(
  defineProps<{
    modelValue: GrantableRole
    compact?: boolean
    disabled?: boolean
  }>(),
  {
    compact: false,
    disabled: false,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: GrantableRole]
}>()

const roles: GrantableRole[] = ['viewer', 'contributor', 'editor']
</script>

<template>
  <div>
    <select
      :value="modelValue"
      :disabled="disabled"
      class="w-full rounded-lg border"
      :class="compact ? 'px-2 py-1 text-sm' : 'px-3 py-2'"
      @change="emit('update:modelValue', ($event.target as HTMLSelectElement).value as GrantableRole)"
    >
      <option v-for="role in roles" :key="role" :value="role">{{ $t(`roles.${role}`) }}</option>
    </select>
    <p class="mt-1 text-xs text-gray-500">{{ $t(`roles.${modelValue}Description`) }}</p>
  </div>
</template>
