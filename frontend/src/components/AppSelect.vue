<script setup lang="ts" generic="T extends string | number | boolean | null">
import { computed, nextTick, onBeforeUnmount, ref, shallowRef, useId } from 'vue'
import { Check, ChevronDown } from '@lucide/vue'
import { useEscapeToClose } from '@/composables/useEscapeToClose'

export interface SelectOption<V> {
  value: V
  label: string
}

/** An endless run of options, e.g. years: each option is the previous one stepped by one. */
export interface SelectSequence<V> {
  step: (value: V, by: number) => V
  label: (value: V) => string
  /** The value for digits typed into the closed or open select, or null while they don't name one yet. */
  fromDigits: (digits: string) => V | null
}

const props = withDefaults(
  defineProps<{
    options?: SelectOption<T>[]
    sequence?: SelectSequence<T>
    /** Accessible name, when no surrounding <label> provides one. */
    label?: string
    placeholder?: string
    disabled?: boolean
    size?: 'sm' | 'md'
    /** Which edge of the field the list lines up with. */
    align?: 'start' | 'end'
  }>(),
  { options: () => [], placeholder: '', disabled: false, size: 'md', align: 'start' },
)

// T includes null only where a field can be empty (shown with the placeholder).
const model = defineModel<T>({ required: true })

defineSlots<{
  /** Content of the closed field; defaults to the selected label. */
  selected?(props: { option: SelectOption<T> | null }): unknown
  /** Content of one entry in the list; defaults to its label. */
  option?(props: { option: SelectOption<T>; active: boolean; selected: boolean }): unknown
}>()

// Endless sequences are virtual: only the rows in view are rendered, out of a window that slides
// along while scrolling, so the list never ends in either direction.
const ROW_HEIGHT = 32
const VISIBLE_ROWS = 7
const WINDOW_SIZE = 200
const SHIFT = 50
const EDGE = 20
const OVERSCAN = 3
/** Typed characters are forgotten after this pause, like the type-ahead of native selects. */
const TYPING_PAUSE_MS = 1000
const PANEL_GAP = 4

const listboxId = useId()
const trigger = ref<HTMLButtonElement | null>(null)
const panel = ref<HTMLElement | null>(null)
const open = ref(false)
const active = shallowRef<T | null>(null)
const typed = ref('')
const panelStyle = ref<Record<string, string>>({})
const firstValue = shallowRef<T | null>(null)
const scrollTop = ref(0)
let typingTimer: ReturnType<typeof setTimeout> | undefined

const isSequence = computed(() => !!props.sequence)

function toOption(value: T): SelectOption<T> {
  return props.sequence
    ? { value, label: props.sequence.label(value) }
    : (props.options.find((option) => option.value === value) ?? { value, label: String(value) })
}

const selectedOption = computed(() => {
  if (model.value === null) return null
  if (props.sequence) return toOption(model.value)
  return props.options.find((option) => option.value === model.value) ?? null
})

/** Rows to render: all options of a list, or the visible part of a sequence's window. */
const rows = computed(() => {
  if (!props.sequence) return props.options.map((option) => ({ option, top: null as number | null }))
  if (firstValue.value === null) return []
  const start = Math.max(0, Math.floor(scrollTop.value / ROW_HEIGHT) - OVERSCAN)
  const end = Math.min(WINDOW_SIZE, start + VISIBLE_ROWS + 2 * OVERSCAN)
  return Array.from({ length: end - start }, (_, index) => ({
    option: toOption(props.sequence!.step(firstValue.value!, start + index)),
    top: (start + index) * ROW_HEIGHT,
  }))
})

function optionId(value: T) {
  return `${listboxId}-${String(value).replace(/\W/g, '_')}`
}

/** The option the keyboard is on, for screen readers (aria-activedescendant). */
const activeId = computed(() => (open.value && active.value !== null ? optionId(active.value) : undefined))

// Opening and closing

function onOutsidePointer(event: PointerEvent) {
  const target = event.target as Node
  if (!trigger.value?.contains(target) && !panel.value?.contains(target)) close()
}

// Scrolling the page would detach the fixed list from its field; scrolling the list itself is fine.
function onOutsideScroll(event: Event) {
  if (!panel.value?.contains(event.target as Node)) close()
}

async function position() {
  const field = trigger.value?.getBoundingClientRect()
  if (!field) return
  // The list lives in <body>, so it takes the field's accent color along explicitly.
  const accent = getComputedStyle(trigger.value!).getPropertyValue('--select-accent').trim()
  const base: Record<string, string> = accent ? { '--select-accent': accent } : {}
  panelStyle.value = {
    ...base,
    minWidth: `${field.width}px`,
    left: `${field.left}px`,
    top: `${field.bottom + PANEL_GAP}px`,
  }
  await nextTick()
  const list = panel.value?.getBoundingClientRect()
  if (!list) return
  const below = window.innerHeight - field.bottom - PANEL_GAP
  // Open upwards where the list doesn't fit below the field but does better above it.
  const top = list.height > below && field.top > below ? field.top - PANEL_GAP - list.height : field.bottom + PANEL_GAP
  const left = props.align === 'end' ? field.right - list.width : field.left
  panelStyle.value = {
    ...base,
    minWidth: `${field.width}px`,
    left: `${Math.max(PANEL_GAP, Math.min(left, window.innerWidth - list.width - PANEL_GAP))}px`,
    top: `${Math.max(PANEL_GAP, top)}px`,
  }
}

async function openList(highlight: T | null = model.value) {
  if (props.disabled) return
  active.value = highlight ?? props.options[0]?.value ?? null
  if (!open.value) {
    open.value = true
    document.addEventListener('pointerdown', onOutsidePointer)
    window.addEventListener('scroll', onOutsideScroll, true)
    window.addEventListener('resize', close)
  }
  if (isSequence.value && active.value !== null) await centerOn(active.value)
  await position()
  revealActive()
}

function close() {
  open.value = false
  clearTyped()
  document.removeEventListener('pointerdown', onOutsidePointer)
  window.removeEventListener('scroll', onOutsideScroll, true)
  window.removeEventListener('resize', close)
}

function choose(value: T) {
  model.value = value
  close()
}

// Endless sequences

/** Moves the window so `value` sits in the middle of the list. */
async function centerOn(value: T) {
  firstValue.value = props.sequence!.step(value, -WINDOW_SIZE / 2)
  await nextTick()
  if (!panel.value) return
  panel.value.scrollTop = (WINDOW_SIZE / 2) * ROW_HEIGHT - ((VISIBLE_ROWS - 1) / 2) * ROW_HEIGHT
  scrollTop.value = panel.value.scrollTop
}

function onScroll() {
  const el = panel.value
  if (!el || !props.sequence || firstValue.value === null) return
  const position = el.scrollTop / ROW_HEIGHT
  // Near either end, generate more options and move the window; the scroll offset changes by the
  // same amount, so the visible options stay where they are.
  if (position < EDGE) {
    firstValue.value = props.sequence.step(firstValue.value, -SHIFT)
    el.scrollTop += SHIFT * ROW_HEIGHT
  } else if (position > WINDOW_SIZE - VISIBLE_ROWS - EDGE) {
    firstValue.value = props.sequence.step(firstValue.value, SHIFT)
    el.scrollTop -= SHIFT * ROW_HEIGHT
  }
  scrollTop.value = el.scrollTop
}

/** The position of `value` in a sequence's window, by stepping from its first value. */
function sequenceIndex(value: T): number {
  for (let index = 0; index < WINDOW_SIZE; index++) {
    if (props.sequence!.step(firstValue.value!, index) === value) return index
  }
  return -1
}

// Keyboard

/** Shows the active option, scrolling as little as possible. */
function revealActive() {
  const el = panel.value
  if (!el || active.value === null) return
  if (!props.sequence) {
    document.getElementById(optionId(active.value))?.scrollIntoView({ block: 'nearest' })
    return
  }
  const index = sequenceIndex(active.value)
  if (index < EDGE || index >= WINDOW_SIZE - EDGE) {
    void centerOn(active.value)
    return
  }
  const top = index * ROW_HEIGHT
  if (top < el.scrollTop) el.scrollTop = top
  else if (top + ROW_HEIGHT > el.scrollTop + VISIBLE_ROWS * ROW_HEIGHT)
    el.scrollTop = top - (VISIBLE_ROWS - 1) * ROW_HEIGHT
}

function highlight(value: T) {
  active.value = value
}

function moveTo(value: T) {
  active.value = value
  void nextTick(revealActive)
}

function move(by: number | 'first' | 'last') {
  if (props.sequence) {
    if (typeof by === 'number') moveTo(props.sequence.step(active.value ?? model.value!, by))
    return
  }
  const values = props.options.map((option) => option.value)
  if (!values.length) return
  const current = Math.max(0, values.indexOf(active.value as T))
  const index = by === 'first' ? 0 : by === 'last' ? values.length - 1 : current + by
  moveTo(values[Math.max(0, Math.min(values.length - 1, index))]!)
}

function clearTyped() {
  typed.value = ''
  clearTimeout(typingTimer)
}

/** Type-ahead: lists jump to the first label starting with the typed text, sequences to the typed digits. */
function typeAhead(char: string) {
  const text = typed.value + char.toLowerCase()
  clearTimeout(typingTimer)
  typingTimer = setTimeout(clearTyped, TYPING_PAUSE_MS)
  if (props.sequence) {
    if (!/^\d$/.test(char)) return
    typed.value = text.slice(0, 6)
    const value = props.sequence.fromDigits(typed.value)
    if (value !== null) void openList(value)
    return
  }
  typed.value = text
  const match = props.options.find((option) => option.label.toLowerCase().startsWith(text))
  if (!match) return
  // Like a native select: a closed field changes right away, an open list moves its highlight.
  if (open.value) moveTo(match.value)
  else model.value = match.value
}

function onKeydown(event: KeyboardEvent) {
  const steps: Record<string, number | 'first' | 'last'> = {
    ArrowDown: 1,
    ArrowUp: -1,
    PageDown: 10,
    PageUp: -10,
    Home: 'first',
    End: 'last',
  }
  if (event.key in steps) {
    event.preventDefault()
    clearTyped()
    if (open.value) move(steps[event.key]!)
    else void openList()
  } else if (event.key === 'Enter' || (event.key === ' ' && !typed.value)) {
    event.preventDefault()
    const typedValue = props.sequence ? props.sequence.fromDigits(typed.value) : null
    if (typedValue !== null) choose(typedValue)
    else if (open.value && active.value !== null) choose(active.value)
    else void openList()
  } else if (event.key === 'Escape' && (open.value || typed.value)) {
    // Handled here, so a surrounding dialog stays open.
    event.preventDefault()
    close()
  } else if (event.key === 'Backspace' && props.sequence && typed.value) {
    event.preventDefault()
    typed.value = typed.value.slice(0, -1)
  } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
    event.preventDefault()
    typeAhead(event.key)
  }
}

// Leaving the field takes digits typed into a sequence, so Tab works like Enter there.
function onBlur() {
  const typedValue = props.sequence ? props.sequence.fromDigits(typed.value) : null
  if (typedValue !== null && typedValue !== model.value) choose(typedValue)
  else close()
}

function toggle() {
  if (open.value) close()
  else void openList()
}

// An open list takes Escape before any dialog around it, even when the field doesn't have the focus
// (Safari and Firefox on macOS don't focus buttons on click).
useEscapeToClose(() => open.value, close)

onBeforeUnmount(close)
</script>

<template>
  <div class="app-select" :class="`app-select-${size}`">
    <button
      ref="trigger"
      type="button"
      role="combobox"
      :disabled="disabled"
      :aria-label="label"
      :aria-expanded="open"
      :aria-controls="listboxId"
      :aria-activedescendant="activeId"
      class="app-select-trigger"
      @click="toggle"
      @keydown="onKeydown"
      @blur="onBlur"
    >
      <span class="min-w-0 truncate" :class="{ 'app-select-placeholder': !selectedOption && !typed }">
        <template v-if="typed && isSequence">{{ typed }}</template>
        <slot v-else name="selected" :option="selectedOption">{{ selectedOption?.label ?? placeholder }}</slot>
      </span>
      <ChevronDown :size="16" class="app-select-chevron" :class="{ 'rotate-180': open }" aria-hidden="true" />
    </button>

    <Teleport to="body">
      <div
        v-show="open"
        :id="listboxId"
        ref="panel"
        role="listbox"
        :aria-label="label"
        class="app-select-panel"
        :class="{ 'app-select-panel-sequence': isSequence }"
        :style="[panelStyle, isSequence ? { height: `${VISIBLE_ROWS * ROW_HEIGHT}px` } : {}]"
        @scroll="onScroll"
        @mousedown.prevent
      >
        <div :class="{ relative: isSequence }" :style="isSequence ? { height: `${WINDOW_SIZE * ROW_HEIGHT}px` } : {}">
          <div
            v-for="row in rows"
            :id="optionId(row.option.value)"
            :key="String(row.option.value)"
            role="option"
            :aria-selected="row.option.value === model"
            class="app-select-option"
            :class="{
              'app-select-option-active': row.option.value === active,
              'app-select-option-selected': row.option.value === model,
            }"
            :style="
              row.top === null
                ? {}
                : { position: 'absolute', insetInline: 0, top: `${row.top}px`, height: `${ROW_HEIGHT}px` }
            "
            @mouseenter="highlight(row.option.value)"
            @click="choose(row.option.value)"
          >
            <span class="min-w-0 flex-1">
              <slot
                name="option"
                :option="row.option"
                :active="row.option.value === active"
                :selected="row.option.value === model"
              >
                {{ row.option.label }}
              </slot>
            </span>
            <Check v-if="row.option.value === model && !isSequence" :size="16" class="shrink-0" aria-hidden="true" />
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style>
/*
 * The look follows these variables, with the form field look as default. Containers can set them,
 * e.g. the calendar toolbar uses its palette colors.
 */
.app-select-trigger {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  border: 1px solid var(--select-border, var(--app-border));
  border-radius: var(--select-radius, 0.5rem);
  background-color: var(--select-bg, var(--app-input));
  box-shadow: var(--select-shadow, none);
  padding: var(--select-padding-y, 0.5rem) 0.5rem var(--select-padding-y, 0.5rem) 0.75rem;
  font-size: var(--select-font-size, 1rem);
  font-weight: var(--select-font-weight, 400);
  line-height: var(--select-line-height, 1.5rem);
  font-variant-numeric: tabular-nums;
  text-align: left;
  color: var(--app-text);
  user-select: none;
}

/* Phones: as tall as the other fields there (see main.css). */
@media (width < 40rem) {
  .app-select-trigger {
    padding-block: var(--select-padding-y, 0.375rem);
  }
}

.app-select-sm .app-select-trigger {
  --select-padding-y: 0.375rem;
  --select-font-size: 0.875rem;
  --select-line-height: 1.25rem;
}

/* Phones: the small size is as tall as all other fields there (see main.css). */
@media (width < 40rem) {
  .app-select-sm .app-select-trigger {
    --select-font-size: 1rem;
    --select-line-height: 1.5rem;
  }
}

.app-select-trigger:focus-visible {
  outline: none;
  border-color: var(--select-focus, var(--color-blue-500));
  box-shadow: 0 0 0 1px var(--select-focus, var(--color-blue-500));
}

.app-select-trigger:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.app-select-placeholder {
  color: var(--app-text-muted);
}

.app-select-chevron {
  flex-shrink: 0;
  opacity: 0.7;
  transition: transform 150ms ease;
}

/* Lives in <body>, above dialogs (z-50/z-60), so lists inside scrolling dialogs aren't cut off. */
.app-select-panel {
  position: fixed;
  z-index: 70;
  max-height: 16rem;
  overflow-y: auto;
  border: 1px solid var(--app-border);
  border-radius: 0.5rem;
  background-color: var(--app-surface);
  padding-block: 0.25rem;
  box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.2);
}

.app-select-panel-sequence {
  max-height: none;
  padding-block: 0;
}

.app-select-option {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.375rem 0.75rem;
  font-size: 0.875rem;
  font-variant-numeric: tabular-nums;
  color: var(--app-text);
  cursor: pointer;
  user-select: none;
}

.app-select-option-active {
  background-color: var(--app-hover);
}

.app-select-option-selected {
  font-weight: 600;
  color: var(--select-accent, var(--color-blue-600));
}

html.dark .app-select-option-selected {
  color: var(--select-accent, var(--color-blue-300));
}
</style>
