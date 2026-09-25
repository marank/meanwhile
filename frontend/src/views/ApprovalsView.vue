<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import * as api from '@/api'

const auth = useAuthStore()
const events = ref<api.Event[]>([])
const busy = ref(false)

onMounted(load)

async function load() {
  if (!auth.token) return
  events.value = await api.listPendingApprovals(auth.token)
}

async function approve(event: api.Event) {
  if (!auth.token) return
  await api.approveEvent(auth.token, event.id)
  await load()
}

async function reject(event: api.Event) {
  if (!auth.token) return
  await api.rejectEvent(auth.token, event.id)
  await load()
}
</script>

<template>
  <div class="max-w-3xl mx-auto p-6">
    <h1 class="text-2xl font-bold text-gray-800 mb-4">{{ $t('app.approvals') }}</h1>
    <div v-if="events.length === 0" class="text-gray-500 bg-white rounded-xl border border-gray-200 p-8 text-center">
      No pending approvals.
    </div>
    <ul v-else class="space-y-3">
      <li v-for="event in events" :key="event.id" class="bg-white rounded-xl border border-gray-200 p-4">
        <div class="flex items-start justify-between">
          <div>
            <h3 class="font-semibold text-gray-800">{{ event.title }}</h3>
            <p class="text-sm text-gray-500">
              {{ new Date(event.start).toLocaleString() }} — {{ new Date(event.end).toLocaleString() }}
            </p>
            <p class="text-sm text-gray-600 mt-1">
              Resource: {{ event.resource_name || '—' }} · Calendar: {{ event.calendar_id }}
            </p>
          </div>
          <div class="flex gap-2">
            <button
              @click="approve(event)"
              :disabled="busy"
              class="px-3 py-1.5 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700 disabled:opacity-50"
            >
              {{ $t('event.approve') }}
            </button>
            <button
              @click="reject(event)"
              :disabled="busy"
              class="px-3 py-1.5 bg-red-600 text-white rounded-lg text-sm hover:bg-red-700 disabled:opacity-50"
            >
              {{ $t('event.reject') }}
            </button>
          </div>
        </div>
      </li>
    </ul>
  </div>
</template>
