<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import * as api from '@/api'
import SettingsPage from '@/components/SettingsPage.vue'
import SettingsPanel from '@/components/SettingsPanel.vue'
import CalendarAccessSettings from '@/components/calendar-settings/CalendarAccessSettings.vue'
import CalendarCategories from '@/components/calendar-settings/CalendarCategories.vue'
import CalendarGeneralSettings from '@/components/calendar-settings/CalendarGeneralSettings.vue'
import CalendarResources from '@/components/calendar-settings/CalendarResources.vue'
import CalendarShareSettings from '@/components/calendar-settings/CalendarShareSettings.vue'
import { errorMessage } from '@/services/errors'
import { useGoBack } from '@/composables/useGoBack'
import { useQueryTab } from '@/composables/useQueryTab'
import { provideCalendarSettingsSync } from '@/composables/useCalendarSettingsSync'
import { toast } from '@/services/toast'
import { useCalendarStore } from '@/stores/calendars'

const validTabs = ['general', 'access', 'categories', 'resources', 'share'] as const

const props = defineProps<{ calendarId: string }>()

provideCalendarSettingsSync()
const goBack = useGoBack()
const calendarStore = useCalendarStore()
const { t } = useI18n()
const { tab, selectTab } = useQueryTab(validTabs)

const tabs = computed(() => validTabs.map((id) => ({ id, label: t(`app.${id}`) })))
const calendar = ref<api.Calendar | null>(null)
const canManage = computed(() => calendar.value?.my_membership?.role === 'owner')

watch(
  () => props.calendarId,
  async (id) => {
    calendar.value = null
    try {
      const loaded = await api.getCalendar(id)
      // Ignore the answer if another calendar was opened in the meantime.
      if (id === props.calendarId) calendar.value = loaded
    } catch (error) {
      if (id === props.calendarId) toast.error(errorMessage(error, t('app.loadFailed')))
    }
  },
  { immediate: true },
)

// Opened directly, the settings lead back to this calendar.
function goBackToCalendar() {
  goBack(calendarStore.selectionPath(props.calendarId))
}
</script>

<template>
  <SettingsPage
    :title="`${$t('app.settings')}: ${calendar?.name ?? ''}`"
    :tabs="tabs"
    :active-tab="tab"
    @back="goBackToCalendar"
    @select-tab="selectTab"
  >
    <SettingsPanel v-if="!calendar" :title="tabs.find((item) => item.id === tab)!.label" loading />
    <!-- Kept alive: a tab loads its data when first opened, not again on every switch. Another calendar
         (the key) starts afresh. -->
    <div v-else :key="calendar.id">
      <KeepAlive>
        <CalendarGeneralSettings
          v-if="tab === 'general'"
          :calendar="calendar"
          :can-manage="canManage"
          @updated="calendar = $event"
        />
        <CalendarAccessSettings
          v-else-if="tab === 'access'"
          :calendar="calendar"
          :can-manage="canManage"
          @updated="calendar = $event"
        />
        <CalendarCategories v-else-if="tab === 'categories'" :calendar-id="calendar.id" :can-manage="canManage" />
        <CalendarResources v-else-if="tab === 'resources'" :calendar-id="calendar.id" :can-manage="canManage" />
        <CalendarShareSettings
          v-else
          :calendar="calendar"
          :can-manage="canManage"
          @updated="calendar = $event"
        />
      </KeepAlive>
    </div>
  </SettingsPage>
</template>
