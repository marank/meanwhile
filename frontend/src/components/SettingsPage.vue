<script setup lang="ts" generic="T extends string">
import { ChevronLeft } from '@lucide/vue'
import IconButton from '@/components/IconButton.vue'
import TabBar from '@/components/TabBar.vue'

defineProps<{
  title: string
  /** Pages with a single section leave the tabs out. */
  tabs?: Array<{ id: T; label: string }>
  activeTab?: T
}>()

const emit = defineEmits<{
  back: []
  selectTab: [id: T]
}>()
</script>

<template>
  <div class="mx-auto w-full max-w-5xl p-4 sm:p-6">
    <header class="mb-2 flex items-center gap-3">
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
      class="mb-4"
      @select="emit('selectTab', $event)"
    />

    <div v-else class="mb-4"></div>

    <slot />
  </div>
</template>
