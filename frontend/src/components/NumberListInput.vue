<script setup lang="ts">
import { ref, watch } from 'vue'
import { formatNumberList, parseNumberList } from '@/services/numberList'

const props = withDefaults(
  defineProps<{
    min: number
    max: number
    /** Accept "+" for the last one. */
    allowLast?: boolean
    label: string
    placeholder?: string
  }>(),
  { allowLast: false, placeholder: '' },
)

const model = defineModel<number[]>({ required: true })

const text = ref(formatNumberList(model.value))
const invalid = ref(false)

// Changes from outside (e.g. another preset) replace the text; the user's own typing stays as typed.
watch(model, (value) => {
  if (
    formatNumberList(parseNumberList(text.value, props.min, props.max, props.allowLast) ?? []) !==
    formatNumberList(value)
  ) {
    text.value = formatNumberList(value)
  }
})

function onInput() {
  const numbers = parseNumberList(text.value, props.min, props.max, props.allowLast)
  invalid.value = numbers === null
  if (numbers) model.value = numbers
}

// Invalid input is dropped when leaving the field, so what is shown is what gets saved.
function onBlur() {
  text.value = formatNumberList(model.value)
  invalid.value = false
}
</script>

<template>
  <input
    v-model="text"
    type="text"
    inputmode="numeric"
    :placeholder="placeholder"
    :aria-label="label"
    :aria-invalid="invalid"
    class="w-32 rounded-lg border px-3 py-1.5 align-middle leading-5"
    @input="onInput"
    @blur="onBlur"
  />
</template>
