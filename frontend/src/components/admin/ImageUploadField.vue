<script setup lang="ts">
import { useId } from 'vue'

withDefaults(
  defineProps<{
    label: string
    emptyLabel: string
    removeLabel: string
    size?: 'sm' | 'lg'
  }>(),
  {
    size: 'lg',
  },
)

const labelId = useId()

// Images are stored inline as data URLs.
const image = defineModel<string | null>({ required: true })

function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

async function onChange(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (file) image.value = await readAsDataUrl(file)
}
</script>

<template>
  <div>
    <span :id="labelId" class="mb-1 block text-sm font-medium text-gray-800">{{ label }}</span>
    <div class="flex items-center gap-4">
      <div
        class="flex items-center justify-center overflow-hidden border border-line"
        :class="[
          size === 'lg' ? 'h-16 w-16 rounded-lg text-sm' : 'h-10 w-10 rounded text-xs',
          image ? 'bg-surface' : 'bg-surface-muted text-gray-400',
        ]"
      >
        <img v-if="image" :src="image" alt="" class="max-h-full max-w-full object-contain" />
        <template v-else>{{ emptyLabel }}</template>
      </div>
      <div class="flex flex-wrap items-center gap-3">
        <!-- A button of our own instead of the browser's file field ("Choose file / No file chosen"),
             which can't be styled; the field stays, invisible, for the keyboard and screen readers. -->
        <label
          class="cursor-pointer rounded-lg border border-line px-3 py-1.5 text-sm text-gray-700 focus-within:ring-2 focus-within:ring-blue-500 hover:bg-hover"
        >
          <input type="file" accept="image/*" :aria-labelledby="labelId" class="sr-only" @change="onChange" />
          {{ image ? $t('app.changeImage') : $t('app.chooseImage') }}
        </label>
        <button v-if="image" type="button" class="text-sm text-red-600 hover:underline" @click="image = null">
          {{ removeLabel }}
        </button>
      </div>
    </div>
  </div>
</template>
