<script setup lang="ts">
import { SlidersHorizontal, UserRound, Users } from '@lucide/vue'
import { computed, type Component } from 'vue'
import { useI18n } from 'vue-i18n'
import SettingsPage from '@/components/SettingsPage.vue'
import AdminGeneralSettings from '@/components/admin/AdminGeneralSettings.vue'
import AdminGroups from '@/components/admin/AdminGroups.vue'
import AdminUsers from '@/components/admin/AdminUsers.vue'
import { useGoBack } from '@/composables/useGoBack'
import { useQueryTab } from '@/composables/useQueryTab'

const validTabs = ['general', 'users', 'groups'] as const

const goBack = useGoBack()
const { t } = useI18n()
const { tab, selectTab } = useQueryTab(validTabs)
const icons: Record<(typeof validTabs)[number], Component> = {
  general: SlidersHorizontal,
  users: UserRound,
  groups: Users,
}
const tabs = computed(() => validTabs.map((id) => ({ id, label: t(`app.${id}`), icon: icons[id] })))
</script>

<template>
  <SettingsPage :title="$t('app.administration')" :tabs="tabs" :active-tab="tab" @back="goBack" @select-tab="selectTab">
    <template #default="{ tab: shown }">
      <AdminGeneralSettings v-if="shown === 'general'" />
      <AdminUsers v-else-if="shown === 'users'" />
      <AdminGroups v-else />
    </template>
  </SettingsPage>
</template>
