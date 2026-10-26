<script setup lang="ts" generic="T extends string">
import { ChevronLeft } from '@lucide/vue'
import IconButton from '@/components/IconButton.vue'
import type { Component } from 'vue'
import TabBar from '@/components/TabBar.vue'

defineProps<{
  title: string
  /** Pages with a single section leave the tabs out. */
  tabs?: Array<{ id: T; label: string; icon?: Component }>
  activeTab?: T
}>()

const emit = defineEmits<{
  back: []
  selectTab: [id: T]
}>()
</script>

<template>
  <!-- On phones the tabs and panels reach both edges of the screen, and the panels' color runs from the
       tabs down to the bottom (the negative margins undo the padding of App.vue's <main>); only the
       heading keeps a margin. -->
  <div
    class="settings-page -mx-1 flex w-[calc(100%+0.5rem)] max-w-5xl flex-col pt-4 sm:mx-auto sm:w-full sm:p-6 max-sm:-mb-[max(0.25rem,env(safe-area-inset-bottom))] max-sm:min-h-[calc(100%+max(0.25rem,env(safe-area-inset-bottom)))]"
  >
    <header class="mb-2 flex items-center gap-3 px-4 sm:px-0">
      <IconButton bordered :label="$t('app.back')" @click="emit('back')">
        <ChevronLeft :size="20" :stroke-width="2.25" />
      </IconButton>
      <h1 class="min-w-0 truncate text-2xl font-bold text-gray-800">{{ title }}</h1>
    </header>

    <TabBar
      v-if="tabs && activeTab"
      :tabs="tabs"
      :active="activeTab"
      :label="$t('app.settingsTabs')"
      class="px-1 sm:mb-4 sm:px-0"
      @select="emit('selectTab', $event)"
    />

    <div v-else class="max-sm:border-b max-sm:border-line sm:mb-4"></div>

    <div class="flex-1 max-sm:bg-surface max-sm:pb-[max(1rem,env(safe-area-inset-bottom))]">
      <slot />
    </div>
  </div>
</template>
