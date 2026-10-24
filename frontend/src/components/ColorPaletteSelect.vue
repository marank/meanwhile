<script setup lang="ts">
import { computed } from 'vue'
import AppSelect from '@/components/AppSelect.vue'

interface ColorPaletteOption {
  id: string
  label: string
  colors: string[]
}

const props = withDefaults(
  defineProps<{
    options: ColorPaletteOption[]
    placeholder: string
    label?: string
    disabled?: boolean
  }>(),
  { label: '', disabled: false },
)

/** The chosen palette; null while the colors match none of them. */
const paletteId = defineModel<string | null>({ required: true })

const selectOptions = computed(() => props.options.map(({ id, label }) => ({ value: id as string | null, label })))

function colorsOf(id: string | null | undefined): string[] {
  return props.options.find((option) => option.id === id)?.colors ?? []
}
</script>

<template>
  <label class="block">
    <span v-if="label" class="mb-1 block text-sm font-medium text-gray-700">{{ label }}</span>
    <AppSelect v-model="paletteId" :options="selectOptions" :placeholder="placeholder" :disabled="disabled">
      <template #selected="{ option }">
        <span class="flex min-w-0 items-center gap-3">
          <span v-if="option" class="flex shrink-0 overflow-hidden rounded-md border border-line" aria-hidden="true">
            <span
              v-for="color in colorsOf(option.value)"
              :key="color"
              class="h-6 w-5"
              :style="{ backgroundColor: color }"
            ></span>
          </span>
          <span class="truncate">{{ option?.label ?? placeholder }}</span>
        </span>
      </template>
      <template #option="{ option }">
        <span class="flex items-center gap-3">
          <span class="flex shrink-0 overflow-hidden rounded-md border border-line" aria-hidden="true">
            <span
              v-for="color in colorsOf(option.value)"
              :key="color"
              class="h-6 w-5"
              :style="{ backgroundColor: color }"
            ></span>
          </span>
          <span>{{ option.label }}</span>
        </span>
      </template>
    </AppSelect>
  </label>
</template>
