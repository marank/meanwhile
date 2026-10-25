<script setup lang="ts">
import { Ban } from '@lucide/vue'
import ResourceIcon from '@/components/ResourceIcon.vue'
import { RESOURCE_ICON_NAMES } from '@/services/resourceIcons'

const model = defineModel<string>({ default: '' })
</script>

<template>
  <div role="group" class="flex flex-wrap gap-1" :aria-label="$t('app.icon')">
    <button
      type="button"
      :aria-pressed="!model"
      :title="$t('app.noIcon')"
      :aria-label="$t('app.noIcon')"
      class="flex h-9 w-9 items-center justify-center rounded-lg border text-gray-500 hover:bg-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
      :class="!model ? 'border-blue-600 bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300' : 'border-line'"
      @click="model = ''"
    >
      <Ban :size="18" />
    </button>
    <button
      v-for="name in RESOURCE_ICON_NAMES"
      :key="name"
      type="button"
      :aria-pressed="model === name"
      :title="name"
      :aria-label="name"
      class="flex h-9 w-9 items-center justify-center rounded-lg border text-gray-700 hover:bg-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
      :class="
        model === name ? 'border-blue-600 bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300' : 'border-line'
      "
      @click="model = name"
    >
      <ResourceIcon :name="name" :size="18" />
    </button>
  </div>
</template>
