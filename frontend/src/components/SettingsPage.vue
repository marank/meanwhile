<script setup lang="ts">
import { ChevronLeft } from 'lucide-vue-next'
import IconButton from '@/components/IconButton.vue'

defineProps<{
  title: string
  tabs: Array<{ id: string; label: string }>
  activeTab: string
}>()

const emit = defineEmits<{
  back: []
  selectTab: [id: string]
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

    <nav class="mb-4 overflow-x-auto border-b border-gray-200" :aria-label="$t('app.settingsTabs')">
      <div class="flex min-w-max gap-1" role="tablist">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          type="button"
          role="tab"
          :aria-selected="activeTab === tab.id"
          :tabindex="activeTab === tab.id ? 0 : -1"
          class="whitespace-nowrap border-b-2 px-4 py-2 text-sm font-medium transition-colors"
          :class="activeTab === tab.id
            ? 'border-blue-600 text-blue-600'
            : 'border-transparent text-gray-600 hover:border-gray-300 hover:text-gray-900'"
          @click="emit('selectTab', tab.id)"
        >
          {{ tab.label }}
        </button>
      </div>
    </nav>

    <slot />
  </div>
</template>
