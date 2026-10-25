<script setup lang="ts">
import { ref } from 'vue'
import type * as api from '@/api'

/** Where a booking (an event with a resource) stands, and the approval for those who decide on it. */
defineProps<{
  bookedEvent: api.Event
  status: api.EventStatus
  busy: boolean
}>()

const emit = defineEmits<{
  decide: [action: 'approve' | 'reject', note: string]
}>()

const decisionNote = ref('')
</script>

<template>
  <div class="mb-4 text-sm text-gray-600">
    <p v-if="status === 'pending' && bookedEvent.awaiting_approval.length" class="text-xs">
      {{ $t('booking.awaiting', { names: bookedEvent.awaiting_approval.join(', ') }) }}
    </p>
    <p v-if="status === 'pending'" class="mt-0.5 text-xs">{{ $t('booking.pendingHint') }}</p>
    <p v-else-if="bookedEvent.decision_note" class="text-xs">„{{ bookedEvent.decision_note }}“</p>
    <div v-if="bookedEvent.can_decide" class="mt-2 flex flex-col gap-2 sm:flex-row">
      <input
        v-model="decisionNote"
        :placeholder="$t('booking.notePlaceholder')"
        class="min-w-0 flex-1 rounded-lg border px-2 py-1 text-sm"
      />
      <div class="flex gap-2">
        <button
          type="button"
          :disabled="busy"
          class="rounded-lg bg-green-600 px-3 py-1 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
          @click="emit('decide', 'approve', decisionNote)"
        >
          {{ $t('booking.approve') }}
        </button>
        <button
          type="button"
          :disabled="busy"
          class="rounded-lg bg-red-600 px-3 py-1 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
          @click="emit('decide', 'reject', decisionNote)"
        >
          {{ $t('booking.reject') }}
        </button>
      </div>
    </div>
  </div>
</template>
