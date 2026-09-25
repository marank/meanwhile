<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import Modal from './Modal.vue'
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
  if (dialog.kind === 'confirm') {
    submitDialog(false)
  } else {
    submitDialog(null)
  }
}

function ok() {
  if (dialog.kind === 'alert') {
    submitDialog(undefined)
  } else if (dialog.kind === 'confirm') {
    submitDialog(true)
  } else {
    submitDialog(inputValue.value)
  }
}
</script>

<template>
  <Modal
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
        class="w-full border border-gray-300 rounded-lg px-3 py-2"
        @keydown.enter="ok"
      />
    </div>

    <template #footer>
      <div class="flex justify-end gap-3">
        <button
          v-if="dialog.kind !== 'alert'"
          @click="cancel"
          class="px-4 py-2 rounded-lg border border-gray-300 hover:bg-gray-100"
        >
          {{ dialog.kind === 'prompt' ? $t('app.cancel') : $t('app.no') }}
        </button>
        <button
          @click="ok"
          class="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700"
        >
          {{ dialog.kind === 'alert' ? $t('app.ok') : dialog.kind === 'prompt' ? $t('app.ok') : $t('app.yes') }}
        </button>
      </div>
    </template>
  </Modal>
</template>
