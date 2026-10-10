<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { GrantableRole } from '@/api'
import AppSelect from '@/components/AppSelect.vue'

withDefaults(defineProps<{ compact?: boolean; disabled?: boolean; label?: string }>(), {
  compact: false,
  disabled: false,
})

const role = defineModel<GrantableRole>({ required: true })

const { t } = useI18n()
const options = computed(() =>
  (['viewer', 'contributor', 'editor'] as const).map((value) => ({ value, label: t(`roles.${value}`) })),
)
</script>

<template>
  <div>
    <AppSelect v-model="role" :options="options" :disabled="disabled" :size="compact ? 'sm' : 'md'" :label="label" />
    <p class="mt-1 text-xs text-gray-500">{{ $t(`roles.${role}Description`) }}</p>
  </div>
</template>
