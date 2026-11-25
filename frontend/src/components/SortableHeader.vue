<script setup lang="ts">
import { ArrowDown, ArrowUp, ChevronsUpDown } from '@lucide/vue'
import type { SortDirection } from '@/composables/useTableSort'

/** A table's column header that sorts the rows by its column (useTableSort). */
defineProps<{ sort: SortDirection | 'none' }>()
defineEmits<{ sort: [] }>()
</script>

<template>
  <th class="px-4 py-2" :aria-sort="sort">
    <button
      type="button"
      class="group/sort -mx-1 inline-flex items-center gap-1 rounded px-1 uppercase hover:text-gray-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
      @click="$emit('sort')"
    >
      <slot />
      <ArrowUp v-if="sort === 'ascending'" :size="12" :stroke-width="2.5" aria-hidden="true" />
      <ArrowDown v-else-if="sort === 'descending'" :size="12" :stroke-width="2.5" aria-hidden="true" />
      <ChevronsUpDown
        v-else
        :size="12"
        :stroke-width="2.5"
        class="opacity-0 group-hover/sort:opacity-100 group-focus-visible/sort:opacity-100"
        aria-hidden="true"
      />
    </button>
  </th>
</template>
