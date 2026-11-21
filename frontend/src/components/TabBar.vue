<script setup lang="ts" generic="T extends string">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch, type Component } from 'vue'
import { useScrollFade } from '@/composables/useScrollFade'

const props = defineProps<{
  tabs: Array<{ id: T; label: string; count?: number; icon?: Component }>
  active: T
  label?: string
  /**
   * Where between the tabs the content is (e.g. 1.4 while swiping from the second tab to the third). Given,
   * the underline slides along with it and the tabs scroll to keep it in the middle.
   */
  position?: number
}>()

const emit = defineEmits<{
  select: [id: T]
}>()

const tablist = ref<HTMLElement | null>(null)
const scroller = ref<HTMLElement | null>(null)

// Only the active tab is in the tab order; the arrow keys, Home and End move between tabs.
async function onKeydown(event: KeyboardEvent) {
  const current = props.tabs.findIndex((tab) => tab.id === props.active)
  const last = props.tabs.length - 1
  const target = {
    ArrowRight: current === last ? 0 : current + 1,
    ArrowLeft: current === 0 ? last : current - 1,
    Home: 0,
    End: last,
  }[event.key]
  if (target === undefined) return
  event.preventDefault()
  emit('select', props.tabs[target]!.id)
  await nextTick()
  tablist.value?.querySelectorAll<HTMLElement>('[role="tab"]')[target]?.focus()
}

// Where the tabs don't fit (phones), they scroll sideways; the edges with more tabs behind them fade out.
const { style: fadeMask } = useScrollFade(scroller, 'x')

/** Centers the active tab, as far as the tabs left and right of it allow (the browser clamps scrollLeft). */
function revealActive() {
  const el = scroller.value
  const tab = tablist.value?.querySelector<HTMLElement>('[aria-selected="true"]')
  if (!el || !tab) return
  const left = tab.getBoundingClientRect().left - el.getBoundingClientRect().left + el.scrollLeft
  el.scrollLeft = left + tab.offsetWidth / 2 - el.clientWidth / 2
}

watch(
  () => props.active,
  () => {
    if (props.position === undefined) void nextTick(revealActive)
  },
)

// The sliding underline: between the two tabs around `position`, as far towards the second as the
// position has come. `layout` changes whenever the tabs' sizes may have.
const layout = ref(0)
const resize = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(() => layout.value++)
const underline = computed(() => {
  void layout.value
  const position = props.position
  const buttons = tablist.value?.querySelectorAll<HTMLElement>('[role="tab"]')
  if (position === undefined || !buttons?.length) return null
  const from = buttons[Math.floor(position)]
  const to = buttons[Math.ceil(position)] ?? from
  if (!from || !to) return null
  const share = position - Math.floor(position)
  return {
    left: from.offsetLeft + (to.offsetLeft - from.offsetLeft) * share,
    width: from.offsetWidth + (to.offsetWidth - from.offsetWidth) * share,
  }
})

watch(underline, (line) => {
  const el = scroller.value
  if (line && el) el.scrollLeft = line.left + line.width / 2 - el.clientWidth / 2
})

onMounted(() => {
  revealActive()
  if (tablist.value) resize?.observe(tablist.value)
  layout.value++
})
onBeforeUnmount(() => resize?.disconnect())
</script>

<template>
  <nav class="border-b border-line" :aria-label="label">
    <!-- Scrolled smoothly when a tab is chosen; following the underline, at once. -->
    <div
      ref="scroller"
      class="tab-scroller overflow-x-auto"
      :class="{ 'scroll-smooth': position === undefined }"
      :style="fadeMask"
    >
      <!-- eslint-disable-next-line vuejs-accessibility/interactive-supports-focus -- focus goes to the tabs -->
      <div ref="tablist" class="relative flex min-w-max gap-1" role="tablist" @keydown="onKeydown">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          type="button"
          role="tab"
          :aria-selected="active === tab.id"
          :tabindex="active === tab.id ? 0 : -1"
          class="inline-flex items-center gap-2 whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium transition-colors"
          :class="[
            active === tab.id
              ? 'border-blue-600 text-blue-600 dark:text-blue-300'
              : 'border-transparent text-gray-600 hover:border-line hover:text-gray-900',
            { 'border-b-transparent!': underline },
          ]"
          @click="emit('select', tab.id)"
        >
          <component :is="tab.icon" v-if="tab.icon" :size="16" class="shrink-0" aria-hidden="true" />
          {{ tab.label }}
          <span v-if="tab.count" class="rounded-full bg-blue-600 px-1.5 text-xs font-semibold leading-5 text-white">{{
            tab.count
          }}</span>
        </button>
        <span
          v-if="underline"
          class="pointer-events-none absolute bottom-0 left-0 h-0.5 bg-blue-600"
          :style="{ width: `${underline.width}px`, translate: `${underline.left}px 0` }"
          data-underline
          aria-hidden="true"
        ></span>
      </div>
    </div>
  </nav>
</template>

<style scoped>
/* The tabs scroll by swiping; a scrollbar under them would look like a second underline. */
.tab-scroller {
  scrollbar-width: none;
}

.tab-scroller::-webkit-scrollbar {
  display: none;
}
</style>
