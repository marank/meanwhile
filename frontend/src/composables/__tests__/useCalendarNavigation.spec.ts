import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'
import { i18n } from '@/i18n'
import type { CalendarTarget } from '@/services/calendarUrl'
import { stubMatchMedia } from '@/components/calendar/__tests__/calendarFixtures'
import { useCalendarNavigation } from '../useCalendarNavigation'

const PHONE = '(max-width: 40rem)'
const day = (month: number, date: number) => new Date(2026, month - 1, date)

/** Stands in for FullCalendar's API: records what it is asked and shows October 2026. */
function fakeGrid() {
  return {
    calls: [] as string[],
    prev() {
      this.calls.push('prev')
    },
    next() {
      this.calls.push('next')
    },
    today() {
      this.calls.push('today')
    },
    gotoDate(date: Date) {
      this.calls.push(`goto ${date.toDateString()}`)
    },
    changeView(view: string, date?: Date) {
      this.calls.push(`view ${view} ${date?.toDateString() ?? ''}`.trim())
    },
    view: {
      type: 'dayGridMonth',
      currentStart: day(10, 1),
      currentEnd: day(11, 1),
      activeStart: day(9, 28),
      activeEnd: day(11, 2),
    },
  }
}

function setup(initial: CalendarTarget = {}, options: { phone?: boolean; grid?: boolean } = {}) {
  const media = stubMatchMedia(options.phone ? [PHONE] : [])
  const grid = fakeGrid()
  const load = vi.fn()
  const scrollListToToday = vi.fn()
  let nav!: ReturnType<typeof useCalendarNavigation>
  mount(
    defineComponent({
      setup() {
        nav = useCalendarNavigation({
          initial,
          firstWeekday: () => 1,
          gridApi: () => (options.grid === false ? undefined : grid),
          load,
          scrollListToToday,
        })
        return () => h('div')
      },
    }),
    { global: { plugins: [i18n] } },
  )
  /** The ranges loaded, as `from – to` local dates. */
  const loaded = () =>
    load.mock.calls.map(([start, end]: Date[]) => `${start!.toDateString()} – ${end!.toDateString()}`)
  return { nav, grid, load, loaded, media, scrollListToToday }
}

/** FullCalendar reporting the range it shows. */
function showGrid(nav: ReturnType<typeof useCalendarNavigation>, type: string, start: Date, end: Date) {
  nav.gridRangeShown({
    start,
    end,
    view: { type, title: `${type} ${start.toDateString()}`, currentStart: start, currentEnd: end },
  })
}

beforeEach(() => {
  i18n.global.locale.value = 'en'
  // Wednesday, 14 October 2026.
  vi.useFakeTimers({ now: new Date(2026, 9, 14, 12), toFake: ['Date'] })
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('useCalendarNavigation', () => {
  it('starts with the grid where the URL says, and follows the range it shows', () => {
    const { nav, load } = setup({ view: 'week', date: day(11, 4) })
    expect(nav.gridStart.value).toEqual({ view: 'timeGridWeek', date: day(11, 4) })
    expect(load).not.toHaveBeenCalled()
    showGrid(nav, 'timeGridWeek', day(11, 2), day(11, 9))
    expect(load).toHaveBeenCalledWith(day(11, 2), day(11, 9))
    expect(nav.shownToolbar.value).toEqual({
      title: `timeGridWeek ${day(11, 2).toDateString()}`,
      view: 'timeGridWeek',
      date: day(11, 2),
      todayInRange: false,
    })
  })

  it('moves the grid through FullCalendar', () => {
    const { nav, grid } = setup()
    nav.goPrev()
    nav.goNext()
    nav.goToday()
    nav.gotoDate(day(12, 24))
    nav.changeView('timeGridWeek', day(12, 24))
    expect(grid.calls).toEqual([
      'prev',
      'next',
      'today',
      `goto ${day(12, 24).toDateString()}`,
      `view timeGridWeek ${day(12, 24).toDateString()}`,
    ])
  })

  it('shows the list a month at a time, and loads each month', async () => {
    const { nav, loaded, scrollListToToday } = setup({ view: 'list', date: day(8, 20) })
    expect(nav.listMode.value).toBe(true)
    expect(nav.shownToolbar.value).toMatchObject({ title: 'August 2026', view: 'list', todayInRange: false })
    nav.goNext()
    await nextTick()
    nav.gotoDate(day(1, 9))
    await nextTick()
    nav.goToday()
    await nextTick()
    expect(nav.shownToolbar.value).toMatchObject({ title: 'October 2026', todayInRange: true })
    expect(scrollListToToday).toHaveBeenCalledOnce()
    expect(loaded()).toEqual([
      `${day(8, 1).toDateString()} – ${day(9, 1).toDateString()}`,
      `${day(9, 1).toDateString()} – ${day(10, 1).toDateString()}`,
      `${day(1, 1).toDateString()} – ${day(2, 1).toDateString()}`,
      `${day(10, 1).toDateString()} – ${day(11, 1).toDateString()}`,
    ])
  })

  it('stacks the week on phones, starting on the first weekday', async () => {
    const { nav, loaded } = setup({ view: 'week', date: day(10, 21) }, { phone: true })
    expect(nav.stackMode.value).toBe(true)
    expect(nav.stackStart.value).toEqual(day(10, 19))
    expect(nav.shownToolbar.value).toMatchObject({ view: 'timeGridWeek', date: day(10, 19), todayInRange: false })
    nav.goPrev()
    await nextTick()
    expect(nav.shownToolbar.value.todayInRange).toBe(true)
    nav.goToday()
    nav.goNext()
    await nextTick()
    nav.gotoDate(day(12, 1))
    await nextTick()
    expect(loaded()).toEqual([
      `${day(10, 19).toDateString()} – ${day(10, 26).toDateString()}`,
      `${day(10, 12).toDateString()} – ${day(10, 19).toDateString()}`,
      `${day(10, 19).toDateString()} – ${day(10, 26).toDateString()}`,
      `${day(11, 30).toDateString()} – ${day(12, 7).toDateString()}`,
    ])
  })

  it('keeps today or the start of what is shown when switching views', () => {
    const { nav } = setup()
    showGrid(nav, 'dayGridMonth', day(12, 1), day(1, 1))
    nav.changeView('list')
    expect(nav.listMonth.value).toEqual(day(12, 1))
    nav.changeView('dayGridMonth')
    expect(nav.listMode.value).toBe(false)
    expect(nav.gridStart.value).toEqual({ view: 'dayGridMonth', date: day(12, 1) })
    nav.changeView('list', day(10, 3))
    nav.changeView('timeGridWeek')
    // October, with today in it: the week of today.
    expect(nav.gridStart.value).toEqual({ view: 'timeGridWeek', date: new Date() })
  })

  it('turns the week into the stacked one and back when crossing the phone breakpoint', async () => {
    const { nav, media } = setup()
    showGrid(nav, 'timeGridWeek', day(10, 12), day(10, 19))
    media.set(PHONE, true)
    await nextTick()
    expect(nav.stackMode.value).toBe(true)
    expect(nav.stackStart.value).toEqual(day(10, 12))
    media.set(PHONE, false)
    await nextTick()
    expect(nav.stackMode.value).toBe(false)
    expect(nav.gridStart.value).toEqual({ view: 'timeGridWeek', date: new Date() })
  })

  it('leaves the month grid alone when crossing the breakpoint', async () => {
    const { nav, media } = setup()
    showGrid(nav, 'dayGridMonth', day(10, 1), day(11, 1))
    media.set(PHONE, true)
    await nextTick()
    expect(nav.stackMode.value).toBe(false)
  })

  it('shows what a link names, unless the grid shows it already', () => {
    const { nav, grid } = setup()
    nav.showTarget({ date: day(10, 20) })
    nav.showTarget({ view: 'month', date: day(10, 1) })
    expect(grid.calls).toEqual([])
    nav.showTarget({ date: day(12, 1) })
    nav.showTarget({ view: 'week', date: day(10, 20) })
    expect(grid.calls).toEqual([`goto ${day(12, 1).toDateString()}`, `view timeGridWeek ${day(10, 20).toDateString()}`])
    nav.showTarget({ view: 'list', date: day(3, 5) })
    expect(nav.listMonth.value).toEqual(day(3, 1))
    nav.showTarget({ date: day(4, 5) })
    expect(nav.listMonth.value).toEqual(day(4, 1))
    nav.showTarget({ view: 'month', date: day(5, 5) })
    expect(nav.gridStart.value).toEqual({ view: 'dayGridMonth', date: day(5, 5) })
  })

  it('follows links in the stacked week', () => {
    const { nav } = setup({}, { phone: true })
    nav.showTarget({ view: 'week', date: day(11, 11) })
    expect(nav.stackStart.value).toEqual(day(11, 9))
    nav.showTarget({ date: day(12, 2) })
    expect(nav.stackStart.value).toEqual(day(11, 30))
    nav.showTarget({ view: 'list' })
    expect(nav.listMode.value).toBe(true)
    expect(nav.stackMode.value).toBe(false)
  })

  it('ignores links before FullCalendar is there', () => {
    const { nav, grid } = setup({}, { grid: false })
    nav.showTarget({ date: day(12, 1) })
    nav.reload()
    expect(grid.calls).toEqual([])
  })

  it('loads what is shown again', async () => {
    const { nav, load } = setup()
    nav.reload(true)
    expect(load).toHaveBeenLastCalledWith(day(9, 28), day(11, 2), true)
    nav.changeView('list', day(10, 1))
    await nextTick()
    nav.reload()
    expect(load).toHaveBeenLastCalledWith(day(10, 1), day(11, 1), false)
  })

  it('reloads the stacked week', () => {
    const { nav, load } = setup({ view: 'week' }, { phone: true })
    nav.reload(true)
    expect(load).toHaveBeenLastCalledWith(day(10, 12), day(10, 19), true)
  })
})
