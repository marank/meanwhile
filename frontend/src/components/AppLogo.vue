<script setup lang="ts">
import { useSettingsStore } from '@/stores/settings'

withDefaults(defineProps<{ size?: 'md' | 'lg' }>(), { size: 'md' })

const settings = useSettingsStore()
</script>

<template>
  <div
    class="flex shrink-0 items-center justify-center overflow-hidden rounded-lg"
    :class="[
      size === 'lg' ? 'h-10 w-10 text-xl' : 'h-8 w-8',
      settings.logoUrl ? 'bg-surface' : 'bg-blue-600 font-bold text-white',
    ]"
  >
    <img v-if="settings.logoUrl" :src="settings.logoUrl" alt="" class="max-h-full max-w-full object-contain" />
    <template v-else>{{ settings.appName.charAt(0).toUpperCase() }}</template>
  </div>
</template>
