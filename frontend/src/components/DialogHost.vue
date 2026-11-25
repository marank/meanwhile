<script setup lang="ts">
import { useId } from 'vue'
import AppModal from './AppModal.vue'
import { dialog, inputValue, submitDialog } from '@/services/dialog'

// Names the prompt's field after the question it answers.
const messageId = useId()

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
    <p :id="messageId" class="text-gray-700">{{ dialog.message }}</p>

    <div v-if="dialog.kind === 'choice'" class="mt-4 flex flex-col gap-2">
      <button
        v-for="choice in dialog.choices"
        :key="choice.value"
        type="button"
        class="rounded-lg border border-line px-4 py-2 text-left hover:bg-hover"
        @click="submitDialog(choice.value)"
      >
        {{ choice.label }}
      </button>
    </div>

    <div v-if="dialog.kind === 'prompt'" class="mt-4">
      <!-- AppModal focuses it when the dialog opens. Enter's default is prevented: closing returns focus
           to the button that opened the prompt, which the same key press would otherwise press again. -->
      <input
        v-model="inputValue"
        type="text"
        :aria-labelledby="messageId"
        class="w-full rounded-lg border px-3 py-2"
        @keydown.enter.prevent="ok"
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
          {{ dialog.kind === 'confirm' ? $t('app.no') : $t('app.cancel') }}
        </button>
        <button
          v-if="dialog.kind !== 'choice'"
          type="button"
          class="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700"
          @click="ok"
        >
          {{ dialog.kind === 'confirm' ? $t('app.yes') : $t('app.ok') }}
        </button>
      </div>
    </template>
  </AppModal>
</template>
