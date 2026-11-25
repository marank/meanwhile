<script setup lang="ts">
import { computed, useId } from 'vue'
import { nonEmpty } from '@/services/text'

withDefaults(
  defineProps<{
    label: string
    /** What the app shows while none is uploaded, e.g. its own logo. */
    defaultImage: string
    /** Says that the default is in use. */
    defaultLabel: string
    removeLabel: string
    size?: 'sm' | 'lg'
  }>(),
  {
    size: 'lg',
  },
)

const labelId = useId()

// Images are stored inline as data URLs; the server sends "" for none.
const image = defineModel<string | null>({ required: true })
const custom = computed(() => nonEmpty(image.value))

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
        class="flex shrink-0 items-center justify-center overflow-hidden rounded-lg border border-line bg-surface p-1"
        :class="size === 'lg' ? 'h-16 w-16' : 'h-10 w-10'"
        :data-default="!custom || undefined"
      >
        <img :src="custom ?? defaultImage" alt="" class="max-h-full max-w-full object-contain" />
      </div>
      <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
        <!-- A button of our own instead of the browser's file field ("Choose file / No file chosen"),
             which can't be styled; the field stays, invisible, for the keyboard and screen readers. -->
        <label
          class="cursor-pointer rounded-lg border border-line px-3 py-1.5 text-sm text-gray-700 focus-within:ring-2 focus-within:ring-blue-500 hover:bg-hover"
        >
          <input type="file" accept="image/*" :aria-labelledby="labelId" class="sr-only" @change="onChange" />
          {{ custom ? $t('app.changeImage') : $t('app.chooseImage') }}
        </label>
        <button v-if="custom" type="button" class="text-sm text-red-600 hover:underline" @click="image = null">
          {{ removeLabel }}
        </button>
        <span v-else class="basis-full text-xs text-gray-500">{{ defaultLabel }}</span>
      </div>
    </div>
  </div>
</template>
