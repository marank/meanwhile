<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-vue-next'
import { monthName } from '@/services/datetime'
import AppSelect from '@/components/AppSelect.vue'
import YearPicker from './YearPicker.vue'

export type CalendarViewType = 'dayGridMonth' | 'timeGridWeek' | 'list'

const props = defineProps<{
  /** Title of the shown range, e.g. "5 – 11 Oct 2026" */
  title: string
  view: CalendarViewType
  /** First day of the shown month or week (the list shows a month) */
  date: Date
  todayInRange: boolean
}>()

const emit = defineEmits<{
  prev: []
  next: []
  today: []
  goto: [date: Date]
  changeView: [view: CalendarViewType]
}>()

const { t } = useI18n()

const month = computed(() => props.date.getMonth() + 1)
const months = computed(() =>
  Array.from({ length: 12 }, (_, index) => ({ value: index + 1, label: monthName(index + 1) })),
)
const year = computed(() => props.date.getFullYear())
const views = computed(() => [
  { value: 'dayGridMonth' as const, label: t('app.month') },
  { value: 'timeGridWeek' as const, label: t('app.week') },
  { value: 'list' as const, label: t('app.list') },
])

function goto(targetYear: number, targetMonth: number) {
  emit('goto', new Date(targetYear, targetMonth - 1, 1))
}

/** The same month and day (the same week in the week view) in another year; 29 February becomes the 28th. */
function shiftYear(by: number) {
  const target = new Date(props.date.getFullYear() + by, props.date.getMonth(), 1)
  const lastDay = new Date(target.getFullYear(), target.getMonth() + 1, 0).getDate()
  target.setDate(Math.min(props.date.getDate(), lastDay))
  emit('goto', target)
}
</script>

<template>
  <!--
    Equal outer columns keep the title exactly centered above the calendar. Where the calendar is
    too narrow for that, the title gets a row of its own above the controls (container query).
  -->
  <div class="calendar-toolbar @container pb-2">
    <div class="grid grid-cols-[auto_auto] items-center gap-3 @min-[60rem]:grid-cols-[1fr_auto_1fr]">
      <div class="flex items-center gap-3">
        <div class="toolbar-group">
          <button
            type="button"
            class="toolbar-button toolbar-icon"
            :aria-label="$t('app.previousYear')"
            @click="shiftYear(-1)"
          >
            <ChevronsLeft :size="18" />
          </button>
          <span class="toolbar-divider" aria-hidden="true"></span>
          <button
            type="button"
            class="toolbar-button toolbar-icon"
            :aria-label="$t('app.previousPeriod')"
            @click="emit('prev')"
          >
            <ChevronLeft :size="18" />
          </button>
          <span class="toolbar-divider" aria-hidden="true"></span>
          <button
            type="button"
            class="toolbar-button toolbar-icon"
            :aria-label="$t('app.nextPeriod')"
            @click="emit('next')"
          >
            <ChevronRight :size="18" />
          </button>
          <span class="toolbar-divider" aria-hidden="true"></span>
          <button
            type="button"
            class="toolbar-button toolbar-icon"
            :aria-label="$t('app.nextYear')"
            @click="shiftYear(1)"
          >
            <ChevronsRight :size="18" />
          </button>
        </div>
        <button type="button" class="toolbar-button toolbar-solo" :disabled="todayInRange" @click="emit('today')">
          {{ $t('app.today') }}
        </button>
      </div>

      <h2
        class="order-first col-span-2 truncate text-center text-lg font-semibold text-[var(--app-text)] @min-[60rem]:order-none @min-[60rem]:col-span-1"
      >
        {{ title }}
      </h2>

      <div class="flex items-center justify-end gap-2">
        <AppSelect
          :model-value="month"
          :options="months"
          :label="$t('app.month')"
          @update:model-value="goto(year, $event)"
        />
        <YearPicker :model-value="year" :label="$t('app.year')" @update:model-value="goto($event, month)" />

        <div class="toolbar-group ml-1" role="radiogroup" :aria-label="$t('app.view')">
          <button
            v-for="option in views"
            :key="option.value"
            type="button"
            role="radio"
            :aria-checked="view === option.value"
            class="toolbar-button"
            :class="{ 'toolbar-active': view === option.value }"
            @click="emit('changeView', option.value)"
          >
            {{ option.label }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* The selects take the toolbar's look and the palette's accent color. */
.calendar-toolbar {
  --select-bg: var(--calendar-control-bg);
  --select-border: var(--calendar-control-border);
  --select-radius: 0.625rem;
  --select-shadow: 0 1px 3px rgb(0 0 0 / 0.12);
  --select-padding-y: calc(0.3rem + 3px);
  --select-font-size: 0.875rem;
  --select-font-weight: 500;
  --select-line-height: 1.25rem;
  --select-focus: var(--calendar-accent-color);
  --select-accent: var(--calendar-accent-color);
}

/* The colors come from the calendar's palette via the --calendar-* variables of the calendar view. */
.toolbar-group {
  display: inline-flex;
  gap: 2px;
  padding: 3px;
  border: 1px solid var(--calendar-control-border);
  border-radius: 0.625rem;
  background-color: var(--calendar-control-bg);
  box-shadow: 0 1px 3px rgb(0 0 0 / 0.12);
}

.toolbar-button {
  border-radius: 0.5rem;
  padding: 0.3rem 0.8rem;
  font-size: 0.875rem;
  /* The same line height as the selects, so all controls of the toolbar are equally tall. */
  line-height: 1.25rem;
  font-weight: 500;
  color: var(--app-text);
  transition:
    background-color 120ms ease,
    color 120ms ease;
}

.toolbar-button:hover:not(:disabled, .toolbar-active) {
  background-color: var(--calendar-control-hover);
}

.toolbar-button:focus-visible {
  outline: 2px solid var(--calendar-accent-color);
  outline-offset: 1px;
}

.toolbar-icon {
  display: inline-flex;
  align-items: center;
  /* As tall as the text buttons next to it (their line plus their padding). */
  height: calc(1.25rem + 0.6rem);
  padding: 0 0.45rem;
}

/* A thin line between the arrows, not quite as tall as the buttons. */
.toolbar-divider {
  align-self: stretch;
  width: 1px;
  margin-block: 0.4rem;
  background-color: var(--calendar-control-border);
}

.toolbar-solo {
  border: 1px solid var(--calendar-control-border);
  border-radius: 0.625rem;
  background-color: var(--calendar-control-bg);
  box-shadow: 0 1px 3px rgb(0 0 0 / 0.12);
  padding: calc(0.3rem + 3px) 0.9rem;
}

.toolbar-solo:disabled {
  opacity: 0.5;
}

.toolbar-active {
  background-color: var(--calendar-accent-color);
  color: var(--calendar-accent-text-color);
  box-shadow: 0 1px 2px rgb(0 0 0 / 0.15);
}
</style>
