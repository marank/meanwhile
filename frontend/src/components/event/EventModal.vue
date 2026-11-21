<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import * as api from '@/api'
import AppModal from '@/components/AppModal.vue'
import TabBar from '@/components/TabBar.vue'
import EventActivityTab from './EventActivityTab.vue'
import EventAvailabilityTab from './EventAvailabilityTab.vue'
import EventBookingStatus from './EventBookingStatus.vue'
import EventDetailsTab from './EventDetailsTab.vue'
import EventParticipantsTab from './EventParticipantsTab.vue'
import EventRecurrenceTab from './EventRecurrenceTab.vue'
import EventRemindersTab from './EventRemindersTab.vue'
import type { OccurrenceRef } from '@/services/occurrences'
import { formatDateTime } from '@/services/datetime'
import { errorMessage } from '@/services/errors'
import { hasRole } from '@/services/roles'
import { useAuthStore } from '@/stores/auth'
import { useCalendarChoices } from '@/composables/useCalendarChoices'
import { useEventAvailability } from '@/composables/useEventAvailability'
import { useEventParticipants, useEventReminders } from '@/composables/useEventExtras'
import { useEventForm } from '@/composables/useEventForm'
import { useEventSave } from '@/composables/useEventSave'
import { useTallestHeight } from '@/composables/useTallestHeight'

type Tab = 'details' | 'recurrence' | 'reminders' | 'participants' | 'availability' | 'activity'

const props = defineProps<{
  /** Target calendar for new events; existing events are loaded from their own calendar. */
  calendarId?: string
  eventId?: string | null
  /** The occurrence that was opened, when the event is a series. */
  occurrence?: OccurrenceRef | null
  defaultStart?: Date
  defaultEnd?: Date
  defaultAllDay?: boolean
}>()

const emit = defineEmits<{
  saved: []
  cancel: []
  deleted: []
}>()

const auth = useAuthStore()
const { t } = useI18n()

const statusLabels: Partial<Record<api.EventStatus, string>> = {
  pending: 'booking.pending',
  approved: 'booking.approved',
  rejected: 'booking.rejected',
  cancelled: 'booking.cancelled',
}
const statusClasses: Partial<Record<api.EventStatus, string>> = {
  pending: 'text-amber-600 dark:text-amber-400',
  approved: 'text-green-600 dark:text-green-400',
  rejected: 'text-red-600 dark:text-red-400',
  cancelled: 'text-gray-500',
}

const calendar = ref<api.Calendar | null>(null)
const event = ref<api.Event | null>(null)
const activeTab = ref<Tab>('details')

const {
  form,
  showRecurrenceCount,
  recurrence,
  foreignRrule,
  slot,
  endBeforeStart,
  bookedResourceIds,
  resourceRequiresApproval,
  locationRequiresApproval,
  fillFromEvent,
  fillFromOccurrence,
  fillDefaults,
  loadRrule,
  onResourceSelect,
  onLocationSelect,
  eventInput,
} = useEventForm()
const participants = useEventParticipants()
const { saved: savedParticipants, pending: pendingParticipants, removedIds: removedParticipantIds } = participants
const reminders = useEventReminders()
const { minutes: reminderMinutes, valid: remindersValid, changed: remindersChanged } = reminders
const availability = useEventAvailability({
  participants: participants.current,
  resourceIds: bookedResourceIds,
  slot,
})
const { people: availabilityPeople, cache: availabilityCache } = availability
const choices = useCalendarChoices()
const { hasCategories, hasResources } = choices

/** The activity tab is loaded once, when first opened, and kept while the dialog is open. */
const activityOpened = ref(false)
watch(activeTab, (tab) => {
  if (tab === 'activity') activityOpened.value = true
})

// Tabs differ in height; the dialog keeps the tallest one's height, so it doesn't jump while switching.
const { el: panel, minHeight: panelMinHeight } = useTallestHeight(activeTab)

/** A changed occurrence of a series: it repeats with the series, not on its own. */
const isException = computed(() => !!event.value?.parent_id)
/** An occurrence of a series was opened; changes ask which occurrences they apply to. */
const seriesOccurrence = computed(() => (event.value?.rrule ? (props.occurrence ?? null) : null))

const tabLabels: Record<Tab, () => string> = {
  details: () => t('event.details'),
  recurrence: () => t('event.recurrence'),
  reminders: () => t('reminders.title'),
  participants: () => t('event.participants'),
  availability: () => t('availability.title'),
  activity: () => t('event.activity'),
}

const tabs = computed(() =>
  (['details', 'recurrence', 'reminders', 'participants', 'availability', 'activity'] as const)
    .filter((id) => id !== 'activity' || props.eventId)
    .filter((id) => id !== 'recurrence' || !isException.value)
    .map((id) => ({ id, label: tabLabels[id]() })),
)

const myRole = computed(() => calendar.value?.my_membership?.role ?? null)
const isCalendarEditor = computed(() => hasRole(myRole.value, 'full'))
// As the backend decides: with "own" access only one's own events, with less ("read") none.
const canModify = computed(
  () =>
    !event.value ||
    isCalendarEditor.value ||
    (hasRole(myRole.value, 'own') && event.value.creator_id === auth.user?.id),
)
const forceAllDay = computed(() => !!calendar.value?.force_all_day)
// Only bookings (events with a resource) go through approval, so only they show a status.
const bookingStatus = computed(() => {
  const booking = event.value?.resource_id ?? event.value?.location_resource_id
  const status = booking ? event.value!.status : null
  return status && statusLabels[status] ? status : null
})

const { busy, error, save, remove, decide } = useEventSave({
  calendar,
  event,
  eventId: () => props.eventId,
  seriesOccurrence,
  isException,
  canModify,
  valid: () => !endBeforeStart.value && remindersValid.value,
  eventInput,
  participants,
  reminders,
  onSaved: () => emit('saved'),
  onDeleted: () => emit('deleted'),
})

// The dialog opens once its calendar is there, so it doesn't flash up small with only "Loading…" in it
// first; only a slow answer shows it before then.
const SHOW_LOADING_AFTER_MS = 300
const loadingShown = ref(false)
const loadingTimer = setTimeout(() => (loadingShown.value = true), SHOW_LOADING_AFTER_MS)
onBeforeUnmount(() => clearTimeout(loadingTimer))
const ready = computed(() => !!calendar.value || !!error.value || loadingShown.value)

/** Loads the event (when editing) and its calendar; false when that failed or there is no calendar. */
async function loadCalendar(): Promise<boolean> {
  try {
    if (props.eventId) event.value = await api.getEvent(props.eventId)
    const calendarId = event.value?.calendar_id ?? props.calendarId
    if (!calendarId) return false
    // Along with the calendar, so the dialog opens with the fields it will keep.
    ;[calendar.value] = await Promise.all([api.getCalendar(calendarId), choices.load(calendarId)])
    return true
  } catch (e) {
    error.value = errorMessage(e, t('app.loadFailed'))
    return false
  }
}

function fillForm() {
  if (event.value) fillFromEvent(event.value, forceAllDay.value)
  else if (props.defaultStart)
    fillDefaults(props.defaultStart, props.defaultEnd, forceAllDay.value || !!props.defaultAllDay)
  if (seriesOccurrence.value) fillFromOccurrence(seriesOccurrence.value)
}

onMounted(async () => {
  if (!(await loadCalendar())) return
  fillForm()
  // Shown early, the dialog had no title field to focus yet.
  if (loadingShown.value)
    void nextTick(() => panel.value?.querySelector<HTMLElement>('[data-autofocus]:not(:disabled)')?.focus())
  if (event.value?.rrule) loadRrule(event.value.rrule)
  if (event.value) {
    const eventId = event.value.id
    await Promise.all([reminders.load(eventId), participants.load(eventId)])
  }
  if (form.startDate) availability.preload(event.value?.id)
})
</script>

<template>
  <AppModal
    :open="ready"
    size="2xl"
    fullscreen-on-phone
    :dismissible="false"
    :title="eventId ? $t('event.edit') : $t('event.add')"
    @close="emit('cancel')"
  >
    <template v-if="bookingStatus" #header>
      <span class="text-lg text-gray-300" aria-hidden="true">|</span>
      <span class="text-lg font-semibold" :class="statusClasses[bookingStatus]" role="status">
        {{ $t(statusLabels[bookingStatus]!) }}
      </span>
    </template>
    <TabBar
      :tabs="tabs"
      :active="activeTab"
      class="mb-3 max-sm:-mx-4 max-sm:px-1 sm:mb-5"
      @select="activeTab = $event"
    />

    <EventBookingStatus
      v-if="bookingStatus && event"
      :booked-event="event"
      :status="bookingStatus"
      :busy="busy"
      @decide="decide"
    />

    <p
      v-if="isException"
      class="mb-4 rounded-lg border border-line bg-surface-muted px-3 py-2 text-sm text-gray-700"
      role="status"
    >
      {{ $t('series.exceptionHint') }}
    </p>

    <p
      v-if="error"
      class="mb-4 rounded bg-red-50 p-2 text-sm text-red-600 dark:bg-red-900 dark:text-red-200"
      role="alert"
    >
      {{ error }}
    </p>

    <div v-if="calendar" ref="panel" :style="panelMinHeight ? { minHeight: `${panelMinHeight}px` } : undefined">
      <!-- Kept once opened, so its comments and history aren't loaded again on every visit. -->
      <EventActivityTab
        v-if="activityOpened && eventId"
        v-show="activeTab === 'activity'"
        :event-id="eventId"
        :can-comment="myRole !== null && myRole !== 'read'"
        :can-moderate="isCalendarEditor"
      />

      <EventAvailabilityTab
        v-if="activeTab === 'availability'"
        :event-id="event?.id ?? null"
        :start="slot.start"
        :end="slot.end"
        :people="availabilityPeople"
        :resource-ids="bookedResourceIds"
        :cache="availabilityCache"
      />

      <!-- Outside the fieldset: everyone who sees the event may be reminded of it. -->
      <EventRemindersTab
        v-else-if="activeTab === 'reminders'"
        v-model="reminderMinutes"
        v-model:valid="remindersValid"
        :all-day="form.allDay"
      />

      <fieldset v-else class="contents" :disabled="!canModify">
        <EventDetailsTab
          v-if="activeTab === 'details'"
          v-model:form="form"
          :calendar-id="calendar.id"
          :force-all-day="forceAllDay"
          :end-before-start="endBeforeStart"
          :location-requires-approval="locationRequiresApproval"
          :resource-requires-approval="resourceRequiresApproval"
          :has-categories="hasCategories"
          :has-resources="hasResources"
          @select-location="onLocationSelect"
          @select-resource="onResourceSelect"
        />

        <EventRecurrenceTab
          v-else-if="activeTab === 'recurrence'"
          v-model:rule="recurrence"
          v-model:foreign="foreignRrule"
          v-model:show-count="showRecurrenceCount"
          :start="form.startDate"
        />

        <EventParticipantsTab
          v-else-if="activeTab === 'participants'"
          v-model:pending="pendingParticipants"
          v-model:removed="removedParticipantIds"
          v-model:participants="savedParticipants"
          :event-id="eventId"
          :can-manage="canModify"
        />
      </fieldset>
    </div>
    <p v-else-if="!error" class="text-sm text-gray-500">{{ $t('app.loading') }}</p>

    <p v-if="event" class="mt-4 text-xs text-gray-500 sm:mt-6">
      {{
        $t('event.createdBy', {
          name: event.creator_name || event.creator_email || '',
          date: formatDateTime(event.created_at),
        })
      }}<span v-if="formatDateTime(event.updated_at) !== formatDateTime(event.created_at)"
        >, {{ $t('event.editedBy', { date: formatDateTime(event.updated_at) }) }}</span
      >
    </p>

    <template #footer>
      <div class="flex items-center justify-between">
        <button
          v-if="event && canModify"
          type="button"
          :disabled="busy"
          class="text-sm text-red-600 hover:underline"
          @click="remove"
        >
          {{ $t('app.delete') }}
        </button>
        <span v-else></span>
        <div class="flex gap-3">
          <button type="button" class="rounded-lg border border-line px-4 py-2 hover:bg-hover" @click="emit('cancel')">
            {{ $t('app.cancel') }}
          </button>
          <button
            v-if="canModify || remindersChanged"
            type="button"
            :disabled="busy || !calendar || endBeforeStart || !remindersValid"
            class="rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
            @click="save"
          >
            {{ $t('app.save') }}
          </button>
        </div>
      </div>
    </template>
  </AppModal>
</template>
