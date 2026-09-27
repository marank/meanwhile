<script setup lang="ts">
export type MenuItem = {
  label: string
  action: () => void
}

const props = defineProps<{
  x: number
  y: number
  items: MenuItem[]
}>()

const emit = defineEmits<{
  close: []
}>()

function handleAction(item: MenuItem) {
  item.action()
  emit('close')
}
</script>

<template>
  <div class="fixed inset-0 z-50" @click="emit('close')" @contextmenu.prevent="emit('close')">
    <div
      class="absolute w-max min-w-[7rem] bg-white dark:bg-gray-900 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 overflow-hidden"
      :style="{ top: `${y}px`, left: `${x}px` }"
      @click.stop
    >
      <button
        v-for="(item, index) in items"
        :key="`${index}-${item.label}`"
        @click="handleAction(item)"
        class="block w-full text-left whitespace-nowrap px-3 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 first:rounded-t-lg last:rounded-b-lg"
      >
        {{ item.label }}
      </button>
    </div>
  </div>
</template>
