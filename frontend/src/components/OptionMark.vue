<script setup lang="ts">
import { computed } from 'vue'
import type { SearchResult } from '@/api'
import ResourceIcon from '@/components/ResourceIcon.vue'
import { optionMark } from '@/services/optionMark'

const props = defineProps<{ option: SearchResult }>()
const mark = computed(() => optionMark(props.option))
</script>

<template>
  <!-- The same small square as before an event's title in the calendar. -->
  <span
    v-if="mark?.kind === 'color'"
    class="block h-2.5 w-2.5 shrink-0 rounded-sm"
    :style="{ backgroundColor: mark.color }"
    aria-hidden="true"
  ></span>
  <ResourceIcon v-else-if="mark?.kind === 'icon'" :name="mark.icon" :size="16" class="text-gray-500" />
</template>
