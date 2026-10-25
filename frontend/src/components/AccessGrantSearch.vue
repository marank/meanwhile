<script lang="ts">
/** A person or group picked to be given access: a user's label is their name, the subtitle their email. */
export interface AccessGrantTarget {
  kind: 'user' | 'group'
  id: string
  label: string
  subtitle: string | null
}
</script>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { Search, User, Users } from '@lucide/vue'
import * as api from '@/api'

const props = defineProps<{
  placeholder: string
  disabled?: boolean
  /** Ids that are listed already; they're left out of the results. */
  excludeUserIds: Set<string>
  excludeGroupIds: Set<string>
  /** Whether groups can be picked, too (groups can only be linked by the owner). */
  groups?: boolean
}>()

const emit = defineEmits<{
  pick: [target: AccessGrantTarget]
}>()

type Option = AccessGrantTarget

const root = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLInputElement | null>(null)
const query = ref('')
const found = ref<Option[]>([])
const loading = ref(false)
const isOpen = ref(false)
const activeIndex = ref(-1)
const listStyle = ref<Record<string, string>>({})

let timer: ReturnType<typeof setTimeout> | null = null
let seq = 0

const options = computed(() =>
  found.value.filter((o) => !(o.kind === 'user' ? props.excludeUserIds : props.excludeGroupIds).has(o.id)),
)

async function search() {
  const q = query.value.trim()
  const mine = ++seq
  loading.value = true
  try {
    const [users, groups] = await Promise.all([
      q.length >= 2 || q === '' ? api.searchEntities('users', q, { limit: 8 }) : Promise.resolve([]),
      props.groups ? api.searchEntities('groups', q, { limit: 8 }) : Promise.resolve([]),
    ])
    if (mine !== seq) return
    const toOption = (kind: Option['kind']) => (r: api.SearchResult) => ({
      kind,
      id: r.id,
      label: r.label,
      subtitle: r.subtitle,
    })
    found.value = [...groups.map(toOption('group')), ...users.map(toOption('user'))]
  } catch {
    if (mine === seq) found.value = []
  } finally {
    if (mine === seq) loading.value = false
  }
}

function open() {
  if (props.disabled) return
  isOpen.value = true
  const rect = inputRef.value?.getBoundingClientRect()
  if (rect) listStyle.value = { top: `${rect.bottom}px`, left: `${rect.left}px`, width: `${rect.width}px` }
  search()
}

function close() {
  isOpen.value = false
  activeIndex.value = -1
}

function onInput(event: Event) {
  query.value = (event.target as HTMLInputElement).value
  if (!isOpen.value) open()
  if (timer) clearTimeout(timer)
  timer = setTimeout(search, 200)
}

function choose(option: Option) {
  emit('pick', option)
  query.value = ''
  close()
  inputRef.value?.blur()
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault()
    if (!isOpen.value) return open()
    const step = event.key === 'ArrowDown' ? 1 : -1
    activeIndex.value = Math.min(Math.max(activeIndex.value + step, 0), options.value.length - 1)
  } else if (event.key === 'Enter') {
    event.preventDefault()
    const option = options.value[activeIndex.value] ?? (options.value.length === 1 ? options.value[0] : undefined)
    if (option) choose(option)
  } else if (event.key === 'Escape' && isOpen.value) {
    event.preventDefault()
    close()
  } else if (event.key === 'Tab') {
    close()
  }
}

function onDocumentClick(event: MouseEvent) {
  if (root.value && !root.value.contains(event.target as Node)) close()
}

// The list is fixed to the viewport, so scrolling the page would detach it from the input.
function onScroll(event: Event) {
  if (isOpen.value && !(event.target as HTMLElement)?.closest?.('[role=listbox]')) close()
}

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
  window.addEventListener('scroll', onScroll, true)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick)
  window.removeEventListener('scroll', onScroll, true)
  if (timer) clearTimeout(timer)
})
</script>

<template>
  <div ref="root" class="relative">
    <Search :size="16" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
    <input
      ref="inputRef"
      :value="query"
      :placeholder="placeholder"
      :disabled="disabled"
      type="text"
      role="combobox"
      :aria-expanded="isOpen"
      aria-autocomplete="list"
      class="w-full rounded-lg border py-2 pl-9 pr-3 text-sm disabled:bg-surface-muted"
      @focus="open"
      @input="onInput"
      @keydown="onKeydown"
    />
    <ul
      v-if="isOpen"
      role="listbox"
      class="fixed z-[100] mt-1 max-h-72 overflow-auto rounded-lg border border-line bg-surface py-1 shadow-lg"
      :style="listStyle"
      @mousedown.prevent
      @mouseleave="activeIndex = -1"
    >
      <li v-if="loading && !options.length" class="px-3 py-2 text-sm text-gray-500">{{ $t('app.loading') }}</li>
      <li v-else-if="!options.length" class="px-3 py-2 text-sm text-gray-500">{{ $t('app.noResults') }}</li>
      <li
        v-for="(option, index) in options"
        :key="`${option.kind}-${option.id}`"
        role="option"
        :aria-selected="index === activeIndex"
        class="flex cursor-pointer items-center gap-3 px-3 py-2 text-sm"
        :class="index === activeIndex ? 'bg-surface-muted' : ''"
        @mouseenter="activeIndex = index"
        @mouseup="choose(option)"
      >
        <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-surface-muted text-gray-500">
          <Users v-if="option.kind === 'group'" :size="15" />
          <User v-else :size="15" />
        </span>
        <span class="min-w-0 flex-1">
          <span class="block truncate text-gray-800">{{ option.label }}</span>
          <span v-if="option.subtitle" class="block truncate text-xs text-gray-500">{{ option.subtitle }}</span>
        </span>
        <span class="shrink-0 text-xs text-gray-500">
          {{ option.kind === 'group' ? $t('app.group') : $t('app.user') }}
        </span>
      </li>
    </ul>
  </div>
</template>
