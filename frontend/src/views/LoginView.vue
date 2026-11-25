<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import AppLogo from '@/components/AppLogo.vue'
import { errorMessage } from '@/services/errors'
import { afterLogin } from '@/services/loginRedirect'
import { useAuthStore } from '@/stores/auth'
import { useSettingsStore } from '@/stores/settings'

const props = defineProps<{ mode?: 'login' | 'register' }>()

const auth = useAuthStore()
const settings = useSettingsStore()
const router = useRouter()
const route = useRoute()
const rulesId = useId()
const { t } = useI18n()

const isRegister = computed(() => props.mode === 'register')

// Where nobody may sign up (ALLOW_REGISTRATION), the login page doesn't offer it and /register leads there.
watch(
  () => [isRegister.value, settings.settings, settings.allowRegistration] as const,
  ([register, loaded, allowed]) => {
    if (register && loaded && !allowed) void router.replace('/login')
  },
  { immediate: true },
)

const email = ref('')
const displayName = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  error.value = ''
  busy.value = true
  try {
    if (isRegister.value) {
      await auth.register(email.value, displayName.value, password.value)
    } else {
      await auth.login(email.value, password.value)
    }
    await router.push(afterLogin(route.query.redirect))
  } catch (e) {
    error.value = errorMessage(e, t('app.actionFailed'))
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
        {{ isRegister ? $t('auth.register') : $t('auth.login') }}
      </h2>

      <form class="space-y-4" @submit.prevent="submit">
        <label class="block">
          <span class="block text-sm font-medium text-gray-700 mb-1">{{ $t('auth.email') }}</span>
          <input v-model="email" type="email" required class="w-full px-3 py-2 border border-line rounded-lg" />
        </label>

        <label v-if="isRegister" class="block">
          <span class="block text-sm font-medium text-gray-700 mb-1">{{ $t('auth.displayName') }}</span>
          <input v-model="displayName" type="text" required class="w-full px-3 py-2 border border-line rounded-lg" />
        </label>

        <div>
          <label class="block">
            <span class="block text-sm font-medium text-gray-700 mb-1">{{ $t('auth.password') }}</span>
            <input
              v-model="password"
              type="password"
              required
              minlength="8"
              :aria-describedby="isRegister ? rulesId : undefined"
              class="w-full px-3 py-2 border border-line rounded-lg"
            />
          </label>
          <!-- After the label, so it describes the field instead of becoming part of its name. -->
          <p v-if="isRegister" :id="rulesId" class="mt-1 text-xs text-gray-500">{{ $t('auth.passwordRules') }}</p>
        </div>

        <p v-if="error" class="text-sm text-red-600 bg-red-50 dark:bg-red-900 dark:text-red-200 p-2 rounded">
          {{ error }}
        </p>

        <button
          type="submit"
          :disabled="busy"
          class="w-full py-2 px-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ isRegister ? $t('auth.register') : $t('auth.login') }}
        </button>
      </form>

      <p v-if="!isRegister" class="mt-4 text-center text-sm">
        <RouterLink to="/forgot-password" class="text-blue-600 hover:underline">{{
          $t('auth.forgotPassword')
        }}</RouterLink>
      </p>
      <p v-if="isRegister || settings.allowRegistration" class="mt-4 text-center text-sm text-gray-600">
        <RouterLink :to="isRegister ? '/login' : '/register'" class="text-blue-600 hover:underline">
          {{ isRegister ? $t('auth.hasAccount') : $t('auth.noAccount') }}
        </RouterLink>
      </p>
    </div>
  </div>
</template>
