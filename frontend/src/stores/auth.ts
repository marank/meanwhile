import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as api from '@/api'

export const useAuthStore = defineStore('auth', () => {
  // `token` is kept for compatibility with components that still pass it,
  // but it is no longer used for authentication (session cookie instead).
  const token = ref<string | null>(null)
  const user = ref<api.User | null>(null)
  const loading = ref(false)
  const initialized = ref(false)

  const isLoggedIn = computed(() => !!user.value)
  const isAdmin = computed(() => !!user.value?.is_admin)

  async function init() {
    if (initialized.value) return
    loading.value = true
    try {
      await api.getCsrf()
      user.value = await api.me()
    } catch {
      user.value = null
    } finally {
      loading.value = false
      initialized.value = true
    }
  }

  async function fetchMe() {
    loading.value = true
    try {
      user.value = await api.me()
    } catch {
      user.value = null
    } finally {
      loading.value = false
    }
  }

  async function login(email: string, password: string) {
    user.value = await api.login({ email, password })
  }

  async function register(email: string, displayName: string, password: string) {
    user.value = await api.register({ email, display_name: displayName, password })
  }

  async function logout() {
    try {
      await api.logout()
    } catch {
      // ignore
    }
    token.value = null
    user.value = null
    initialized.value = false
  }

  return {
    token,
    user,
    loading,
    initialized,
    isLoggedIn,
    isAdmin,
    login,
    register,
    logout,
    init,
    fetchMe,
  }
})
