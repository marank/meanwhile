<script setup lang="ts">
import { computed, onMounted, reactive, ref, useId } from 'vue'
import { useI18n } from 'vue-i18n'
import * as api from '@/api'
import AppModal from '@/components/AppModal.vue'
import SearchableSelect from '@/components/SearchableSelect.vue'
import TabBar from '@/components/TabBar.vue'
import EventActivityTab from './EventActivityTab.vue'
import EventParticipantsTab, { type PendingParticipant } from './EventParticipantsTab.vue'
import EventRecurrenceTab from './EventRecurrenceTab.vue'
import { confirm } from '@/services/dialog'
import { browserTimeZone, formatDateTime, toDateInputValue, toTimeInputValue } from '@/services/datetime'
import { bookingErrorMessage, errorMessage } from '@/services/errors'
import { buildRrule, parseRrule, recurrenceDefaults, type RecurrenceRule } from '@/services/rrule'
import { useAuthStore } from '@/stores/auth'

type Tab = 'details' | 'recurrence' | 'participants' | 'activity'

const HOUR_MS = 60 * 60 * 1000

const props = defineProps<{
  /** Target calendar for new events; existing events are loaded from their own calendar. */
  calendarId?: string
  eventId?: string | null
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
  pending: 'border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-100',
  approved: 'border-green-300 bg-green-50 text-green-900 dark:border-green-800 dark:bg-green-950 dark:text-green-100',
  rejected: 'border-red-300 bg-red-50 text-red-900 dark:border-red-800 dark:bg-red-950 dark:text-red-100',
  cancelled: 'border-line bg-surface-muted text-gray-700',
}

const calendar = ref<api.Calendar | null>(null)
const event = ref<api.Event | null>(null)
const busy = ref(false)
const error = ref('')
const decisionNote = ref('')
const activeTab = ref<Tab>('details')

const form = reactive({
  title: '',
  description: '',
  allDay: false,
  startDate: '',
  startTime: '09:00',
  endDate: '',
  endTime: '10:00',
  categoryId: null as string | null,
  resourceId: null as string | null,
})
const fieldId = useId()
const selectedResource = ref<api.SearchResult | null>(null)
const showRecurrenceCount = ref(false)
/** The recurrence as the editor shows it; null when the event doesn't repeat. */
const recurrence = ref<RecurrenceRule | null>(null)
/** A rule from another client that the editor can't show; sent back unchanged. */
const foreignRrule = ref<string | null>(null)
// The loaded rule as the editor would write it: if nothing changed, the original is sent back as it was.
let loadedRrule: string | null = null
const pendingParticipants = ref<PendingParticipant[]>([])

const tabs = computed(() =>
  (['details', 'recurrence', 'participants', 'activity'] as const)
    .filter((id) => id !== 'activity' || props.eventId)
    .map((id) => ({ id, label: t(`event.${id}`) })),
)

const myRole = computed(() => calendar.value?.my_membership?.role ?? null)
const isCalendarEditor = computed(() => myRole.value === 'owner' || myRole.value === 'editor')
const canModify = computed(() => !event.value || isCalendarEditor.value || event.value.creator_id === auth.user?.id)
const forceAllDay = computed(() => !!calendar.value?.force_all_day)
// Only bookings (events with a resource) go through approval, so only they show a status.
const bookingStatus = computed(() => {
  const status = event.value?.resource_id ? event.value.status : null
  return status && statusLabels[status] ? status : null
})
const resourceRequiresApproval = computed(() => selectedResource.value?.meta?.requires_approval === true)
const endBeforeStart = computed(() => {
  if (!form.startDate || !form.endDate) return false
  if (form.allDay) return form.endDate < form.startDate
  return `${form.endDate}T${form.endTime}` < `${form.startDate}T${form.startTime}`
})

onMounted(async () => {
  try {
    if (props.eventId) event.value = await api.getEvent(props.eventId)
    const calendarId = event.value?.calendar_id ?? props.calendarId
    if (!calendarId) return
    calendar.value = await api.getCalendar(calendarId)
  } catch (e) {
    error.value = errorMessage(e, t('app.loadFailed'))
    return
  }
  if (event.value) fillFromEvent(event.value)
  else if (props.defaultStart) fillDefaults(props.defaultStart)
  if (event.value?.rrule) loadRrule(event.value.rrule)
})

function setLocalRange(start: Date, end: Date) {
  form.startDate = toDateInputValue(start)
  form.startTime = toTimeInputValue(start)
  form.endDate = toDateInputValue(end)
  form.endTime = toTimeInputValue(end)
}

function fillFromEvent(value: api.Event) {
  form.title = value.title
  form.description = value.description || ''
  form.allDay = forceAllDay.value || value.all_day
  if (form.allDay) {
    // All-day events are stored as UTC midnights, so the UTC date is the calendar date.
    form.startDate = value.start.slice(0, 10)
    form.endDate = value.end.slice(0, 10)
  } else {
    setLocalRange(new Date(value.start), new Date(value.end))
  }
  form.categoryId = value.category_id
  form.resourceId = value.resource_id
  showRecurrenceCount.value = value.show_recurrence_count
}

function fillDefaults(start: Date) {
  form.allDay = forceAllDay.value || !!props.defaultAllDay
  setLocalRange(start, props.defaultEnd ?? new Date(start.getTime() + HOUR_MS))
}

function loadRrule(value: string) {
  recurrence.value = parseRrule(value, recurrenceDefaults(new Date(`${form.startDate}T00:00:00`)))
  if (recurrence.value) loadedRrule = buildRrule(recurrence.value)
  else foreignRrule.value = value
}

function currentRrule(): string | null {
  if (foreignRrule.value) return foreignRrule.value
  const rule = buildRrule(recurrence.value)
  // Writing an unchanged rule differently (e.g. spelling out the day of month) would count as a change.
  return rule !== null && rule === loadedRrule ? event.value!.rrule : rule
}

function onResourceSelect(_value: string | null, option: api.SearchResult | null) {
  selectedResource.value = option
}

function eventInput(): api.EventInput {
  const toDate = (date: string, time: string) =>
    form.allDay ? new Date(`${date}T00:00:00.000Z`) : new Date(`${date}T${time}`)
  const rrule = currentRrule()
  return {
    title: form.title,
    description: form.description || null,
    start: toDate(form.startDate, form.startTime).toISOString(),
    end: toDate(form.endDate, form.endTime).toISOString(),
    all_day: form.allDay,
    timezone: browserTimeZone(),
    show_recurrence_count: rrule !== null && showRecurrenceCount.value,
    rrule,
    category_id: form.categoryId,
    resource_id: form.resourceId,
  }
}

async function submit(action: () => Promise<unknown>, done: () => void) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    await action()
    done()
  } catch (e) {
    error.value = bookingErrorMessage(e)
  } finally {
    busy.value = false
  }
}

async function save() {
  const target = calendar.value
  if (!target || endBeforeStart.value) return
  await submit(
    async () => {
      if (props.eventId) {
        await api.updateEvent(props.eventId, eventInput())
      } else {
        await api.createEvent(target.id, {
          ...eventInput(),
          participants: pendingParticipants.value.map(({ user_id, email, status }) => ({ user_id, email, status })),
        })
      }
    },
    () => emit('saved'),
  )
}

async function remove() {
  const eventId = props.eventId
  if (!eventId || !(await confirm(t('app.deleteEventText'), t('app.deleteEventTitle')))) return
  await submit(
    () => api.deleteEvent(eventId),
    () => emit('deleted'),
  )
}

async function decide(action: 'approve' | 'reject') {
  const eventId = props.eventId
  if (!eventId) return
  const note = decisionNote.value.trim() || undefined
  await submit(
    () => (action === 'approve' ? api.approveEvent(eventId, note) : api.rejectEvent(eventId, note)),
    () => emit('saved'),
  )
}
</script>

<template>
  <AppModal
    open
    size="xl"
    :dismissible="false"
    :title="eventId ? $t('app.edit') : $t('app.add')"
    @close="emit('cancel')"
  >
    <TabBar :tabs="tabs" :active="activeTab" class="mb-5" @select="activeTab = $event" />

    <div
      v-if="bookingStatus"
      class="mb-4 rounded-lg border px-3 py-2 text-sm"
      :class="statusClasses[bookingStatus]"
      role="status"
    >
      <p class="font-medium">{{ $t(statusLabels[bookingStatus]!) }}</p>
      <p v-if="bookingStatus === 'pending'" class="mt-0.5 text-xs opacity-80">{{ $t('booking.pendingHint') }}</p>
      <p v-else-if="event?.decision_note" class="mt-0.5 text-xs opacity-80">„{{ event.decision_note }}“</p>
      <div v-if="event?.can_decide" class="mt-2 flex flex-col gap-2 sm:flex-row">
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
            @click="decide('approve')"
          >
            {{ $t('booking.approve') }}
          </button>
          <button
            type="button"
            :disabled="busy"
            class="rounded-lg bg-red-600 px-3 py-1 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
            @click="decide('reject')"
          >
            {{ $t('booking.reject') }}
          </button>
        </div>
      </div>
    </div>

    <p
      v-if="error"
      class="mb-4 rounded bg-red-50 p-2 text-sm text-red-600 dark:bg-red-900 dark:text-red-200"
      role="alert"
    >
      {{ error }}
    </p>

    <template v-if="calendar">
      <EventActivityTab
        v-if="activeTab === 'activity' && eventId"
        :event-id="eventId"
        :can-comment="myRole !== null && myRole !== 'viewer'"
        :can-moderate="isCalendarEditor"
      />

      <fieldset v-else class="contents" :disabled="!canModify">
        <div v-if="activeTab === 'details'" class="space-y-3">
          <label class="block">
            <span class="block text-sm font-medium text-gray-700">{{ $t('event.title') }}</span>
            <input v-model="form.title" class="mt-1 w-full rounded-lg border px-3 py-2" />
          </label>

          <label class="block">
            <span class="block text-sm font-medium text-gray-700">{{ $t('event.description') }}</span>
            <textarea v-model="form.description" class="mt-1 w-full rounded-lg border px-3 py-2" rows="2"></textarea>
          </label>

          <div>
            <label class="flex items-center gap-2 text-sm">
              <input v-model="form.allDay" type="checkbox" :disabled="forceAllDay" />
              {{ $t('event.allDay') }}
            </label>
            <p v-if="forceAllDay" class="mt-1 text-xs text-gray-500">{{ $t('event.allDayRequired') }}</p>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label :for="`${fieldId}-start`" class="block text-xs font-medium text-gray-700">{{
                $t('event.start')
              }}</label>
              <input
                :id="`${fieldId}-start`"
                v-model="form.startDate"
                type="date"
                class="mt-1 w-full rounded-lg border px-2 py-1"
              />
              <input
                v-if="!form.allDay"
                v-model="form.startTime"
                type="time"
                :aria-label="`${$t('event.start')} (${$t('event.time')})`"
                class="mt-1 w-full rounded-lg border px-2 py-1"
              />
            </div>
            <div>
              <label :for="`${fieldId}-end`" class="block text-xs font-medium text-gray-700">{{
                $t('event.end')
              }}</label>
              <input
                :id="`${fieldId}-end`"
                v-model="form.endDate"
                type="date"
                :aria-invalid="endBeforeStart"
                class="mt-1 w-full rounded-lg border px-2 py-1"
              />
              <input
                v-if="!form.allDay"
                v-model="form.endTime"
                type="time"
                :aria-label="`${$t('event.end')} (${$t('event.time')})`"
                :aria-invalid="endBeforeStart"
                class="mt-1 w-full rounded-lg border px-2 py-1"
              />
            </div>
          </div>
          <p v-if="endBeforeStart" class="text-xs text-red-600" role="alert">{{ $t('event.endBeforeStart') }}</p>

          <div>
            <label :for="`${fieldId}-category`" class="block text-sm font-medium text-gray-700">{{
              $t('event.category')
            }}</label>
            <SearchableSelect
              v-model="form.categoryId"
              :input-id="`${fieldId}-category`"
              entity="categories"
              :calendar-id="calendar.id"
              open-on-focus
              clearable
              class="mt-1"
              :placeholder="$t('event.noCategory')"
            />
          </div>

          <div>
            <label :for="`${fieldId}-resource`" class="block text-sm font-medium text-gray-700">{{
              $t('event.bookResource')
            }}</label>
            <SearchableSelect
              v-model="form.resourceId"
              :input-id="`${fieldId}-resource`"
              entity="resources"
              :calendar-id="calendar.id"
              open-on-focus
              clearable
              class="mt-1"
              :placeholder="$t('event.noResource')"
              @select="onResourceSelect"
            />
            <p v-if="resourceRequiresApproval" class="mt-1 text-xs text-amber-600">
              {{ $t('event.resourceRequiresApproval') }}
            </p>
          </div>
        </div>

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
          :event-id="eventId"
          :can-manage="canModify"
        />
      </fieldset>
    </template>
    <p v-else-if="!error" class="text-sm text-gray-500">{{ $t('app.loading') }}</p>

    <p v-if="event" class="mt-6 text-xs text-gray-500">
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
            v-if="canModify"
            type="button"
            :disabled="busy || !calendar || endBeforeStart"
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
