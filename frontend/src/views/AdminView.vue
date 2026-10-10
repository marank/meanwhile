<script setup lang="ts">
import { computed } from 'vue'
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
const tabs = computed(() => validTabs.map((id) => ({ id, label: t(`app.${id}`) })))
</script>

<template>
  <SettingsPage :title="$t('app.administration')" :tabs="tabs" :active-tab="tab" @back="goBack" @select-tab="selectTab">
    <AdminGeneralSettings v-if="tab === 'general'" />
    <AdminUsers v-else-if="tab === 'users'" />
    <AdminGroups v-else />
  </SettingsPage>
</template>
