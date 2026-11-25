<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import * as api from '@/api'
import AppModal from '@/components/AppModal.vue'
import AppSelect from '@/components/AppSelect.vue'
import AppSwitch from '@/components/AppSwitch.vue'
import { toDateInputValue, toTimeInputValue } from '@/services/datetime'
import { bookingErrorMessage } from '@/services/errors'
import type { OccurrenceRef } from '@/services/occurrences'
import { hasRole } from '@/services/roles'
import { useCalendarStore } from '@/stores/calendars'

/** Where and when a copy of the event goes; the copy is made as the event was last saved. */
const props = defineProps<{
  event: api.Event
  /** The occurrence of a series that was opened; the copy starts on its day by default. */
  occurrence?: OccurrenceRef | null
  hasParticipants: boolean
}>()

const emit = defineEmits<{
  done: [copy: api.Event]
  cancel: []
}>()

const { t } = useI18n()
const calendarStore = useCalendarStore()

/** The calendars one may add events to. */
const calendars = computed(() =>
  calendarStore.items.filter((item) => hasRole(item.membership.role, 'own')).map((item) => item.calendar),
)

const calendarId = ref(
  calendars.value.find((calendar) => calendar.id === props.event.calendar_id)?.id ?? calendars.value[0]?.id ?? '',
)
const otherCalendar = computed(() => calendarId.value !== props.event.calendar_id)
const isSeries = computed(() => !!props.event.rrule && !props.event.parent_id)

const start = props.occurrence?.start ?? props.event.start
// All-day events by their UTC date, as stored; timed ones in local time.
const date = ref(props.event.all_day ? start.slice(0, 10) : toDateInputValue(new Date(start)))
const time = ref(toTimeInputValue(new Date(start)))
const invite = ref(false)

const busy = ref(false)
const error = ref('')

async function submit() {
  if (busy.value || !calendarId.value || !date.value) return
  busy.value = true
  error.value = ''
  try {
    const copy = await api.duplicateEvent(props.event.id, {
      calendar_id: calendarId.value,
      start: props.event.all_day
        ? `${date.value}T00:00:00.000Z`
        : new Date(`${date.value}T${time.value}`).toISOString(),
      invite_participants: props.hasParticipants && invite.value,
    })
    emit('done', copy)
  } catch (e) {
    error.value = bookingErrorMessage(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <AppModal open :title="t('duplicate.title')" always-on-top @close="emit('cancel')">
    <form id="duplicate-event" class="space-y-4" @submit.prevent="submit">
      <p v-if="error" class="rounded bg-red-50 p-2 text-sm text-red-600 dark:bg-red-900 dark:text-red-200" role="alert">
        {{ error }}
      </p>
      <p v-if="!calendars.length" class="text-sm text-gray-500">{{ t('duplicate.noCalendar') }}</p>
      <template v-else>
        <label class="block">
          <span class="block text-sm font-medium text-gray-700">{{ t('duplicate.calendar') }}</span>
          <AppSelect
            v-model="calendarId"
            :options="calendars.map((calendar) => ({ value: calendar.id, label: calendar.name }))"
            class="mt-1"
          />
        </label>
        <div class="flex gap-3">
          <label class="block flex-1">
            <span class="block text-sm font-medium text-gray-700">{{ t('duplicate.date') }}</span>
            <input v-model="date" type="date" required class="mt-1 w-full rounded-lg border px-2 py-1.5" />
          </label>
          <label v-if="!event.all_day" class="block">
            <span class="block text-sm font-medium text-gray-700">{{ t('duplicate.time') }}</span>
            <input v-model="time" type="time" required class="mt-1 w-28 rounded-lg border px-2 py-1.5" />
          </label>
        </div>
        <div v-if="hasParticipants" class="space-y-1">
          <AppSwitch v-model="invite" :label="t('duplicate.inviteParticipants')" />
          <p class="text-xs text-gray-500">{{ t('duplicate.inviteHint') }}</p>
        </div>
        <ul class="list-disc space-y-1 pl-4 text-xs text-gray-500">
          <li>{{ t('duplicate.hint') }}</li>
          <li v-if="isSeries">{{ t('duplicate.seriesHint') }}</li>
          <li v-if="otherCalendar">{{ t('duplicate.otherCalendarHint') }}</li>
        </ul>
      </template>
    </form>
    <template #footer>
      <div class="flex justify-end gap-3">
        <button type="button" class="rounded-lg border border-line px-4 py-2 hover:bg-hover" @click="emit('cancel')">
          {{ t('app.cancel') }}
        </button>
        <button
          type="submit"
          form="duplicate-event"
          :disabled="busy || !calendars.length || !date"
          class="rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {{ t('duplicate.submit') }}
        </button>
      </div>
    </template>
  </AppModal>
</template>
