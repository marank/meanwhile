import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { CalendarApi, ViewApi } from '@fullcalendar/vue3'
import type { CalendarViewType } from '@/components/calendar/CalendarToolbar.vue'
import { showsTarget, type CalendarTarget, type CalendarViewName } from '@/services/calendarUrl'
import { addDays } from '@/services/days'
import { useMediaQuery } from './useMediaQuery'

export type GridViewType = Exclude<CalendarViewType, 'list'>

/** What FullCalendar can be asked to do; it is only mounted while neither the list nor the stacked week is shown. */
type GridApi = Pick<CalendarApi, 'prev' | 'next' | 'today' | 'gotoDate' | 'changeView'> & {
  view: Pick<ViewApi, 'type' | 'currentStart' | 'currentEnd' | 'activeStart' | 'activeEnd'>
}

/** The range FullCalendar shows, as its `datesSet` reports it. */
export interface GridRange {
  start: Date
  end: Date
  view: Pick<ViewApi, 'type' | 'title' | 'currentStart' | 'currentEnd'>
}

const VIEW_TYPES: Record<CalendarViewName, CalendarViewType> = {
  month: 'dayGridMonth',
  week: 'timeGridWeek',
  list: 'list',
}

function firstOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1)
}

/**
 * Which range the calendar shows, and in which form: FullCalendar's month or week grid, the list
 * (CalendarAgenda, a month) or, on phones, the week with its days stacked (CalendarWeekStack). The list
 * and the stacked week are our own; FullCalendar isn't mounted meanwhile, and opens again where they were.
 * Each range shown is handed to `load`.
 */
export function useCalendarNavigation(options: {
  /** Where to start, as the URL names it. */
  initial: CalendarTarget
  firstWeekday: () => number
  gridApi: () => GridApi | undefined
  load: (start: Date, end: Date, force?: boolean) => void
  /** Scrolls the list to today, once it shows today's month. */
  scrollListToToday: () => void
}) {
  const { initial, gridApi, load } = options
  const { locale } = useI18n()

  /** What FullCalendar shows, as its last `datesSet` reported it. */
  const gridToolbar = ref({
    title: '',
    view: 'dayGridMonth' as CalendarViewType,
    date: new Date(),
    todayInRange: true,
  })
  /** The view and day FullCalendar opens with when it is mounted. */
  const gridStart = ref<{ view: GridViewType; date?: Date }>({
    view: initial.view === 'week' ? 'timeGridWeek' : 'dayGridMonth',
    date: initial.date,
  })

  const listMode = ref(initial.view === 'list')
  const listMonth = ref(firstOfMonth(initial.date ?? new Date()))
  const listEnd = computed(() => new Date(listMonth.value.getFullYear(), listMonth.value.getMonth() + 1, 1))

  // On phones the week shows its days stacked instead of seven narrow columns of hours.
  // The week is the one with `stackDate` in it.
  const isPhone = useMediaQuery('(max-width: 40rem)')
  const stackMode = ref(initial.view === 'week' && isPhone.value)
  const stackDate = ref(initial.date ?? new Date())
  const stackStart = computed(() => {
    const date = stackDate.value
    const back = (date.getDay() - options.firstWeekday() + 7) % 7
    return new Date(date.getFullYear(), date.getMonth(), date.getDate() - back)
  })
  const stackEnd = computed(() => addDays(stackStart.value, 7))

  const listToolbar = computed(() => {
    const now = new Date()
    return {
      title: new Intl.DateTimeFormat(locale.value, { month: 'long', year: 'numeric' }).format(listMonth.value),
      view: 'list' as CalendarViewType,
      date: listMonth.value,
      todayInRange: now >= listMonth.value && now < listEnd.value,
    }
  })

  const stackToolbar = computed(() => {
    const now = new Date()
    const format = new Intl.DateTimeFormat(locale.value, { day: 'numeric', month: 'short', year: 'numeric' })
    return {
      title: format.formatRange(stackStart.value, addDays(stackStart.value, 6)),
      view: 'timeGridWeek' as CalendarViewType,
      date: stackStart.value,
      todayInRange: now >= stackStart.value && now < stackEnd.value,
    }
  })

  /** What the toolbar shows: the list's month, the stacked week, or FullCalendar's view. */
  const shownToolbar = computed(() =>
    listMode.value ? listToolbar.value : stackMode.value ? stackToolbar.value : gridToolbar.value,
  )

  watch(
    () => [listMode.value, listMonth.value.getTime()] as const,
    ([list]) => {
      if (list) load(listMonth.value, listEnd.value)
    },
    { immediate: true },
  )

  watch(
    () => [stackMode.value, stackStart.value.getTime()] as const,
    ([stack]) => {
      if (stack) load(stackStart.value, stackEnd.value)
    },
    { immediate: true },
  )

  function shiftListMonth(by: number) {
    listMonth.value = new Date(listMonth.value.getFullYear(), listMonth.value.getMonth() + by, 1)
  }

  function goPrev() {
    if (listMode.value) shiftListMonth(-1)
    else if (stackMode.value) stackDate.value = addDays(stackStart.value, -7)
    else gridApi()?.prev()
  }

  function goNext() {
    if (listMode.value) shiftListMonth(1)
    else if (stackMode.value) stackDate.value = addDays(stackStart.value, 7)
    else gridApi()?.next()
  }

  function goToday() {
    if (stackMode.value) {
      stackDate.value = new Date()
      return
    }
    if (!listMode.value) {
      gridApi()?.today()
      return
    }
    listMonth.value = firstOfMonth(new Date())
    options.scrollListToToday()
  }

  function gotoDate(date: Date) {
    if (listMode.value) listMonth.value = firstOfMonth(date)
    else if (stackMode.value) stackDate.value = date
    else gridApi()?.gotoDate(date)
  }

  /** The day to keep in view when switching views: today if it is shown, else the start of what is shown. */
  function anchorDate(): Date {
    const shown = shownToolbar.value
    return shown.todayInRange ? new Date() : shown.date
  }

  function changeView(view: CalendarViewType, date?: Date) {
    if (view === 'list') {
      listMonth.value = firstOfMonth(date ?? anchorDate())
      stackMode.value = false
      listMode.value = true
    } else if (view === 'timeGridWeek' && isPhone.value) {
      stackDate.value = date ?? anchorDate()
      listMode.value = false
      stackMode.value = true
    } else if (listMode.value || stackMode.value) {
      gridStart.value = { view, date: date ?? anchorDate() }
      listMode.value = false
      stackMode.value = false
    } else {
      gridApi()?.changeView(view, date)
    }
  }

  /** FullCalendar's `datesSet`: it shows another range. */
  function gridRangeShown({ start, end, view }: GridRange) {
    load(start, end)
    const now = new Date()
    gridToolbar.value = {
      title: view.title,
      view: view.type as CalendarViewType,
      date: view.currentStart,
      todayInRange: now >= view.currentStart && now < view.currentEnd,
    }
  }

  /** Shows what a link names (another month, the week view), unless it is shown already. */
  function showTarget(target: CalendarTarget) {
    if (stackMode.value) showInStack(target)
    else if (target.view === 'week' && isPhone.value) changeView('timeGridWeek', target.date)
    else if (listMode.value) showInList(target)
    else if (target.view === 'list') changeView('list', target.date)
    else showInGrid(target)
  }

  function showInStack(target: CalendarTarget) {
    if (target.view && target.view !== 'week') changeView(VIEW_TYPES[target.view], target.date)
    else if (target.date) stackDate.value = target.date
  }

  function showInList(target: CalendarTarget) {
    if (target.view && target.view !== 'list') changeView(VIEW_TYPES[target.view], target.date)
    else if (target.date) listMonth.value = firstOfMonth(target.date)
  }

  function showInGrid(target: CalendarTarget) {
    const api = gridApi()
    if (!api) return
    const { currentStart, currentEnd, type } = api.view
    const view: CalendarViewName = type === 'timeGridWeek' ? 'week' : 'month'
    if (showsTarget(target, view, currentStart, currentEnd)) return
    // In one step: the view's own dates-set would otherwise write the URL before the date is reached.
    if (target.view && target.view !== view) api.changeView(VIEW_TYPES[target.view], target.date)
    else if (target.date) api.gotoDate(target.date)
  }

  /** Loads the range shown again; `force` also when it was loaded already. */
  function reload(force = false) {
    if (listMode.value) {
      load(listMonth.value, listEnd.value, force)
      return
    }
    if (stackMode.value) {
      load(stackStart.value, stackEnd.value, force)
      return
    }
    const view = gridApi()?.view
    if (view) load(view.activeStart, view.activeEnd, force)
  }

  // Turning the phone or resizing the window across the breakpoint keeps the week, in the other form.
  watch(isPhone, (phone) => {
    if (phone && !listMode.value && !stackMode.value && gridToolbar.value.view === 'timeGridWeek') {
      changeView('timeGridWeek')
    } else if (!phone && stackMode.value) {
      gridStart.value = { view: 'timeGridWeek', date: anchorDate() }
      stackMode.value = false
    }
  })

  return {
    listMode,
    listMonth,
    listEnd,
    stackMode,
    stackStart,
    gridStart,
    gridToolbar,
    shownToolbar,
    goPrev,
    goNext,
    goToday,
    gotoDate,
    changeView,
    gridRangeShown,
    showTarget,
    reload,
  }
}
