<script setup lang="ts">
import { Bell, CircleCheck, CircleX, X } from 'lucide-vue-next'
import { dismissToast, toasts, type ToastTone } from '@/services/toast'

const toneClasses: Record<ToastTone, string> = {
  success: 'border-green-200 text-green-800',
  error: 'border-red-200 text-red-800',
  info: 'border-blue-200 text-blue-800',
}
</script>

<template>
  <div
    class="pointer-events-none fixed inset-x-4 top-4 z-[100] flex flex-col items-end gap-2 sm:left-auto sm:w-96"
    aria-live="polite"
  >
    <TransitionGroup name="toast">
      <div
        v-for="item in toasts"
        :key="item.id"
        class="pointer-events-auto flex w-full items-start gap-3 rounded-lg border bg-surface p-4 shadow-lg"
        :class="toneClasses[item.tone]"
        role="status"
      >
        <CircleCheck v-if="item.tone === 'success'" class="mt-0.5 shrink-0" :size="20" />
        <Bell v-else-if="item.tone === 'info'" class="mt-0.5 shrink-0" :size="20" />
        <CircleX v-else class="mt-0.5 shrink-0" :size="20" />
        <p class="flex-1 text-sm font-medium">{{ item.message }}</p>
        <button
          type="button"
          class="rounded p-0.5 hover:bg-hover"
          :aria-label="$t('app.close')"
          @click="dismissToast(item.id)"
        >
          <X :size="18" />
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition:
    opacity 150ms ease,
    transform 150ms ease;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(-0.5rem);
}
</style>
