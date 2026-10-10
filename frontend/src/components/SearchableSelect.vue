<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ChevronDown, X } from 'lucide-vue-next'
import * as api from '@/api'

const props = withDefaults(
  defineProps<{
    modelValue: string | null
    entity: api.SearchEntity
    calendarId?: string
    allowFreeText?: boolean
    freeTextValidator?: (value: string) => boolean
    placeholder?: string
    defaultLimit?: number
    debounceMs?: number
    minSearchLength?: number
    openOnFocus?: boolean
    clearable?: boolean
    disabled?: boolean
    /** id of the input, for associating a <label for>. */
    inputId?: string
  }>(),
  {
    defaultLimit: 20,
    debounceMs: 200,
    minSearchLength: 0,
    openOnFocus: false,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string | null]
  select: [value: string | null, option: api.SearchResult | null]
}>()

const { t } = useI18n()

const root = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLInputElement | null>(null)
const listRef = ref<HTMLElement | null>(null)
const listboxId = useId()
const query = ref('')
const preload = ref<api.SearchResult[]>([])
const results = ref<api.SearchResult[]>([])
const loading = ref(false)
const isOpen = ref(false)
const activeIndex = ref(-1)
const selectedOption = ref<api.SearchResult | null>(null)
const dropdownStyle = ref<Record<string, string>>({})

let debounceTimer: ReturnType<typeof setTimeout> | null = null
let fetchSeq = 0

const options = computed<api.SearchResult[]>(() => {
  const seen = new Set<string>()
  return [...results.value, ...preload.value].filter((o) => {
    if (seen.has(o.id)) return false
    seen.add(o.id)
    return true
  })
})

const freeTextValue = computed(() => {
  const value = query.value.trim()
  if (!props.allowFreeText || !value) return null
  if (props.freeTextValidator && !props.freeTextValidator(value)) return null
  const lower = value.toLowerCase()
  if (options.value.some((o) => o.label.toLowerCase() === lower || o.id === value)) return null
  return value
})

const optionCount = computed(() => options.value.length + (freeTextValue.value ? 1 : 0))

function canSearch(q: string) {
  return q.length >= props.minSearchLength
}

async function fetchResults(q: string) {
  if (!canSearch(q)) {
    if (q) results.value = []
    else preload.value = []
    loading.value = false
    return
  }
  const seq = ++fetchSeq
  loading.value = true
  try {
    const res = await api.searchEntities(props.entity, q, {
      limit: props.defaultLimit,
      calendarId: props.calendarId,
    })
    if (seq !== fetchSeq) return
    if (q) {
      results.value = res
    } else {
      preload.value = res
      results.value = res
    }
    resolveSelected()
  } catch {
    if (seq === fetchSeq && q) results.value = []
  } finally {
    if (seq === fetchSeq) loading.value = false
  }
}

function updatePosition() {
  const input = inputRef.value
  if (!input) return
  const rect = input.getBoundingClientRect()
  // The list is position: fixed, so viewport coordinates apply as they are.
  dropdownStyle.value = {
    top: `${rect.bottom}px`,
    left: `${rect.left}px`,
    width: `${rect.width}px`,
  }
}

function open() {
  if (props.disabled || isOpen.value) return
  isOpen.value = true
  activeIndex.value = -1
  nextTick(updatePosition)
}

function debouncedSearch(q: string) {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => fetchResults(q), props.debounceMs)
}

function close() {
  if (!isOpen.value) return
  isOpen.value = false
  activeIndex.value = -1
  if (selectedOption.value) {
    query.value = selectedOption.value.label
  } else if (!props.allowFreeText) {
    query.value = ''
  }
}

function onInput(event: Event) {
  const value = (event.target as HTMLInputElement).value
  query.value = value
  const trimmed = value.trim()
  if (trimmed.length < props.minSearchLength) {
    results.value = []
    close()
    return
  }
  open()
  debouncedSearch(trimmed)
}

function onFocus() {
  const q = query.value.trim()
  if (props.openOnFocus || q.length >= props.minSearchLength) {
    open()
    fetchResults(q)
  }
}

function choose(option: api.SearchResult) {
  selectedOption.value = option
  query.value = option.label
  isOpen.value = false
  activeIndex.value = -1
  emit('update:modelValue', option.id)
  emit('select', option.id, option)
}

function chooseFreeText() {
  if (freeTextValue.value === null) return
  const value = freeTextValue.value
  selectedOption.value = null
  query.value = value
  isOpen.value = false
  activeIndex.value = -1
  emit('update:modelValue', value)
  emit('select', value, null)
}

function clear() {
  selectedOption.value = null
  query.value = ''
  emit('update:modelValue', null)
  emit('select', null, null)
  inputRef.value?.focus()
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    if (!isOpen.value) {
      open()
      fetchResults(query.value.trim())
    }
    activeIndex.value = Math.min(activeIndex.value + 1, optionCount.value - 1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    if (!isOpen.value) {
      open()
      fetchResults(query.value.trim())
    }
    activeIndex.value = Math.max(activeIndex.value - 1, 0)
  } else if (event.key === 'Enter') {
    event.preventDefault()
    if (!isOpen.value) {
      open()
      return fetchResults(query.value.trim())
    }
    if (activeIndex.value >= 0 && activeIndex.value < options.value.length) {
      choose(options.value[activeIndex.value]!)
    } else if (freeTextValue.value !== null) {
      chooseFreeText()
    }
  } else if (event.key === 'Escape' && isOpen.value) {
    // Only swallow Escape while the list is open, so a surrounding dialog can close on the next press.
    event.preventDefault()
    close()
  } else if (event.key === 'Tab') {
    close()
  }
}

function onDocumentClick(event: MouseEvent) {
  if (root.value && !root.value.contains(event.target as Node)) close()
}

function onWindowResize() {
  if (isOpen.value) updatePosition()
}

// Scrolling the page would detach the fixed list from its input; scrolling the list itself is fine.
function onScrollClose(event: Event) {
  if (isOpen.value && !listRef.value?.contains(event.target as Node)) close()
}

// Shows the option behind a value set from outside (e.g. an existing event's resource) once it's loaded.
function resolveSelected() {
  if (!props.modelValue) {
    selectedOption.value = null
    return
  }
  if (selectedOption.value?.id === props.modelValue) return
  const match = options.value.find((o) => o.id === props.modelValue)
  if (match) {
    selectedOption.value = match
    if (!isOpen.value) query.value = match.label
    emit('select', match.id, match)
  } else if (props.allowFreeText) {
    selectedOption.value = null
    if (!isOpen.value) query.value = props.modelValue
  }
}

watch(
  () => props.modelValue,
  (value) => {
    if (!value) {
      selectedOption.value = null
      query.value = ''
      return
    }
    resolveSelected()
  },
  { immediate: true },
)

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
  window.addEventListener('resize', onWindowResize)
  window.addEventListener('scroll', onScrollClose, true)
  if (props.minSearchLength === 0) fetchResults('')
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick)
  window.removeEventListener('resize', onWindowResize)
  window.removeEventListener('scroll', onScrollClose, true)
  if (debounceTimer) clearTimeout(debounceTimer)
})

const displayPlaceholder = computed(() => props.placeholder || t('app.search'))
</script>

<template>
  <div ref="root" class="relative">
    <input
      :id="inputId"
      ref="inputRef"
      :value="query"
      :placeholder="displayPlaceholder"
      :disabled="disabled"
      type="text"
      role="combobox"
      :aria-expanded="isOpen"
      aria-autocomplete="list"
      :aria-controls="listboxId"
      class="w-full rounded-lg border px-3 py-2 pr-8 text-sm disabled:bg-surface-muted"
      @focus="onFocus"
      @input="onInput"
      @keydown="onKeydown"
    />
    <button
      v-if="clearable && modelValue && !disabled"
      type="button"
      :aria-label="$t('app.clear')"
      class="absolute right-7 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
      @click.stop="clear"
    >
      <X :size="16" />
    </button>
    <ChevronDown :size="16" class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />

    <ul
      v-if="isOpen"
      :id="listboxId"
      ref="listRef"
      role="listbox"
      class="fixed z-[100] mt-1 max-h-60 overflow-auto rounded-lg border border-line bg-surface py-1 shadow-lg"
      :style="dropdownStyle"
      @mousedown.prevent
      @mouseleave="activeIndex = -1"
    >
      <li v-if="loading && !optionCount" class="px-3 py-2 text-sm text-gray-500">
        {{ $t('app.loading') }}
      </li>
      <li v-else-if="!loading && !optionCount" class="px-3 py-2 text-sm text-gray-500">
        {{ $t('app.noResults') }}
      </li>
      <template v-else>
        <li
          v-for="(option, index) in options"
          :key="option.id"
          role="option"
          :aria-selected="option.id === modelValue"
          class="px-3 py-2 cursor-pointer text-sm"
          :class="[
            index === activeIndex ? 'bg-surface-muted' : '',
            option.id === modelValue ? 'text-blue-700 dark:text-blue-300 font-medium' : 'text-gray-800',
          ]"
          @mouseenter="activeIndex = index"
          @mouseup="choose(option)"
        >
          <div class="truncate">{{ option.label }}</div>
          <div v-if="option.subtitle" class="truncate text-xs text-gray-500">
            {{ option.subtitle }}
          </div>
        </li>
        <li
          v-if="freeTextValue !== null"
          role="option"
          :aria-selected="freeTextValue === modelValue"
          class="px-3 py-2 cursor-pointer text-sm"
          :class="[
            activeIndex === options.length ? 'bg-surface-muted' : '',
            freeTextValue === modelValue ? 'text-blue-700 dark:text-blue-300 font-medium' : 'text-gray-800',
          ]"
          @mouseenter="activeIndex = options.length"
          @mouseup="chooseFreeText"
        >
          {{ $t('app.useValue', { value: freeTextValue }) }}
        </li>
      </template>
    </ul>
  </div>
</template>
