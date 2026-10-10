<script setup lang="ts">
import { computed } from 'vue'
import { Check, ChevronDown } from 'lucide-vue-next'
import { Listbox, ListboxButton, ListboxLabel, ListboxOption, ListboxOptions } from '@headlessui/vue'

export interface ColorPaletteOption {
  id: string
  label: string
  colors: string[]
}

const props = withDefaults(defineProps<{
  modelValue: string | null
  options: ColorPaletteOption[]
  placeholder: string
  label?: string
  disabled?: boolean
}>(), {
  disabled: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const selected = computed(() => props.options.find((option) => option.id === props.modelValue) ?? null)
</script>

<template>
  <Listbox :model-value="modelValue" :disabled="disabled" @update:model-value="emit('update:modelValue', $event)">
    <ListboxLabel v-if="label" class="mb-1 block text-sm font-medium text-gray-700">{{ label }}</ListboxLabel>
    <div class="relative">
      <ListboxButton class="flex w-full items-center justify-between gap-3 rounded-lg border border-gray-300 bg-[var(--app-input)] px-3 py-2 text-left text-sm focus-visible:outline-none focus-visible:!border-blue-500 focus-visible:ring-1 focus-visible:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-60">
        <span class="flex min-w-0 items-center gap-3">
          <span v-if="selected" class="flex shrink-0 overflow-hidden rounded-md border border-gray-200" aria-hidden="true">
            <span v-for="color in selected.colors" :key="color" class="h-7 w-5" :style="{ backgroundColor: color }"></span>
          </span>
          <span class="truncate font-medium text-gray-700">{{ selected?.label || placeholder }}</span>
        </span>
        <ChevronDown :size="18" class="shrink-0 text-gray-400" />
      </ListboxButton>

      <Transition leave-active-class="transition duration-100 ease-in" leave-from-class="opacity-100" leave-to-class="opacity-0">
        <ListboxOptions class="absolute z-20 mt-1 max-h-72 w-full overflow-auto rounded-lg border border-gray-200 bg-white p-1 shadow-lg focus:outline-none">
          <ListboxOption v-for="option in options" v-slot="{ active, selected: isSelected }" :key="option.id" :value="option.id" as="template">
            <li
              class="flex cursor-pointer select-none items-center gap-3 rounded-md px-3 py-2 text-sm"
              :class="[
                active ? 'bg-[var(--app-surface-muted)]' : '',
                isSelected ? 'text-blue-700 dark:text-blue-300' : 'text-gray-800 dark:text-gray-200',
              ]"
            >
              <span class="flex shrink-0 overflow-hidden rounded-md border border-gray-200" aria-hidden="true">
                <span v-for="color in option.colors" :key="color" class="h-7 w-5" :style="{ backgroundColor: color }"></span>
              </span>
              <span class="flex-1 font-medium">{{ option.label }}</span>
              <Check v-if="isSelected" :size="18" class="text-blue-600 dark:text-blue-300" />
            </li>
          </ListboxOption>
        </ListboxOptions>
      </Transition>
    </div>
  </Listbox>
</template>
