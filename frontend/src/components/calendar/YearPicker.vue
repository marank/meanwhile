<script setup lang="ts">
import AppSelect, { type SelectSequence } from '@/components/AppSelect.vue'

defineProps<{ label: string }>()

const year = defineModel<number>({ required: true })

/** Years without end in either direction; typing four or more digits picks that year. */
const years: SelectSequence<number> = {
  step: (value, by) => value + by,
  label: String,
  fromDigits: (digits) => (digits.length >= 4 ? Number(digits) : null),
}
</script>

<template>
  <AppSelect v-model="year" :sequence="years" :label="label" align="end" />
</template>
