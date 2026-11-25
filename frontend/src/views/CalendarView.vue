<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import CalendarToolbar from '@/components/calendar/CalendarToolbar.vue'
import CalendarAgenda from '@/components/calendar/CalendarAgenda.vue'
import CalendarGrid from '@/components/calendar/CalendarGrid.vue'
import CalendarWeekStack from '@/components/calendar/CalendarWeekStack.vue'
import EventModal from '@/components/event/EventModal.vue'
import { ALL_CALENDARS, useCalendarStore } from '@/stores/calendars'
import { useEventStore } from '@/stores/events'
import { useOverviewStore } from '@/stores/overview'
import { storeToRefs } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import { seriesOccurrence, type OccurrenceRef } from '@/services/occurrences'
import { parseCalendarQuery } from '@/services/calendarUrl'
import { useCalendarDisplay } from '@/composables/useCalendarDisplay'
import { useCalendarNavigation } from '@/composables/useCalendarNavigation'
import { useLoader } from '@/composables/useLoader'
import { useNowColumns } from '@/composables/useNowColumns'
import * as api from '@/api'
import type { Occurrence } from '@/api'
import { i18n } from '@/i18n'
import { errorMessage } from '@/services/errors'
import { toast } from '@/services/toast'

const props = defineProps<{
  calendarId?: string
  folderId?: string
  /** /event/<id>: the event, open over the calendar. */
  eventId?: string
}>()

const router = useRouter()
const route = useRoute()
const calendarStore = useCalendarStore()
const eventStore = useEventStore()
const overviewStore = useOverviewStore()
const { dayStart } = storeToRefs(useAuthStore())

// The URL decides what is shown: /calendar/all, /calendar/<id-or-readable-path> or /calendar/folder/<id>.
// /calendar alone (opening the app) shows what was shown last, or else the first calendar; null meanwhile.
// Below an event (/event/<id>) the same is shown, keeping the event's URL.
const selection = computed(() => props.folderId ?? props.calendarId ?? null)
watch(
  () => [selection.value, calendarStore.loaded] as const,
  ([id, loaded]) => {
    if (id !== null) calendarStore.select(id)
    else if (loaded) {
      const start = calendarStore.startSelection()
      calendarStore.select(start)
      if (!props.eventId) void router.replace({ path: calendarStore.selectionPath(start), query: route.query })
    }
  },
  { immediate: true },
)

// A deleted or no longer shared calendar or folder in the URL falls back to the start; what is shown is
// remembered for the next time.
watch(
  () => [selection.value, calendarStore.loaded, calendarStore.selectedCalendar, calendarStore.selectedFolder] as const,
  ([id, loaded, calendar, folder]) => {
    if (!loaded || id === null) return
    if (id === ALL_CALENDARS || calendar || folder) calendarStore.rememberSelection(calendarStore.selectedId)
    else void router.replace('/calendar')
  },
  { immediate: true },
)

const { displaySettings, hiddenDays, eventColor, calendarNameOf, colorStyle } = useCalendarDisplay()

const gridRef = ref<InstanceType<typeof CalendarGrid> | null>(null)
const agendaRef = ref<InstanceType<typeof CalendarAgenda> | null>(null)

// The URL can name the month or week and the view to show: ?date=2026-10, ?month=10&year=2025, ?view=week.
// It is only ever read, never written: a bookmark keeps the parameters it was made with.
const nav = useCalendarNavigation({
  initial: parseCalendarQuery(route.query),
  firstWeekday: () => displaySettings.value.first_weekday,
  gridApi: () => gridRef.value?.getApi(),
  load: (start, end, force) => void eventStore.load(start, end, force),
  scrollListToToday: () => agendaRef.value?.scrollToToday(),
})
const { listMode, listMonth, listEnd, stackMode, stackStart, gridStart, gridToolbar, shownToolbar } = nav

// A link followed while the calendar is open (another month, the week view) is applied.
watch(
  () => route.query,
  (query) => nav.showTarget(parseCalendarQuery(query)),
)

const showModal = ref(false)
const modalEventId = ref<string | null>(null)
const modalOccurrence = ref<OccurrenceRef | null>(null)
const modalDate = ref<Date>(new Date())
const modalEndDate = ref<Date | undefined>(undefined)
const modalAllDay = ref<boolean | undefined>(undefined)

function openCreateModal(start: Date, end?: Date, allDay?: boolean) {
  // New events need one target calendar ("all" and folder selections are ambiguous) where one may add them.
  if (!calendarStore.canCreateInSelected) return
  modalEventId.value = null
  modalDate.value = start
  modalEndDate.value = end
  modalAllDay.value = allDay
  showModal.value = true
}

function openEditModal(occ: Occurrence) {
  modalEventId.value = occ.event_id
  modalOccurrence.value = seriesOccurrence(occ)
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  modalEventId.value = null
  modalOccurrence.value = null
  modalEndDate.value = undefined
  modalAllDay.value = undefined
  // Closed, the event's URL gives way to the calendar's.
  if (props.eventId) void router.replace(calendarStore.selectionPath(calendarStore.selectedId))
}

/** The day an event starts on; all-day events on their UTC date, the same in every zone. */
function startDay(event: api.Event): Date {
  const start = new Date(event.start)
  if (!event.all_day) return start
  return new Date(start.getUTCFullYear(), start.getUTCMonth(), start.getUTCDate())
}

// /event/<id> opens the event at its date; the calendar is switched to the event's if it doesn't show it.
watch(
  () => [props.eventId, calendarStore.loaded] as const,
  async ([eventId, loaded]) => {
    if (!eventId || !loaded) return
    let event: api.Event
    try {
      event = await api.getEvent(eventId)
    } catch (error) {
      // The server's own words are English only; a missing event is said in the reader's language.
      const missing = error instanceof api.ApiError && error.status === 404
      toast.error(missing ? i18n.global.t('event.notFound') : errorMessage(error, i18n.global.t('app.loadFailed')))
      void router.replace(calendarStore.selectionPath(calendarStore.selectedId))
      return
    }
    if (props.eventId !== eventId) return
    if (!calendarStore.selectedCalendarIds.includes(event.calendar_id) && calendarStore.canSelect(event.calendar_id)) {
      calendarStore.select(event.calendar_id)
    }
    nav.gotoDate(startDay(event))
    modalEventId.value = eventId
    modalOccurrence.value = null
    showModal.value = true
  },
  { immediate: true },
)

function saved() {
  closeModal()
  nav.reload(true)
}

/** A copy was made: it opens in place of the original, at its date, to be adjusted; the calendar
 * switches to the copy's where what is shown doesn't have it. */
function duplicated(copy: api.Event) {
  toast.success(i18n.global.t('duplicate.done'))
  const shown =
    calendarStore.selectedCalendarIds.includes(copy.calendar_id) || !calendarStore.canSelect(copy.calendar_id)
  // The URL decides what is shown (and an event's URL gives way to the calendar's).
  if (!shown || props.eventId) {
    void router.replace(calendarStore.selectionPath(shown ? calendarStore.selectedId : copy.calendar_id))
  }
  nav.gotoDate(startDay(copy))
  nav.reload(true)
  modalEventId.value = copy.id
  modalOccurrence.value = null
  showModal.value = true
}

watch(
  () => calendarStore.canCreateInSelected,
  (canCreate) => {
    if (!canCreate && showModal.value && !modalEventId.value) closeModal()
  },
)

watch(
  () => calendarStore.selectedCalendarIds.join(','),
  () => nav.reload(),
  { flush: 'post' },
)

useLoader(overviewStore.load, { immediate: !overviewStore.settings })

const nowColumns = useNowColumns(
  () => (!listMode.value && gridToolbar.value.view === 'timeGridWeek' ? gridToolbar.value.date : null),
  () => hiddenDays.value,
)

const calendarStyle = computed(() => ({
  ...colorStyle.value,
  '--calendar-now-column': nowColumns.value?.today ?? 0,
  '--calendar-now-columns': nowColumns.value?.count ?? 1,
}))
</script>

<template>
  <div class="calendar-root h-full flex flex-col" :style="calendarStyle">
    <div class="mx-auto flex w-full max-w-[100rem] flex-1 flex-col overflow-hidden p-2">
      <CalendarToolbar
        v-bind="shownToolbar"
        @prev="nav.goPrev"
        @next="nav.goNext"
        @today="nav.goToday"
        @goto="nav.gotoDate"
        @change-view="nav.changeView"
      />
      <div class="min-h-0 flex-1">
        <CalendarAgenda
          v-if="listMode"
          ref="agendaRef"
          :day-start="dayStart"
          :occurrences="eventStore.occurrences"
          :range-start="listMonth"
          :range-end="listEnd"
          :color-of="eventColor"
          :calendar-name-of="calendarNameOf"
          :can-create="calendarStore.canCreateInSelected"
          @open="openEditModal"
          @create="openCreateModal"
        />
        <CalendarWeekStack
          v-else-if="stackMode"
          :day-start="dayStart"
          :occurrences="eventStore.occurrences"
          :week-start="stackStart"
          :hidden-days="hiddenDays"
          :weekend-days="displaySettings.weekend_days"
          :color-of="eventColor"
          :can-create="calendarStore.canCreateInSelected"
          @open="openEditModal"
          @create="openCreateModal"
        />
        <CalendarGrid
          v-else
          ref="gridRef"
          :day-start="dayStart"
          :occurrences="eventStore.occurrences"
          :color-of="eventColor"
          :display="displaySettings"
          :hidden-days="hiddenDays"
          :initial-view="gridStart.view"
          :initial-date="gridStart.date"
          :can-create="calendarStore.canCreateInSelected"
          @range-shown="nav.gridRangeShown"
          @open="openEditModal"
          @create="openCreateModal"
          @moved="nav.reload(true)"
        />
      </div>
    </div>

    <!-- Keyed by the event, so a copy opened right after its original is loaded afresh. -->
    <EventModal
      v-if="showModal"
      :key="modalEventId ?? 'new'"
      :calendar-id="calendarStore.selectedCalendar?.id"
      :event-id="modalEventId"
      :occurrence="modalOccurrence"
      :default-start="modalDate"
      :default-end="modalEndDate"
      :default-all-day="modalAllDay"
      @saved="saved"
      @cancel="closeModal"
      @deleted="saved"
      @duplicated="duplicated"
    />
  </div>
</template>

<style>
.calendar-root {
  --calendar-control-bg: var(--app-surface);
  --calendar-control-border: var(--calendar-border-color);
  --calendar-control-hover: color-mix(in srgb, var(--app-surface-muted) 85%, var(--app-text) 15%);
}

html.dark .calendar-root {
  --calendar-control-bg: transparent;
  --calendar-control-hover: color-mix(in srgb, var(--app-surface-muted) 70%, var(--app-text) 30%);
}
</style>
