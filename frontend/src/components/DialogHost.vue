<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import AppModal from './AppModal.vue'
import { dialog, inputValue, submitDialog } from '@/services/dialog'

const inputRef = ref<HTMLInputElement | null>(null)

watch(
  () => dialog.open,
  (open) => {
    if (open && dialog.kind === 'prompt') {
      nextTick(() => inputRef.value?.focus())
    }
  },
)

function cancel() {
  submitDialog(dialog.kind === 'confirm' ? false : null)
}

function ok() {
  if (dialog.kind === 'confirm') submitDialog(true)
  else if (dialog.kind === 'prompt') submitDialog(inputValue.value)
  else submitDialog()
}
</script>

<template>
  <AppModal
    always-on-top
    :open="dialog.open"
    :title="dialog.title || (dialog.kind === 'alert' ? $t('app.notice') : $t('app.confirm'))"
    @close="cancel"
  >
    <p class="text-gray-700">{{ dialog.message }}</p>

    <div v-if="dialog.kind === 'prompt'" class="mt-4">
      <input
        ref="inputRef"
        v-model="inputValue"
        type="text"
        class="w-full rounded-lg border px-3 py-2"
        @keydown.enter="ok"
      />
    </div>

    <template #footer>
      <div class="flex justify-end gap-3">
        <button
          v-if="dialog.kind !== 'alert'"
          type="button"
          class="px-4 py-2 rounded-lg border border-line hover:bg-hover"
          @click="cancel"
        >
          {{ dialog.kind === 'prompt' ? $t('app.cancel') : $t('app.no') }}
        </button>
        <button type="button" class="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700" @click="ok">
          {{ dialog.kind === 'confirm' ? $t('app.yes') : $t('app.ok') }}
        </button>
      </div>
    </template>
  </AppModal>
</template>
