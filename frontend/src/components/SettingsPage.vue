<script setup lang="ts" generic="T extends string">
import { ChevronLeft } from '@lucide/vue'
import IconButton from '@/components/IconButton.vue'
import { defineComponent, ref, watch, type Component } from 'vue'
import TabBar from '@/components/TabBar.vue'
import { useMediaQuery } from '@/composables/useMediaQuery'
import { useTabSwipe } from '@/composables/useTabSwipe'

const props = defineProps<{
  title: string
  /** Pages with a single section leave the tabs out. */
  tabs?: Array<{ id: T; label: string; icon?: Component }>
  activeTab?: T
}>()

const emit = defineEmits<{
  back: []
  selectTab: [id: T]
}>()

defineSlots<{
  /** The content of one tab; while tabs slide, two are shown. */
  default(props: { tab: T | undefined }): unknown
}>()

// Renders its slot; lets each tab's content be kept alive on its own.
const TabContent = defineComponent({
  setup:
    (_, { slots }) =>
    () =>
      slots.default?.(),
})

const reducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)')
const isPhone = useMediaQuery('(width < 40rem)')
const viewport = ref<HTMLElement | null>(null)

// Tabs move when they change (on phones they slide, from sm up their cards fade); on touch screens,
// swiping sideways moves between them.
const swipe = useTabSwipe({
  tabs: () => props.tabs?.map((tab) => tab.id) ?? [],
  active: () => props.activeTab,
  select: (id) => emit('selectTab', id),
  animate: () => !reducedMotion.value,
  width: () => viewport.value?.clientWidth ?? 0,
})

const shift = (id: T) => swipe.panes.value.find((pane) => pane.id === id)?.shift

// The tab bar stays at the top while the page scrolls. A tab chosen further down starts at its top, right
// below the bar, not as far down as the one before was scrolled.
const tabBar = ref<{ $el: HTMLElement } | null>(null)

function scrollParent(el: HTMLElement | null) {
  for (let node = el?.parentElement; node; node = node.parentElement) {
    if (/auto|scroll/.test(getComputedStyle(node).overflowY)) return node
  }
  return null
}

/**
 * Scrolls up by `by`, to where the tabs' content starts right below the bar. A tab too short to be scrolled
 * there would leave the page scrolled to its top, the heading jumping back in; so from then on the tabs'
 * area is at least as tall as the screen below the bar.
 */
function scrollUp(scroller: HTMLElement, by: number) {
  if (!by || !viewport.value) return
  viewport.value.style.minHeight = `${scroller.clientHeight - (tabBar.value?.$el.offsetHeight ?? 0)}px`
  scroller.scrollTop -= by
}

/** How far the page is scrolled past the point where the tabs' content starts right below the bar. */
function scrolledPastTop() {
  const panels = viewport.value
  const scroller = scrollParent(panels)
  if (!panels || !scroller) return { scroller, past: 0 }
  const top = panels.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop
  const past = scroller.scrollTop - (top - (tabBar.value?.$el.offsetHeight ?? 0))
  return { scroller, past: Math.max(0, past) }
}

// While tabs slide, the incoming one is lowered by as much, so it shows its top; afterwards the page
// scrolls up by as much instead. Measured before the incoming tab is rendered.
const lowered = ref(0)
let shownBefore: T | undefined
watch(
  swipe.moving,
  (moving) => {
    if (!moving) return
    lowered.value = scrolledPastTop().past
    shownBefore = swipe.panes.value[0]?.id
  },
  { flush: 'sync' },
)
watch(swipe.moving, (moving) => {
  if (moving) return
  const { scroller } = scrolledPastTop()
  if (scroller && swipe.panes.value[0]?.id !== shownBefore) scrollUp(scroller, lowered.value)
  lowered.value = 0
})
// Without sliding (reduced motion) the new tab is just scrolled to.
watch(
  () => props.activeTab,
  () => {
    if (swipe.moving.value) return
    const { scroller, past } = scrolledPastTop()
    if (scroller) scrollUp(scroller, past)
  },
  { flush: 'post' },
)

/**
 * Where a tab is while tabs change, from how far it is shifted aside (in widths). On phones it slides that
 * far. From sm up, where the tabs are cards, the leaving card fades out in the first half, nudged a little
 * aside, and the coming one fades in in the second half from the side it lies on.
 */
function paneStyle(id: T) {
  const x = shift(id)
  if (!x) return undefined
  const y = swipe.panes.value[1]?.id === id ? lowered.value : 0
  if (isPhone.value) return { translate: `${x * 100}% ${y}px` }
  return { translate: `${x * 2}rem ${y}px`, opacity: Math.max(0, 1 - 2 * Math.abs(x)) }
}
</script>

<template>
  <div
    class="settings-page -mx-1 flex w-[calc(100%+0.5rem)] max-w-5xl flex-col pt-4 sm:mx-auto sm:w-full sm:p-6 max-sm:-mb-[max(0.25rem,env(safe-area-inset-bottom))] max-sm:min-h-[calc(100%+max(0.25rem,env(safe-area-inset-bottom)))]"
  >
    <!-- On phones the tabs and panels reach both edges of the screen, and the panels' color runs from the
         tabs down to the bottom (the negative margins undo the padding of App.vue's <main>); only the
         heading keeps a margin. One element at the top, so App.vue's page transitions can move it. -->
    <header class="mb-2 flex items-center gap-3 px-4 sm:px-0">
      <IconButton bordered :label="$t('app.back')" @click="emit('back')">
        <ChevronLeft :size="20" :stroke-width="2.25" />
      </IconButton>
      <h1 class="min-w-0 truncate text-2xl font-bold text-gray-800">{{ title }}</h1>
    </header>

    <!-- Stays at the top while scrolling, at the very edge (the negative top undoes <main>'s padding). -->
    <TabBar
      v-if="tabs && activeTab"
      ref="tabBar"
      :tabs="tabs"
      :active="activeTab"
      :position="swipe.position.value"
      :label="$t('app.settingsTabs')"
      class="sticky -top-1 z-10 bg-surface-muted px-1 sm:-top-4 sm:mb-4 sm:px-0"
      @select="emit('selectTab', $event)"
    />

    <div v-else class="max-sm:border-b max-sm:border-line sm:mb-4"></div>

    <div
      class="flex-1 max-sm:bg-surface max-sm:pb-[max(1rem,env(safe-area-inset-bottom))]"
      :class="{ 'touch-pan-y': tabs }"
      data-tab-panels
      v-on="swipe.handlers"
    >
      <!-- The tabs lie on top of each other; the ones sliding in or out are shifted aside, whole, however
           long each is (cut off only sideways). Each tab is kept alive: it loads its data when first
           shown, not again on every switch. -->
      <div
        v-if="tabs"
        ref="viewport"
        class="grid"
        :class="{ 'overflow-x-clip': swipe.moving.value }"
        :data-sliding="swipe.moving.value || undefined"
      >
        <div
          v-for="tab in tabs"
          :key="tab.id"
          class="col-start-1 row-start-1 min-w-0"
          :style="paneStyle(tab.id)"
          :inert="tab.id !== activeTab || undefined"
        >
          <KeepAlive>
            <TabContent v-if="shift(tab.id) !== undefined">
              <slot :tab="tab.id" />
            </TabContent>
          </KeepAlive>
        </div>
      </div>
      <slot v-else :tab="activeTab" />
    </div>
  </div>
</template>
