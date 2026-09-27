<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{ mode?: 'login' | 'register' }>()

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const isRegister = computed(() => props.mode === 'register' || route.name === 'register')

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
    router.push('/calendar')
  } catch (e: any) {
    error.value = e.detail?.detail || e.message || 'Authentication failed'
  } finally {
    busy.value = false
  }
}

function toggleMode() {
  router.push(isRegister.value ? '/login' : '/register')
}
</script>

<template>
  <div class="min-h-full flex items-center justify-center bg-gray-50 p-6">
    <div class="w-full max-w-md bg-white rounded-xl shadow-md p-8">
      <div class="flex items-center justify-center gap-3 mb-6">
        <div class="w-10 h-10 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold text-xl">
          C
        </div>
        <h1 class="text-2xl font-bold text-gray-800">{{ $t('app.name') }}</h1>
      </div>

      <h2 class="text-lg font-medium text-gray-700 mb-4 text-center">
        {{ isRegister ? $t('auth.register') : $t('auth.login') }}
      </h2>

      <form @submit.prevent="submit" class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">{{ $t('auth.email') }}</label>
          <input
            v-model="email"
            type="email"
            required
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
          />
        </div>

        <div v-if="isRegister">
          <label class="block text-sm font-medium text-gray-700 mb-1">{{ $t('auth.displayName') }}</label>
          <input
            v-model="displayName"
            type="text"
            required
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">{{ $t('auth.password') }}</label>
          <input
            v-model="password"
            type="password"
            required
            minlength="8"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
          />
        </div>

        <p v-if="error" class="text-sm text-red-600 bg-red-50 dark:bg-red-900 dark:text-red-200 p-2 rounded">{{ error }}</p>

        <button
          type="submit"
          :disabled="busy"
          class="w-full py-2 px-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ isRegister ? $t('auth.register') : $t('auth.login') }}
        </button>
      </form>

      <p class="mt-4 text-center text-sm text-gray-600">
        <button @click="toggleMode" class="text-blue-600 hover:underline">
          {{ isRegister ? $t('auth.hasAccount') : $t('auth.noAccount') }}
        </button>
      </p>
    </div>
  </div>
</template>
