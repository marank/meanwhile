<script setup lang="ts">
import { KeyRound, LayoutGrid, Mail, SlidersHorizontal } from '@lucide/vue'
import { computed, type Component } from 'vue'
import { useI18n } from 'vue-i18n'
import SettingsPage from '@/components/SettingsPage.vue'
import AccountGeneralSettings from '@/components/account/AccountGeneralSettings.vue'
import AppPasswordsPanel from '@/components/account/AppPasswordsPanel.vue'
import EmailNotificationsPanel from '@/components/account/EmailNotificationsPanel.vue'
import OverviewSettingsPanel from '@/components/account/OverviewSettingsPanel.vue'
import { useGoBack } from '@/composables/useGoBack'
import { useQueryTab } from '@/composables/useQueryTab'

const validTabs = ['general', 'overview', 'emailNotifications', 'appPasswords'] as const

const goBack = useGoBack()
const { t } = useI18n()
const { tab, selectTab } = useQueryTab(validTabs)
const icons: Record<(typeof validTabs)[number], Component> = {
  general: SlidersHorizontal,
  overview: LayoutGrid,
  emailNotifications: Mail,
  appPasswords: KeyRound,
}
const tabs = computed(() => validTabs.map((id) => ({ id, label: t(`app.${id}`), icon: icons[id] })))
</script>

<template>
  <SettingsPage :title="$t('app.account')" :tabs="tabs" :active-tab="tab" @back="goBack" @select-tab="selectTab">
    <template #default="{ tab: shown }">
      <AccountGeneralSettings v-if="shown === 'general'" />
      <OverviewSettingsPanel v-else-if="shown === 'overview'" />
      <EmailNotificationsPanel v-else-if="shown === 'emailNotifications'" />
      <AppPasswordsPanel v-else />
    </template>
  </SettingsPage>
</template>
