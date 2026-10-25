import { computed, onBeforeUnmount, ref } from 'vue'

/**
 * Where the current time's line goes in the week view: FullCalendar draws it in today's column only, so it is
 * moved left by today's column and widened to all of them (they are equally wide). Null when the week
 * shown (starting on `weekStart`, without `hiddenDays`) doesn't have today in it.
 */
export function useNowColumns(weekStart: () => Date | null, hiddenDays: () => number[]) {
  const now = ref(new Date())
  const clock = setInterval(() => (now.value = new Date()), 60 * 1000)
  onBeforeUnmount(() => clearInterval(clock))

  return computed(() => {
    const start = weekStart()
    if (!start) return null
    const hidden = hiddenDays()
    const days = Array.from(
      { length: 7 },
      (_, i) => new Date(start.getFullYear(), start.getMonth(), start.getDate() + i),
    ).filter((day) => !hidden.includes(day.getDay()))
    const today = days.findIndex((day) => day.toDateString() === now.value.toDateString())
    return today < 0 ? null : { today, count: days.length }
  })
}
