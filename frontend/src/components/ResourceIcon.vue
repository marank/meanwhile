<script setup lang="ts">
import { computed } from 'vue'
import { resourceIcon } from '@/services/resourceIcons'

const props = withDefaults(defineProps<{ name?: string | null; size?: number }>(), { name: null, size: 16 })
const icon = computed(() => resourceIcon(props.name))
</script>

<template>
  <component :is="icon" v-if="icon" :size="size" class="shrink-0" aria-hidden="true" />
</template>
