<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { KeyRound, Trash2 } from 'lucide-vue-next'
import LanguageSwitcher from '@/components/LanguageSwitcher.vue'
import IconButton from '@/components/IconButton.vue'
import SettingsPage from '@/components/SettingsPage.vue'
import SettingsPanel from '@/components/SettingsPanel.vue'
import { useAuthStore } from '@/stores/auth'
import { formatDateTime } from '@/services/datetime'
import { confirm } from '@/services/dialog'
import { errorMessage, toast } from '@/services/toast'
import { useI18n } from 'vue-i18n'
import * as api from '@/api'

type Tab = 'profile' | 'language' | 'dateTime' | 'appPasswords'
const validTabs: Tab[] = ['profile', 'language', 'dateTime', 'appPasswords']
const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const auth = useAuthStore()

const tab = computed<Tab>(() => validTabs.includes(route.query.tab as Tab) ? route.query.tab as Tab : 'profile')
const tabs = computed(() => validTabs.map((id) => ({ id, label: t(`app.${id}`) })))
const displayName = ref('')
const loading = ref(true)
const busy = ref(false)
const actionBusy = ref(false)
const appPasswords = ref<api.AppPassword[]>([])
const newLabel = ref('')
const createdPassword = ref<string | null>(null)

function selectTab(id: string) {
  if (!validTabs.includes(id as Tab)) return
  router.push({ query: { ...route.query, tab: id } })
}

onMounted(async () => {
  if (!auth.isLoggedIn) return
  try {
    await auth.fetchMe()
    displayName.value = auth.user?.display_name || ''
    await loadAppPasswords()
  } catch (error) {
    toast.error(errorMessage(error, t('app.loadFailed')))
  } finally {
    loading.value = false
  }
})

watch(() => route.query.tab, (value) => {
  if (value && !validTabs.includes(value as Tab)) router.replace({ query: { ...route.query, tab: 'profile' } })
})

async function loadAppPasswords() {
  if (!auth.isLoggedIn) return
  appPasswords.value = await api.listAppPasswords()
}

async function saveProfile() {
  if (!auth.isLoggedIn || busy.value) return
  busy.value = true
  try {
    await api.updateProfile({ display_name: displayName.value })
    await auth.fetchMe()
    toast.success(t('app.profileSaved'))
  } catch (error) {
    toast.error(errorMessage(error, t('app.saveFailed')))
  } finally {
    busy.value = false
  }
}

async function saveFormat(field: 'time_format' | 'date_format', value: string) {
  if (!auth.isLoggedIn || actionBusy.value) return
  actionBusy.value = true
  try {
    await api.updateProfile({ [field]: value } as any)
    await auth.fetchMe()
    toast.success(t('app.preferenceSaved'))
  } catch (error) {
    toast.error(errorMessage(error, t('app.saveFailed')))
  } finally {
    actionBusy.value = false
  }
}

async function createAppPassword() {
  if (!auth.isLoggedIn || !newLabel.value || actionBusy.value) return
  actionBusy.value = true
  try {
    const created = await api.createAppPassword(newLabel.value)
    createdPassword.value = created.password || null
    newLabel.value = ''
    await loadAppPasswords()
    toast.success(t('app.appPasswordCreated'))
  } catch (error) {
    toast.error(errorMessage(error, t('app.saveFailed')))
  } finally {
    actionBusy.value = false
  }
}

async function revoke(item: api.AppPassword) {
  if (!auth.isLoggedIn || actionBusy.value) return
  const ok = await confirm(t('app.revokeAppPasswordText', { label: item.label }), t('app.revokeAppPasswordTitle'))
  if (!ok) return
  actionBusy.value = true
  try {
    await api.deleteAppPassword(item.id)
    await loadAppPasswords()
    toast.success(t('app.appPasswordRevoked'))
  } catch (error) {
    toast.error(errorMessage(error, t('app.deleteFailed')))
  } finally {
    actionBusy.value = false
  }
}
</script>

<template>
  <SettingsPage :title="$t('app.account')" :tabs="tabs" :active-tab="tab" @back="router.back()" @select-tab="selectTab">
    <SettingsPanel v-if="tab === 'profile'" :title="$t('app.profile')" :description="$t('app.profileDescription')" :loading="loading">
      <label class="block max-w-xl">
        <span class="mb-1 block text-sm font-medium text-gray-700">{{ $t('auth.displayName') }}</span>
        <input v-model="displayName" class="w-full rounded-lg border border-gray-300 px-3 py-2" />
      </label>
      <template #footer>
        <button type="button" :disabled="busy" class="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50" @click="saveProfile">
          {{ $t('app.save') }}
        </button>
      </template>
    </SettingsPanel>

    <SettingsPanel v-else-if="tab === 'language'" :title="$t('app.language')" :description="$t('app.languageDescription')" :loading="loading">
      <LanguageSwitcher />
    </SettingsPanel>

    <SettingsPanel v-else-if="tab === 'dateTime'" :title="$t('app.dateTime')" :description="$t('app.dateTimeDescription')" :loading="loading">
      <div class="grid max-w-3xl gap-5 sm:grid-cols-2">
        <label class="block">
          <span class="mb-1 block text-sm font-medium text-gray-700">{{ $t('app.timeFormat') }}</span>
          <select :value="auth.user?.time_format" :disabled="actionBusy" class="w-full rounded-lg border border-gray-300 px-3 py-2" @change="saveFormat('time_format', ($event.target as HTMLSelectElement).value)">
            <option value="auto">{{ $t('app.formatAuto') }}</option>
            <option value="24h">{{ $t('app.format24h') }}</option>
            <option value="12h">{{ $t('app.format12h') }}</option>
          </select>
        </label>
        <label class="block">
          <span class="mb-1 block text-sm font-medium text-gray-700">{{ $t('app.dateFormat') }}</span>
          <select :value="auth.user?.date_format" :disabled="actionBusy" class="w-full rounded-lg border border-gray-300 px-3 py-2" @change="saveFormat('date_format', ($event.target as HTMLSelectElement).value)">
            <option value="auto">{{ $t('app.formatAuto') }}</option>
            <option value="dmy">31.12.2026</option>
            <option value="mdy">12/31/2026</option>
            <option value="ymd">2026-12-31</option>
          </select>
        </label>
      </div>
    </SettingsPanel>

    <SettingsPanel v-else :title="$t('app.appPasswords')" :description="$t('app.appPasswordsDescription')" :loading="loading" flush>
      <div class="space-y-4 p-5 sm:p-6">
        <div class="flex flex-col gap-2 sm:flex-row">
          <input v-model="newLabel" :placeholder="$t('app.appPasswordLabelPlaceholder')" class="min-w-0 flex-1 rounded-lg border border-gray-300 px-3 py-2" />
          <button type="button" :disabled="!newLabel || actionBusy" class="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50" @click="createAppPassword">
            {{ $t('app.add') }}
          </button>
        </div>
        <div v-if="createdPassword" class="rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-800">
          <p>{{ $t('app.appPasswordCreatedInfo') }}</p>
          <code class="mt-2 block break-all font-mono font-semibold">{{ createdPassword }}</code>
          <p class="mt-1 text-xs">{{ $t('app.copySecretNow') }}</p>
        </div>
      </div>
      <div class="overflow-x-auto border-t border-gray-200">
        <table class="w-full min-w-[34rem] text-sm">
          <thead class="bg-gray-50 text-left text-xs uppercase text-gray-500">
            <tr><th class="px-4 py-2">{{ $t('app.nameLabel') }}</th><th class="px-4 py-2">{{ $t('app.lastUsed') }}</th><th class="px-4 py-2 text-right">{{ $t('app.actions') }}</th></tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            <tr v-for="item in appPasswords" :key="item.id" class="hover:bg-gray-50">
              <td class="px-4 py-3 font-medium text-gray-800">{{ item.label }}</td>
              <td class="px-4 py-3 text-gray-500">{{ item.last_used_at ? formatDateTime(item.last_used_at) : $t('app.never') }}</td>
              <td class="px-4 py-3"><div class="flex justify-end"><IconButton :label="$t('app.delete')" tone="danger" :disabled="actionBusy" @click="revoke(item)"><Trash2 :size="18" /></IconButton></div></td>
            </tr>
            <tr v-if="!appPasswords.length"><td colspan="3" class="px-6 py-8 text-center text-gray-500"><KeyRound class="mx-auto mb-2" :size="24" />{{ $t('app.noAppPasswords') }}</td></tr>
          </tbody>
        </table>
      </div>
    </SettingsPanel>
  </SettingsPage>
</template>
