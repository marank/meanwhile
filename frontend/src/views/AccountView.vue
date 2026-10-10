<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import SettingsPage from '@/components/SettingsPage.vue'
import AccountGeneralSettings from '@/components/account/AccountGeneralSettings.vue'
import AppPasswordsPanel from '@/components/account/AppPasswordsPanel.vue'
import OverviewSettingsPanel from '@/components/account/OverviewSettingsPanel.vue'
import { useGoBack } from '@/composables/useGoBack'
import { useQueryTab } from '@/composables/useQueryTab'

const validTabs = ['general', 'overview', 'appPasswords'] as const

const goBack = useGoBack()
const { t } = useI18n()
const { tab, selectTab } = useQueryTab(validTabs)
const tabs = computed(() => validTabs.map((id) => ({ id, label: t(`app.${id}`) })))
</script>

<template>
  <SettingsPage :title="$t('app.account')" :tabs="tabs" :active-tab="tab" @back="goBack" @select-tab="selectTab">
    <AccountGeneralSettings v-if="tab === 'general'" />
    <OverviewSettingsPanel v-else-if="tab === 'overview'" />
    <AppPasswordsPanel v-else />
  </SettingsPage>
</template>
