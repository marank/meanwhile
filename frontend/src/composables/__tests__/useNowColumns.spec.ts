import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'
import { useNowColumns } from '../useNowColumns'

function setup(weekStart: Date | null, hiddenDays: number[] = []) {
  const start = ref(weekStart)
  let columns!: ReturnType<typeof useNowColumns>
  const wrapper = mount(
    defineComponent({
      setup() {
        columns = useNowColumns(
          () => start.value,
          () => hiddenDays,
        )
        return () => h('div')
      },
    }),
  )
  return { columns, start, wrapper }
}

beforeEach(() => {
  // Wednesday, 14 October 2026.
  vi.useFakeTimers({ now: new Date(2026, 9, 14, 12) })
})

afterEach(() => vi.useRealTimers())

describe('useNowColumns', () => {
  it("names today's column among the days shown", () => {
    expect(setup(new Date(2026, 9, 12)).columns.value).toEqual({ today: 2, count: 7 })
    // Without the weekend (Sunday and Saturday), the week starting on Sunday.
    expect(setup(new Date(2026, 9, 11), [0, 6]).columns.value).toEqual({ today: 2, count: 5 })
  })

  it('is null for another week, and without a week', () => {
    const { columns, start } = setup(new Date(2026, 9, 19))
    expect(columns.value).toBeNull()
    start.value = null
    expect(columns.value).toBeNull()
  })

  it('moves on to the next day as the clock runs, until unmounted', () => {
    const { columns, wrapper } = setup(new Date(2026, 9, 12))
    vi.advanceTimersByTime(12 * 60 * 60 * 1000)
    expect(columns.value).toEqual({ today: 3, count: 7 })
    wrapper.unmount()
    expect(vi.getTimerCount()).toBe(0)
  })
})
