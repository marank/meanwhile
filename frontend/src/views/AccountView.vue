<script setup lang="ts">
import { onMounted, ref } from 'vue'
import LanguageSwitcher from '@/components/LanguageSwitcher.vue'
import { useAuthStore } from '@/stores/auth'
import * as api from '@/api'

type Tab = 'profile' | 'language' | 'appPasswords'
const tab = ref<Tab>('profile')

const auth = useAuthStore()
const displayName = ref('')
const busy = ref(false)
const message = ref('')

const appPasswords = ref<api.AppPassword[]>([])
const newLabel = ref('')
const createdPassword = ref<string | null>(null)

onMounted(async () => {
  if (!auth.token) return
  await auth.fetchMe()
  displayName.value = auth.user?.display_name || ''
  await loadAppPasswords()
})

async function loadAppPasswords() {
  if (!auth.token) return
  appPasswords.value = await api.listAppPasswords(auth.token)
}

async function saveProfile() {
  if (!auth.token) return
  busy.value = true
  await api.updateProfile(auth.token, displayName.value)
  await auth.fetchMe()
  message.value = 'Profile saved'
  busy.value = false
}

async function createAppPassword() {
  if (!auth.token || !newLabel.value) return
  const created = await api.createAppPassword(auth.token, newLabel.value)
  createdPassword.value = created.password || null
  newLabel.value = ''
  await loadAppPasswords()
}

async function revoke(id: string) {
  if (!auth.token) return
  await api.deleteAppPassword(auth.token, id)
  await loadAppPasswords()
}
</script>

<template>
  <div class="max-w-4xl mx-auto p-6">
    <h1 class="text-2xl font-bold text-gray-800 mb-2">{{ $t('app.account') }}</h1>

    <div class="flex gap-2 mb-4 border-b border-gray-200">
      <button
        v-for="t in ['profile', 'language', 'appPasswords']"
        :key="t"
        @click="tab = t as Tab"
        :class="{ 'border-b-2 border-blue-600 text-blue-600': tab === t }"
        class="px-4 py-2 text-sm font-medium text-gray-600 capitalize"
      >
        {{ $t(`app.${t}`) }}
      </button>
    </div>

    <div v-if="tab === 'profile'" class="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
      <h2 class="font-semibold text-gray-700">{{ $t('app.profile') }}</h2>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">{{ $t('auth.displayName') }}</label>
        <input v-model="displayName" class="w-full border rounded-lg px-3 py-2" />
      </div>
      <button
        @click="saveProfile"
        :disabled="busy"
        class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
      >
        {{ $t('app.save') }}
      </button>
      <p v-if="message" class="text-green-600 text-sm">{{ message }}</p>
    </div>

    <div v-if="tab === 'language'" class="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
      <h2 class="font-semibold text-gray-700">{{ $t('app.language') }}</h2>
      <LanguageSwitcher />
    </div>

    <div v-if="tab === 'appPasswords'" class="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
      <h2 class="font-semibold text-gray-700">{{ $t('app.appPasswords') }}</h2>
      <p class="text-sm text-gray-500">
        Use app passwords for CalDAV clients. Once you create one, your normal account password will no longer work for CalDAV.
      </p>

      <div class="flex gap-2">
        <input v-model="newLabel" placeholder="Label (e.g. Thunderbird)" class="flex-1 border rounded-lg px-3 py-2" />
        <button @click="createAppPassword" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
          {{ $t('app.add') }}
        </button>
      </div>

      <div v-if="createdPassword" class="bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-800">
        Created password: <code class="font-mono font-semibold">{{ createdPassword }}</code>
        <p class="text-xs mt-1">Copy it now — it won't be shown again.</p>
      </div>

      <ul class="divide-y divide-gray-100">
        <li v-for="ap in appPasswords" :key="ap.id" class="py-3 flex items-center justify-between">
          <div>
            <div class="font-medium text-gray-800">{{ ap.label }}</div>
            <div class="text-xs text-gray-500">
              Last used: {{ ap.last_used_at ? new Date(ap.last_used_at).toLocaleString() : 'Never' }}
            </div>
          </div>
          <button @click="revoke(ap.id)" class="text-red-600 hover:underline text-sm">{{ $t('app.delete') }}</button>
        </li>
      </ul>
    </div>
  </div>
</template>
