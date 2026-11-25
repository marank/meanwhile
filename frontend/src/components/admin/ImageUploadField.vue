<script setup lang="ts">
import { computed, ref, useId } from 'vue'
import { nonEmpty } from '@/services/text'

withDefaults(
  defineProps<{
    label: string
    /** What the app shows while none is uploaded, e.g. its own logo. */
    defaultImage: string
    /** Says that the default is in use. */
    defaultLabel: string
    removeLabel: string
    /** The size it looks best in, and that the format matters (e.g. for emails). */
    hint: string
    size?: 'sm' | 'lg'
  }>(),
  {
    size: 'lg',
  },
)

const labelId = useId()
const hintId = useId()
const tooLarge = ref(false)

// What the server takes (AppSettingsUpdate: a data URL of at most 1,000,000 characters, so a file
// of about 730 KB); a larger one is refused here, with the reason, instead of failing on saving.
const MAX_BYTES = 700 * 1024

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
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  tooLarge.value = file.size > MAX_BYTES
  // Cleared, so picking the same file again after a refusal still counts as a change.
  input.value = ''
  if (!tooLarge.value) image.value = await readAsDataUrl(file)
}
</script>

<template>
  <div>
    <span :id="labelId" class="mb-1 block text-sm font-medium text-gray-800">{{ label }}</span>
    <div class="flex items-start gap-4">
      <!-- One width for every size of preview, so the buttons of logo and favicon line up. -->
      <div class="flex w-16 shrink-0 justify-center">
        <div
          class="flex items-center justify-center overflow-hidden rounded-lg border border-line bg-surface p-1"
          :class="size === 'lg' ? 'h-16 w-16' : 'h-10 w-10'"
          :data-default="!custom || undefined"
        >
          <img :src="custom ?? defaultImage" alt="" class="max-h-full max-w-full object-contain" />
        </div>
      </div>
      <div class="flex min-w-0 flex-col items-start gap-1">
        <div class="flex items-center gap-3">
          <!-- A button of our own instead of the browser's file field ("Choose file / No file chosen"),
               which can't be styled; the field stays, invisible, for the keyboard and screen readers. -->
          <label
            class="cursor-pointer rounded-lg border border-line px-3 py-1.5 text-sm text-gray-700 focus-within:ring-2 focus-within:ring-blue-500 hover:bg-hover"
          >
            <input
              type="file"
              accept="image/*"
              :aria-labelledby="labelId"
              :aria-describedby="hintId"
              class="sr-only"
              @change="onChange"
            />
            {{ custom ? $t('app.changeImage') : $t('app.chooseImage') }}
          </label>
          <button v-if="custom" type="button" class="text-sm text-red-600 hover:underline" @click="image = null">
            {{ removeLabel }}
          </button>
        </div>
        <p v-if="tooLarge" role="alert" class="text-xs text-red-600">{{ $t('app.imageTooLarge') }}</p>
        <p v-if="!custom" class="text-xs text-gray-500">{{ defaultLabel }}</p>
        <p :id="hintId" class="text-xs text-gray-500">{{ hint }}</p>
      </div>
    </div>
  </div>
</template>
