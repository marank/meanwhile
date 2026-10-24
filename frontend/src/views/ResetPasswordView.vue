<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import * as api from '@/api'
import AppLogo from '@/components/AppLogo.vue'
import { errorMessage } from '@/services/errors'
import { useSettingsStore } from '@/stores/settings'

const settings = useSettingsStore()
const { t } = useI18n()

/** First the email address, then the code from the email with the new password, then done. The code
 * works in this browser session only, so both steps happen on this page. */
const step = ref<'email' | 'code' | 'done'>('email')
const email = ref('')
const code = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  error.value = ''
  busy.value = true
  try {
    if (step.value === 'email') {
      await api.requestPasswordReset(email.value)
      step.value = 'code'
    } else {
      await api.resetPassword(code.value.trim(), password.value)
      step.value = 'done'
    }
  } catch (e) {
    // allauth answers a wrong or expired code with an error on the field "key".
    const badCode = e instanceof api.ApiError && JSON.stringify(e.detail).includes('"param":"key"')
    error.value = badCode ? t('auth.resetInvalid') : errorMessage(e, t('app.actionFailed'))
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

      <h2 class="text-lg font-medium text-gray-700 mb-4 text-center">{{ $t('auth.resetTitle') }}</h2>

      <p v-if="step === 'done'" class="text-sm text-gray-700" role="status">{{ $t('auth.resetDone') }}</p>

      <form v-else class="space-y-4" @submit.prevent="submit">
        <template v-if="step === 'email'">
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
        <template v-else>
          <p class="text-sm text-gray-600" role="status">{{ $t('auth.resetSent') }}</p>
          <div>
            <label for="reset-code" class="block text-sm font-medium text-gray-700 mb-1">
              {{ $t('auth.resetCode') }}
            </label>
            <input
              id="reset-code"
              v-model="code"
              type="text"
              autocomplete="one-time-code"
              required
              class="w-full px-3 py-2 border border-line rounded-lg font-mono tracking-widest"
            />
          </div>
          <div>
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
          {{ step === 'email' ? $t('auth.resetSend') : $t('auth.setPassword') }}
        </button>
      </form>

      <p class="mt-4 text-center text-sm">
        <RouterLink to="/login" class="text-blue-600 hover:underline">{{ $t('auth.backToLogin') }}</RouterLink>
      </p>
    </div>
  </div>
</template>
