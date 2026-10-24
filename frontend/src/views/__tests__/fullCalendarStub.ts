import { defineComponent, h, onMounted, watch, type PropType } from 'vue'
import { vi } from 'vitest'

/* eslint-disable @typescript-eslint/no-explicit-any -- the options are FullCalendar's, typed loosely here. */

/**
 * Stands in for FullCalendar (`vi.mock('@fullcalendar/vue3', () => import('./fullCalendarStub'))`): it renders
 * nothing, keeps the options it was given, and has an API that moves through months and weeks the way
 * FullCalendar does, reporting each range through the `datesSet` option.
 */

interface FakeView {
  type: string
  title: string
  currentStart: Date
  currentEnd: Date
  activeStart: Date
  activeEnd: Date
}

export const fullCalendar = {
  /** The options of the mounted calendar, kept current. */
  options: null as Record<string, any> | null,
  view: null as FakeView | null,
  /** The day FullCalendar keeps in view: moved by navigating, kept when switching views. */
  date: new Date(),
  mounts: 0,
  scrollToTime: vi.fn(),
  reset() {
    this.options = null
    this.view = null
    this.date = new Date()
    this.mounts = 0
    this.scrollToTime.mockReset()
  },
}

function rangeOf(type: string, date: Date): FakeView {
  const firstDay = fullCalendar.options?.firstDay ?? 0
  if (type === 'timeGridWeek') {
    const back = (date.getDay() - firstDay + 7) % 7
    const start = new Date(date.getFullYear(), date.getMonth(), date.getDate() - back)
    const end = new Date(start.getFullYear(), start.getMonth(), start.getDate() + 7)
    return {
      type,
      title: `Week of ${start.toDateString()}`,
      currentStart: start,
      currentEnd: end,
      activeStart: start,
      activeEnd: end,
    }
  }
  const start = new Date(date.getFullYear(), date.getMonth(), 1)
  const end = new Date(date.getFullYear(), date.getMonth() + 1, 1)
  // The month grid starts with the week of the first and ends with the week of the last.
  const back = (start.getDay() - firstDay + 7) % 7
  const activeStart = new Date(start.getFullYear(), start.getMonth(), 1 - back)
  const forward = (7 - ((end.getDay() - firstDay + 7) % 7)) % 7
  const activeEnd = new Date(end.getFullYear(), end.getMonth(), 1 + forward)
  return {
    type,
    title: `Month of ${start.toDateString()}`,
    currentStart: start,
    currentEnd: end,
    activeStart,
    activeEnd,
  }
}

function show(type: string, date: Date) {
  fullCalendar.date = date
  const view = rangeOf(type, date)
  fullCalendar.view = view
  fullCalendar.options?.datesSet?.({ start: view.activeStart, end: view.activeEnd, view })
}

function shift(by: number) {
  const { type, currentStart: start } = fullCalendar.view!
  show(
    type,
    type === 'timeGridWeek'
      ? new Date(start.getFullYear(), start.getMonth(), start.getDate() + 7 * by)
      : new Date(start.getFullYear(), start.getMonth() + by, 1),
  )
}

const api = {
  get view() {
    return fullCalendar.view!
  },
  prev: () => shift(-1),
  next: () => shift(1),
  today: () => show(fullCalendar.view!.type, new Date()),
  gotoDate: (date: Date) => show(fullCalendar.view!.type, date),
  changeView: (type: string, date?: Date) => show(type, date ?? fullCalendar.date),
  scrollToTime: (time: string) => fullCalendar.scrollToTime(time),
}

export default defineComponent({
  name: 'FullCalendar',
  props: { options: { type: Object as PropType<Record<string, any>>, required: true } },
  setup(props, { expose }) {
    watch(
      () => props.options,
      (options) => (fullCalendar.options = options),
      { immediate: true },
    )
    // Another first weekday makes another grid, as with FullCalendar.
    watch(
      () => props.options.firstDay,
      () => fullCalendar.view && show(fullCalendar.view.type, fullCalendar.date),
    )
    onMounted(() => {
      fullCalendar.mounts++
      show(props.options.initialView, props.options.initialDate ?? new Date())
    })
    expose({ getApi: () => api })
    return () => h('div', { class: 'full-calendar-stub' })
  },
})
