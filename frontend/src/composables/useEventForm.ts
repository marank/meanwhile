import { computed, reactive, ref, watch } from 'vue'
import type * as api from '@/api'
import type { OccurrenceRef } from '@/services/occurrences'
import { browserTimeZone, toDateInputValue, toTimeInputValue } from '@/services/datetime'
import { buildRrule, parseRrule, recurrenceDefaults, type RecurrenceRule } from '@/services/rrule'

const HOUR_MS = 60 * 60 * 1000
const DAY_MS = 24 * HOUR_MS
/** New events take up their time unless said otherwise. */
const BUSY: api.ShowAs = 'busy'

/** The fields of the event dialog: filled from an event, an occurrence or defaults, and turned into what is saved. */
export function useEventForm() {
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
    showAs: BUSY,
  })
  const selectedResource = ref<api.SearchResult | null>(null)
  const selectedLocation = ref<api.SearchResult | null>(null)
  const showRecurrenceCount = ref(false)
  /** The recurrence as the editor shows it; null when the event doesn't repeat. */
  const recurrence = ref<RecurrenceRule | null>(null)
  /** A rule from another client that the editor can't show; sent back unchanged. */
  const foreignRrule = ref<string | null>(null)
  // The loaded rule, and as the editor would write it: if nothing changed, the original is sent back as it was.
  let originalRrule: string | null = null
  let loadedRrule: string | null = null

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

  const endBeforeStart = computed(() => {
    if (!form.startDate || !form.endDate) return false
    if (form.allDay) return form.endDate < form.startDate
    return `${form.endDate}T${form.endTime}` < `${form.startDate}T${form.startTime}`
  })

  const bookedResourceIds = computed(() =>
    [form.locationResourceId, form.resourceId].filter((id): id is string => !!id),
  )
  const resourceRequiresApproval = computed(() => selectedResource.value?.meta?.requires_approval === true)
  const locationRequiresApproval = computed(
    () => !!form.locationResourceId && selectedLocation.value?.meta?.requires_approval === true,
  )

  // All-day dates are counted as UTC midnights, so a DST change doesn't shift them by an hour.
  const startMs = () =>
    new Date(form.allDay ? `${form.startDate}T00:00:00Z` : `${form.startDate}T${form.startTime}`).getTime()
  const endMs = () => new Date(form.allDay ? `${form.endDate}T00:00:00Z` : `${form.endDate}T${form.endTime}`).getTime()

  // A changed start moves the end along, keeping the duration, so the end isn't reported as before the start
  // before it was even touched. Filling the form sets both itself.
  let filling = false
  let lastStart = Number.NaN
  function fill(apply: () => void) {
    filling = true
    apply()
    filling = false
    lastStart = startMs()
  }
  watch(
    () => [form.startDate, form.startTime],
    () => {
      const start = startMs()
      if (filling || Number.isNaN(start)) return
      const duration = endMs() - lastStart
      lastStart = start
      if (Number.isNaN(duration)) return
      const end = new Date(start + (duration >= 0 ? duration : form.allDay ? 0 : HOUR_MS))
      if (form.allDay) {
        form.endDate = end.toISOString().slice(0, 10)
      } else {
        form.endDate = toDateInputValue(end)
        form.endTime = toTimeInputValue(end)
      }
    },
    { flush: 'sync' },
  )
  // All-day starts are counted differently.
  watch(
    () => form.allDay,
    () => (lastStart = startMs()),
    { flush: 'sync' },
  )

  function setLocalRange(start: Date, end: Date) {
    form.startDate = toDateInputValue(start)
    form.startTime = toTimeInputValue(start)
    form.endDate = toDateInputValue(end)
    form.endTime = toTimeInputValue(end)
  }

  function fillFromEvent(value: api.Event, forceAllDay: boolean) {
    fill(() => fillEventFields(value, forceAllDay))
  }

  function fillEventFields(value: api.Event, forceAllDay: boolean) {
    form.title = value.title
    form.description = value.description
    form.allDay = forceAllDay || value.all_day
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
    form.showAs = value.show_as
    showRecurrenceCount.value = value.show_recurrence_count
  }

  /** Shows the opened occurrence's times instead of those of the series' first occurrence. */
  function fillFromOccurrence(occurrence: OccurrenceRef) {
    fill(() => {
      if (form.allDay) {
        // Occurrence ends of all-day events are exclusive; the form shows the last day.
        form.startDate = occurrence.start.slice(0, 10)
        form.endDate = new Date(new Date(occurrence.end).getTime() - DAY_MS).toISOString().slice(0, 10)
      } else {
        setLocalRange(new Date(occurrence.start), new Date(occurrence.end))
      }
    })
  }

  /** A new event: an hour from `start` unless an end is given. */
  function fillDefaults(start: Date, end: Date | undefined, allDay: boolean) {
    fill(() => {
      form.allDay = allDay
      setLocalRange(start, end ?? new Date(start.getTime() + HOUR_MS))
    })
  }

  function loadRrule(value: string) {
    originalRrule = value
    recurrence.value = parseRrule(value, recurrenceDefaults(new Date(`${form.startDate}T00:00:00`)))
    if (recurrence.value) loadedRrule = buildRrule(recurrence.value)
    else foreignRrule.value = value
  }

  function currentRrule(): string | null {
    if (foreignRrule.value) return foreignRrule.value
    const rule = buildRrule(recurrence.value)
    // Writing an unchanged rule differently (e.g. spelling out the day of month) would count as a change.
    return rule !== null && rule === loadedRrule ? originalRrule : rule
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
      description: form.description,
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
      show_as: form.showAs,
    }
  }

  return {
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
  }
}
