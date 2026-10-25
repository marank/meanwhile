<script setup lang="ts">
import { useSettingsStore } from '@/stores/settings'

withDefaults(defineProps<{ size?: 'md' | 'lg' }>(), { size: 'md' })

const settings = useSettingsStore()
</script>

<template>
  <!-- Our logo brings its own rounded tile; an uploaded one gets a surface behind it. -->
  <div
    class="flex shrink-0 items-center justify-center overflow-hidden rounded-lg"
    :class="[size === 'lg' ? 'h-10 w-10' : 'h-8 w-8', settings.logoUrl && 'bg-surface']"
  >
    <img :src="settings.logoUrl ?? '/logo.svg'" alt="" class="max-h-full max-w-full object-contain" />
  </div>
</template>
