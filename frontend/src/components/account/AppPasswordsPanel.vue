<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { KeyRound, Trash2 } from '@lucide/vue'
import IconButton from '@/components/IconButton.vue'
import SettingsPanel from '@/components/SettingsPanel.vue'
import * as api from '@/api'
import { useAction } from '@/composables/useAction'
import { useLoader } from '@/composables/useLoader'
import { formatDateTime } from '@/services/datetime'
import { confirm } from '@/services/dialog'

const { t } = useI18n()
const { busy, run } = useAction()
const appPasswords = ref<api.AppPassword[]>([])
const newLabel = ref('')
const createdPassword = ref<string | null>(null)

const { loading } = useLoader(loadAppPasswords)

async function loadAppPasswords() {
  appPasswords.value = await api.listAppPasswords()
}

async function createAppPassword() {
  const label = newLabel.value
  if (!label) return
  await run(
    async () => {
      const created = await api.createAppPassword(label)
      createdPassword.value = created.password || null
      newLabel.value = ''
      await loadAppPasswords()
    },
    { success: t('app.appPasswordCreated'), failure: t('app.saveFailed') },
  )
}

async function revoke(item: api.AppPassword) {
  if (!(await confirm(t('app.revokeAppPasswordText', { label: item.label }), t('app.revokeAppPasswordTitle')))) return
  await run(
    async () => {
      await api.deleteAppPassword(item.id)
      await loadAppPasswords()
    },
    { success: t('app.appPasswordRevoked'), failure: t('app.deleteFailed') },
  )
}
</script>

<template>
  <SettingsPanel
    :title="$t('app.appPasswords')"
    :description="$t('app.appPasswordsDescription')"
    :loading="loading"
    flush
  >
    <div class="space-y-4 p-5 sm:p-6">
      <div class="flex flex-col gap-2 sm:flex-row">
        <input
          v-model="newLabel"
          :placeholder="$t('app.appPasswordLabelPlaceholder')"
          class="min-w-0 flex-1 rounded-lg border border-line px-3 py-2"
        />
        <button
          type="button"
          :disabled="!newLabel || busy"
          class="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
          @click="createAppPassword"
        >
          {{ $t('app.add') }}
        </button>
      </div>
      <div v-if="createdPassword" class="rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-800">
        <p>{{ $t('app.appPasswordCreatedInfo') }}</p>
        <code class="mt-2 block break-all font-mono font-semibold">{{ createdPassword }}</code>
        <p class="mt-1 text-xs">{{ $t('app.copySecretNow') }}</p>
      </div>
    </div>
    <div class="overflow-x-auto border-t border-line">
      <table class="w-full min-w-[34rem] text-sm">
        <thead class="bg-surface-muted text-left text-xs uppercase text-gray-500">
          <tr>
            <th class="px-4 py-2">{{ $t('app.nameLabel') }}</th>
            <th class="px-4 py-2">{{ $t('app.lastUsed') }}</th>
            <th class="px-4 py-2 text-right">{{ $t('app.actions') }}</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-line">
          <tr v-for="item in appPasswords" :key="item.id" class="hover:bg-hover">
            <td class="px-4 py-3 font-medium text-gray-800">{{ item.label }}</td>
            <td class="px-4 py-3 text-gray-500">
              {{ item.last_used_at ? formatDateTime(item.last_used_at) : $t('app.never') }}
            </td>
            <td class="px-4 py-3">
              <div class="flex justify-end">
                <IconButton :label="$t('app.delete')" tone="danger" :disabled="busy" @click="revoke(item)"
                  ><Trash2 :size="18"
                /></IconButton>
              </div>
            </td>
          </tr>
          <tr v-if="!appPasswords.length">
            <td colspan="3" class="px-6 py-8 text-center text-gray-500">
              <KeyRound class="mx-auto mb-2" :size="24" />{{ $t('app.noAppPasswords') }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </SettingsPanel>
</template>
