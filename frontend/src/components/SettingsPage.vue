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
  <!-- On phones the tabs and panels reach both edges of the screen (the negative margin undoes the
       p-1 of App.vue's <main>); only the heading keeps a margin. -->
  <div class="-mx-1 w-[calc(100%+0.5rem)] max-w-5xl py-4 sm:mx-auto sm:w-full sm:p-6">
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
      class="mb-4 px-1 sm:px-0"
      @select="emit('selectTab', $event)"
    />

    <div v-else class="mb-4"></div>

    <slot />
  </div>
</template>
