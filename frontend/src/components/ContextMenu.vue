<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useEscapeToClose } from '@/composables/useEscapeToClose'

export type MenuItem = {
  label: string
  action: () => void
  /** Destructive, e.g. deleting: shown in red. */
  danger?: boolean
}

const props = defineProps<{
  x: number
  y: number
  items: MenuItem[]
  /** Open upwards from `y`, e.g. from a button at the bottom of the screen. */
  above?: boolean
  /** End at `x` instead of starting there, e.g. under a button at the end of a row. */
  alignEnd?: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

const VIEWPORT_MARGIN = 4

const menu = ref<HTMLElement | null>(null)
const position = ref({ left: props.x, top: props.y })
const returnFocusTo = document.activeElement instanceof HTMLElement ? document.activeElement : null

function menuItems(): HTMLElement[] {
  return Array.from(menu.value?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? [])
}

onMounted(() => {
  // Keep the whole menu on screen when it opens near the right or bottom edge.
  const rect = menu.value!.getBoundingClientRect()
  const top = props.above ? props.y - rect.height : props.y
  const left = props.alignEnd ? props.x - rect.width : props.x
  position.value = {
    left: Math.max(VIEWPORT_MARGIN, Math.min(left, window.innerWidth - rect.width - VIEWPORT_MARGIN)),
    top: Math.max(VIEWPORT_MARGIN, Math.min(top, window.innerHeight - rect.height - VIEWPORT_MARGIN)),
  }
  menuItems()[0]?.focus()
})

function close() {
  emit('close')
  returnFocusTo?.focus()
}

useEscapeToClose(() => true, close)

function choose(item: MenuItem) {
  close()
  item.action()
}

function onKeydown(event: KeyboardEvent) {
  const items = menuItems()
  const current = items.indexOf(document.activeElement as HTMLElement)
  const target = {
    ArrowDown: (current + 1) % items.length,
    ArrowUp: (current - 1 + items.length) % items.length,
    Home: 0,
    End: items.length - 1,
  }[event.key]
  if (target !== undefined) {
    event.preventDefault()
    items[target]?.focus()
  } else if (event.key === 'Tab') {
    event.preventDefault()
    close()
  }
}
</script>

<template>
  <div class="fixed inset-0 z-50" @click="close" @contextmenu.prevent="close">
    <!-- eslint-disable-next-line vuejs-accessibility/interactive-supports-focus -- focus goes to the menu items -->
    <div
      ref="menu"
      role="menu"
      class="absolute w-max min-w-[7rem] overflow-hidden rounded-lg border border-line bg-surface shadow-lg"
      :style="{ top: `${position.top}px`, left: `${position.left}px` }"
      @click.stop
      @keydown="onKeydown"
    >
      <button
        v-for="(item, index) in items"
        :key="`${index}-${item.label}`"
        type="button"
        role="menuitem"
        tabindex="-1"
        :data-tone="item.danger ? 'danger' : undefined"
        class="block w-full whitespace-nowrap px-3 py-2 text-left text-sm hover:bg-hover focus:outline-none focus-visible:bg-hover"
        :class="item.danger ? 'text-red-600' : 'text-gray-700'"
        @click="choose(item)"
      >
        {{ item.label }}
      </button>
    </div>
  </div>
</template>
