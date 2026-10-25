<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { EmailNotifications } from '@/api'
import SettingsPanel from '@/components/SettingsPanel.vue'
import SettingsToggle from '@/components/SettingsToggle.vue'
import { useAction } from '@/composables/useAction'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const auth = useAuthStore()
const { busy, run } = useAction()

const kinds: Array<keyof EmailNotifications> = [
  'invitations',
  'responses',
  'approvals',
  'decisions',
  'comments',
  'memberships',
  'role_changes',
  'reminders',
]

const form = ref<EmailNotifications>({ ...auth.user!.email_notifications })

function save() {
  return run(() => auth.updateProfile({ email_notifications: form.value }), {
    success: t('app.settingsSaved'),
    failure: t('app.saveFailed'),
  })
}
</script>

<template>
  <SettingsPanel
    :title="$t('emailNotifications.title')"
    :description="$t('emailNotifications.description', { email: auth.user?.email })"
  >
    <div class="space-y-3">
      <SettingsToggle
        v-for="kind in kinds"
        :key="kind"
        v-model="form[kind]"
        :title="$t(`emailNotifications.${kind}`)"
        :description="$t(`emailNotifications.${kind}Help`)"
      />
    </div>
    <template #footer>
      <button
        type="button"
        :disabled="busy"
        class="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
        @click="save"
      >
        {{ $t('app.save') }}
      </button>
    </template>
  </SettingsPanel>
</template>
