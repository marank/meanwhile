<script setup lang="ts">
import { computed, ref, useId } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import * as api from '@/api'
import AppLogo from '@/components/AppLogo.vue'
import { errorMessage } from '@/services/errors'
import { useAuthStore } from '@/stores/auth'
import { useSettingsStore } from '@/stores/settings'

/**
 * Without a key: asking for the link by email. With the key from that link: setting the new password.
 * `invite`: the link came with the invitation to a new account, which has no password yet.
 */
const props = defineProps<{ resetKey?: string; invite?: boolean }>()

const settings = useSettingsStore()
const rulesId = useId()
const auth = useAuthStore()
const router = useRouter()
const { t } = useI18n()

const settingNew = computed(() => !!props.resetKey)

const email = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)
/** The link was sent, or the password set. */
const done = ref(false)

async function submit() {
  error.value = ''
  busy.value = true
  try {
    if (settingNew.value && (await api.resetPassword(props.resetKey!, password.value))) {
      // Signed in with the new password, in place of anyone who was signed in in this browser before.
      auth.clearSession()
      await router.push('/calendar')
      return
    }
    if (!settingNew.value) await api.requestPasswordReset(email.value)
    done.value = true
  } catch (e) {
    // allauth answers an unknown, used or expired key with an error on the field "key".
    const badKey = e instanceof api.ApiError && JSON.stringify(e.detail).includes('"param":"key"')
    error.value = badKey ? t('auth.resetInvalid') : errorMessage(e, t('app.actionFailed'))
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="min-h-full flex items-center justify-center bg-surface-muted p-6">
    <div class="w-full max-w-md bg-surface rounded-xl shadow-md p-8">
      <div class="flex items-center justify-center gap-3 mb-6">
        <AppLogo size="lg" />
        <h1 class="text-2xl font-bold text-gray-800">{{ settings.appName }}</h1>
      </div>

      <h2 class="text-lg font-medium text-gray-700 mb-4 text-center">
        {{ settingNew && invite ? $t('auth.inviteTitle') : $t('auth.resetTitle') }}
      </h2>

      <p v-if="done" class="text-sm text-gray-700" role="status">
        {{ settingNew ? $t('auth.resetDone') : $t('auth.resetSent') }}
      </p>

      <form v-else class="space-y-4" @submit.prevent="submit">
        <div v-if="settingNew">
          <label for="new-password" class="block text-sm font-medium text-gray-700 mb-1">
            {{ $t('auth.newPassword') }}
          </label>
          <input
            id="new-password"
            v-model="password"
            type="password"
            autocomplete="new-password"
            required
            minlength="8"
            :aria-describedby="rulesId"
            class="w-full px-3 py-2 border border-line rounded-lg"
          />
          <span :id="rulesId" class="mt-1 block text-xs text-gray-500">{{ $t('auth.passwordRules') }}</span>
        </div>
        <template v-else>
          <p class="text-sm text-gray-600">{{ $t('auth.resetRequestHelp') }}</p>
          <div>
            <label for="reset-email" class="block text-sm font-medium text-gray-700 mb-1">{{ $t('auth.email') }}</label>
            <input
              id="reset-email"
              v-model="email"
              type="email"
              autocomplete="email"
              required
              class="w-full px-3 py-2 border border-line rounded-lg"
            />
          </div>
        </template>

        <p v-if="error" class="text-sm text-red-600 bg-red-50 dark:bg-red-900 dark:text-red-200 p-2 rounded">
          {{ error }}
        </p>

        <button
          type="submit"
          :disabled="busy"
          class="w-full py-2 px-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ settingNew ? $t('auth.setPassword') : $t('auth.resetSend') }}
        </button>
      </form>

      <p class="mt-4 text-center text-sm">
        <RouterLink to="/login" class="text-blue-600 hover:underline">{{ $t('auth.backToLogin') }}</RouterLink>
      </p>
    </div>
  </div>
</template>
