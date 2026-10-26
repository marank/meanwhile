<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string
    description?: string
    loading?: boolean
    flush?: boolean
  }>(),
  {
    description: '',
    loading: false,
    flush: false,
  },
)
</script>

<template>
  <!-- On phones part of the page's area below the tabs (SettingsPage), a card from sm up. -->
  <section class="overflow-hidden bg-surface sm:rounded-xl sm:border sm:border-line">
    <header
      class="flex flex-col items-start gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:px-6"
    >
      <div class="min-w-0">
        <h2 class="font-semibold text-gray-800">{{ title }}</h2>
        <p v-if="description" class="mt-1 text-sm text-gray-500">{{ description }}</p>
      </div>
      <div v-if="$slots.actions" class="shrink-0">
        <slot name="actions" />
      </div>
    </header>

    <div class="border-t border-line">
      <div
        v-if="loading"
        class="flex min-h-40 items-center justify-center px-6 py-10 text-sm text-gray-500"
        role="status"
      >
        {{ $t('app.loading') }}
      </div>
      <div v-else :class="flush ? '' : 'p-5 sm:p-6'">
        <slot />
      </div>
    </div>

    <footer v-if="$slots.footer && !loading" class="flex items-center justify-end gap-3 px-5 pb-5 sm:px-6 sm:pb-6">
      <slot name="footer" />
    </footer>
  </section>
</template>
