<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { GrantableRole } from '@/api'
import AppSelect from '@/components/AppSelect.vue'
import { allValues } from '@/utils/enums'

const props = withDefaults(
  defineProps<{
    compact?: boolean
    disabled?: boolean
    label?: string
    /** The role everyone gets in a public calendar, which never includes managing it. */
    publicAccess?: boolean
  }>(),
  { compact: false, disabled: false, publicAccess: false },
)

const role = defineModel<GrantableRole>({ required: true })

const { t } = useI18n()
const options = computed(() =>
  allValues<GrantableRole>({ read: true, own: true, full: true, manage: true })
    .filter((value) => !props.publicAccess || value !== 'manage')
    .map((value) => ({ value, label: t(`roles.${value}`) })),
)
</script>

<template>
  <AppSelect v-model="role" :options="options" :disabled="disabled" :size="compact ? 'sm' : 'md'" :label="label" />
</template>
