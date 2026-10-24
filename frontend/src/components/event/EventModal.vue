<script setup lang="ts">
import { computed, onMounted, reactive, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import * as api from '@/api'
import AppModal from '@/components/AppModal.vue'
import SearchableSelect from '@/components/SearchableSelect.vue'
import TabBar from '@/components/TabBar.vue'
import EventActivityTab from './EventActivityTab.vue'
import EventAvailabilityTab from './EventAvailabilityTab.vue'
import AppSwitch from '@/components/AppSwitch.vue'
import EventParticipantsTab, { type PendingParticipant } from './EventParticipantsTab.vue'
import EventRecurrenceTab from './EventRecurrenceTab.vue'
import EventRemindersTab from './EventRemindersTab.vue'
import { confirm } from '@/services/dialog'
import { chooseScope, type OccurrenceRef } from '@/services/occurrences'
import { createAvailabilityCache, loadAvailability, startOfDay } from '@/services/availability'
import { browserTimeZone, formatDateTime, toDateInputValue, toTimeInputValue } from '@/services/datetime'
import { bookingErrorMessage, errorMessage } from '@/services/errors'
import { buildRrule, parseRrule, recurrenceDefaults, type RecurrenceRule } from '@/services/rrule'
import { hasRole } from '@/services/roles'
import { useAuthStore } from '@/stores/auth'

type Tab = 'details' | 'recurrence' | 'reminders' | 'participants' | 'availability' | 'activity'

const HOUR_MS = 60 * 60 * 1000
const DAY_MS = 24 * HOUR_MS

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
  /** Free text, or the name of the booked place in locationResourceId. */
  location: '',
  locationResourceId: null as string | null,
})
const fieldId = useId()
const selectedResource = ref<api.SearchResult | null>(null)
const selectedLocation = ref<api.SearchResult | null>(null)
const showRecurrenceCount = ref(false)
/** The recurrence as the editor shows it; null when the event doesn't repeat. */
const recurrence = ref<RecurrenceRule | null>(null)
/** A rule from another client that the editor can't show; sent back unchanged. */
const foreignRrule = ref<string | null>(null)
// The loaded rule as the editor would write it: if nothing changed, the original is sent back as it was.
let loadedRrule: string | null = null
/** Participants added in the dialog; sent when the event is saved. */
const pendingParticipants = ref<PendingParticipant[]>([])
/** Saved participants removed in the dialog; removed when the event is saved. */
const removedParticipantIds = ref<string[]>([])
/** The event's time as entered, for the availability view. */
const slot = computed(() => {
  if (form.allDay) {
    const start = new Date(`${form.startDate}T00:00:00`)
    const end = new Date(`${form.endDate || form.startDate}T00:00:00`)
    end.setDate(end.getDate() + 1)
    return { start, end }
  }
  return {
    start: new Date(`${form.startDate}T${form.startTime}`),
    end: new Date(`${form.endDate}T${form.endTime}`),
  }
})

/** The saved participants, loaded once with the event. */
const participants = ref<api.EventParticipant[] | null>(null)

/** Whose availability is shown: oneself and the participants who have an account. */
const availabilityPeople = computed(() => {
  const me = auth.user ? [{ id: auth.user.id, name: t('availability.me') }] : []
  const saved = (participants.value ?? []).filter((p) => !removedParticipantIds.value.includes(p.id))
  const others = [...saved, ...pendingParticipants.value]
    .filter((p) => p.user_id && p.user_id !== auth.user?.id)
    .map((p) => ({ id: p.user_id!, name: p.display_name || p.email }))
  return [...me, ...others]
})
const bookedResourceIds = computed(() => [form.locationResourceId, form.resourceId].filter((id): id is string => !!id))
const availabilityCache = createAvailabilityCache()

/** The availability tab finds the event's day ready when it is opened. */
function preloadAvailability() {
  if (!form.startDate) return
  const userIds = availabilityPeople.value.map((p) => p.id)
  if (userIds.length || bookedResourceIds.value.length) {
    loadAvailability(availabilityCache, startOfDay(slot.value.start), userIds, bookedResourceIds.value, event.value?.id)
  }
}

/** The activity tab is loaded once, when first opened, and kept while the dialog is open. */
const activityOpened = ref(false)
watch(activeTab, (tab) => {
  if (tab === 'activity') activityOpened.value = true
})

// Tabs differ in height; the dialog keeps the tallest one's height, so it doesn't jump while switching.
// At most as tall as fits without scrolling, though (phones), so short tabs don't scroll into emptiness.
const panel = ref<HTMLElement | null>(null)
const panelMinHeight = ref(0)
watch(
  activeTab,
  () => {
    const el = panel.value
    if (!el) return
    const scroller = el.closest<HTMLElement>('.overflow-y-auto')
    let fits = Infinity
    if (scroller) {
      // What the scrolling body shows besides the panel: the tabs above it, the note and padding below it.
      const top = el.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop
      const below = scroller.scrollHeight - top - el.offsetHeight
      fits = scroller.clientHeight - top - below
    }
    panelMinHeight.value = Math.min(Math.max(panelMinHeight.value, el.offsetHeight), fits)
  },
  { flush: 'pre' },
)

/** The current user's own reminders, in minutes before the start; saved with the event. */
const reminders = ref<number[]>([])
const remindersValid = ref(true)
let loadedReminders = ''
const remindersChanged = computed(() => reminders.value.join(',') !== loadedReminders)

/** A changed occurrence of a series: it repeats with the series, not on its own. */
const isException = computed(() => !!event.value?.parent_id)
/** An occurrence of a series was opened; changes ask which occurrences they apply to. */
const seriesOccurrence = computed(() => (event.value?.rrule && props.occurrence) || null)

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
const canModify = computed(() => !event.value || isCalendarEditor.value || event.value.creator_id === auth.user?.id)
const forceAllDay = computed(() => !!calendar.value?.force_all_day)
// Only bookings (events with a resource) go through approval, so only they show a status.
const bookingStatus = computed(() => {
  const booking = event.value?.resource_id || event.value?.location_resource_id
  const status = booking ? event.value!.status : null
  return status && statusLabels[status] ? status : null
})
const resourceRequiresApproval = computed(() => selectedResource.value?.meta?.requires_approval === true)
const locationRequiresApproval = computed(
  () => !!form.locationResourceId && selectedLocation.value?.meta?.requires_approval === true,
)
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
  if (seriesOccurrence.value) fillFromOccurrence(seriesOccurrence.value)
  if (event.value?.rrule) loadRrule(event.value.rrule)
  if (event.value) {
    const eventId = event.value.id
    // Reminders of a changed occurrence are those of its series.
    const [own, saved] = await Promise.all([
      api.getReminders(eventId).catch(() => ({ minutes: [] })),
      api.listEventParticipants(eventId).catch(() => []),
    ])
    reminders.value = own.minutes
    loadedReminders = reminders.value.join(',')
    participants.value = saved
  }
  preloadAvailability()
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
  form.location = value.location
  form.locationResourceId = value.location_resource_id
  showRecurrenceCount.value = value.show_recurrence_count
}

/** Shows the opened occurrence's times instead of those of the series' first occurrence. */
function fillFromOccurrence(occurrence: OccurrenceRef) {
  if (form.allDay) {
    // Occurrence ends of all-day events are exclusive; the form shows the last day.
    form.startDate = occurrence.start.slice(0, 10)
    form.endDate = new Date(new Date(occurrence.end).getTime() - DAY_MS).toISOString().slice(0, 10)
  } else {
    setLocalRange(new Date(occurrence.start), new Date(occurrence.end))
  }
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

// Picking a suggested place books it; typed text is just where the event takes place.
function onLocationSelect(value: string | null, option: api.SearchResult | null) {
  selectedLocation.value = option
  form.locationResourceId = option?.id ?? null
  form.location = option?.label ?? value ?? ''
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
    location: form.location || null,
    location_resource_id: form.locationResourceId,
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

/** Sends the participants added and removed in the dialog (of a series: for all occurrences).
 * Each one leaves its list once sent, so saving again after a failure sends only the rest. */
async function saveParticipants(eventId: string) {
  for (const id of [...removedParticipantIds.value]) {
    await api.removeEventParticipant(eventId, id)
    removedParticipantIds.value = removedParticipantIds.value.filter((removed) => removed !== id)
  }
  for (const pending of [...pendingParticipants.value]) {
    const { user_id, email, status } = pending
    await api.addEventParticipant(eventId, user_id ? { user_id, status } : { email, status })
    pendingParticipants.value = pendingParticipants.value.filter((p) => p !== pending)
  }
}

/** Saves the user's reminders for the event (of a series: for all occurrences) if they changed. */
async function saveReminders(eventId: string) {
  if (remindersChanged.value) await api.setReminders(eventId, reminders.value)
}

async function save() {
  const target = calendar.value
  if (!target || endBeforeStart.value || !remindersValid.value || busy.value) return
  const existing = event.value
  if (existing && !canModify.value) {
    // Who may not change the event may still set their own reminders.
    await submit(
      () => saveReminders(existing.id),
      () => emit('saved'),
    )
    return
  }
  const occurrence = seriesOccurrence.value
  if (occurrence && existing) {
    const input = eventInput()
    // A new recurrence can't apply to a single occurrence.
    const scope = await chooseScope('edit', input.rrule === existing.rrule)
    if (!scope) return
    await submit(
      async () => {
        await api.updateOccurrence(existing.id, occurrence.recurrenceId, scope, input)
        await saveParticipants(existing.id)
        await saveReminders(existing.id)
      },
      () => emit('saved'),
    )
    return
  }
  await submit(
    async () => {
      if (existing) {
        await api.updateEvent(existing.id, eventInput())
        await saveParticipants(existing.id)
        await saveReminders(existing.id)
      } else {
        const created = await api.createEvent(target.id, {
          ...eventInput(),
          participants: pendingParticipants.value.map(({ user_id, email, status }) => ({ user_id, email, status })),
        })
        // From now on the dialog edits the created event, so saving again after a failed step
        // below doesn't create it twice.
        event.value = created
        pendingParticipants.value = []
        await saveReminders(created.id)
      }
    },
    () => emit('saved'),
  )
}

async function remove() {
  const eventId = props.eventId
  if (!eventId) return
  const occurrence = seriesOccurrence.value
  if (occurrence) {
    const scope = await chooseScope('delete')
    if (!scope) return
    await submit(
      () => api.deleteOccurrence(eventId, occurrence.recurrenceId, scope),
      () => emit('deleted'),
    )
    return
  }
  const text = isException.value ? t('series.deleteExceptionText') : t('app.deleteEventText')
  if (!(await confirm(text, t('app.deleteEventTitle')))) return
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
    size="2xl"
    fullscreen-on-phone
    :dismissible="false"
    :title="eventId ? $t('app.edit') : $t('app.add')"
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

    <div v-if="bookingStatus" class="mb-4 text-sm text-gray-600">
      <p v-if="bookingStatus === 'pending' && event?.awaiting_approval.length" class="text-xs">
        {{ $t('booking.awaiting', { names: event.awaiting_approval.join(', ') }) }}
      </p>
      <p v-if="bookingStatus === 'pending'" class="mt-0.5 text-xs">{{ $t('booking.pendingHint') }}</p>
      <p v-else-if="event?.decision_note" class="text-xs">„{{ event.decision_note }}“</p>
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
        v-model="reminders"
        v-model:valid="remindersValid"
        :all-day="form.allDay"
      />

      <fieldset v-else class="contents" :disabled="!canModify">
        <div v-if="activeTab === 'details'" class="space-y-4 sm:space-y-6">
          <section class="space-y-3">
            <label class="block">
              <span class="block text-sm font-medium text-gray-700">{{ $t('event.title') }}</span>
              <input v-model="form.title" class="mt-1 w-full rounded-lg border px-3 py-2" />
            </label>

            <div>
              <div class="flex items-baseline justify-between gap-2">
                <label :for="`${fieldId}-location`" class="block text-sm font-medium text-gray-700">{{
                  $t('event.location')
                }}</label>
                <span v-if="locationRequiresApproval" class="text-xs text-amber-600 dark:text-amber-400">{{
                  $t('event.approvalRequired')
                }}</span>
              </div>
              <SearchableSelect
                :model-value="form.location || null"
                :input-id="`${fieldId}-location`"
                entity="locations"
                :calendar-id="calendar.id"
                allow-free-text
                live-free-text
                open-on-focus
                clearable
                class="mt-1"
                :placeholder="$t('event.locationPlaceholder')"
                @select="onLocationSelect"
              />
            </div>

            <label class="block">
              <span class="block text-sm font-medium text-gray-700">{{ $t('event.description') }}</span>
              <textarea v-model="form.description" class="mt-1 w-full rounded-lg border px-3 py-2" rows="3"></textarea>
            </label>
          </section>

          <section class="space-y-3 border-t border-line pt-4 sm:pt-5">
            <AppSwitch v-model="form.allDay" :label="$t('event.allDay')" :disabled="forceAllDay" />
            <p v-if="forceAllDay" class="text-xs text-gray-500">{{ $t('event.allDayRequired') }}</p>

            <div class="grid items-end gap-3 sm:grid-cols-[1fr_auto_1fr]">
              <div>
                <label :for="`${fieldId}-start`" class="block text-sm font-medium text-gray-700">{{
                  $t('event.start')
                }}</label>
                <div class="mt-1 flex gap-2">
                  <input
                    :id="`${fieldId}-start`"
                    v-model="form.startDate"
                    type="date"
                    class="min-w-0 flex-1 rounded-lg border px-2 py-1.5"
                  />
                  <input
                    v-if="!form.allDay"
                    v-model="form.startTime"
                    type="time"
                    :aria-label="`${$t('event.start')} (${$t('event.time')})`"
                    class="w-28 rounded-lg border px-2 py-1.5"
                  />
                </div>
              </div>
              <span class="hidden pb-2 text-gray-400 sm:block" aria-hidden="true">–</span>
              <div>
                <label :for="`${fieldId}-end`" class="block text-sm font-medium text-gray-700">{{
                  $t('event.end')
                }}</label>
                <div class="mt-1 flex gap-2">
                  <input
                    :id="`${fieldId}-end`"
                    v-model="form.endDate"
                    type="date"
                    :aria-invalid="endBeforeStart"
                    class="min-w-0 flex-1 rounded-lg border px-2 py-1.5"
                  />
                  <input
                    v-if="!form.allDay"
                    v-model="form.endTime"
                    type="time"
                    :aria-label="`${$t('event.end')} (${$t('event.time')})`"
                    :aria-invalid="endBeforeStart"
                    class="w-28 rounded-lg border px-2 py-1.5"
                  />
                </div>
              </div>
            </div>
            <p v-if="endBeforeStart" class="text-xs text-red-600" role="alert">{{ $t('event.endBeforeStart') }}</p>
          </section>

          <section class="space-y-3 border-t border-line pt-4 sm:pt-5">
            <div class="grid gap-3 sm:grid-cols-2">
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
                <div class="flex items-baseline justify-between gap-2">
                  <label :for="`${fieldId}-resource`" class="block text-sm font-medium text-gray-700">{{
                    $t('event.resource')
                  }}</label>
                  <span v-if="resourceRequiresApproval" class="text-xs text-amber-600 dark:text-amber-400">{{
                    $t('event.approvalRequired')
                  }}</span>
                </div>
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
              </div>
            </div>
          </section>
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
          v-model:removed="removedParticipantIds"
          v-model:participants="participants"
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
