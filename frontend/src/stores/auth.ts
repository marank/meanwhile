import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as api from '@/api'

const TOKEN_KEY = 'calendar_token'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const user = ref<api.User | null>(null)
  const loading = ref(false)

  const isLoggedIn = computed(() => !!token.value && !!user.value)

  function setToken(newToken: string | null) {
    token.value = newToken
    if (newToken) {
      localStorage.setItem(TOKEN_KEY, newToken)
    } else {
      localStorage.removeItem(TOKEN_KEY)
    }
  }

  async function fetchMe() {
    if (!token.value) return
    loading.value = true
    try {
      user.value = await api.me(token.value)
    } catch {
      setToken(null)
      user.value = null
    } finally {
      loading.value = false
    }
  }

  async function login(email: string, password: string) {
    const resp = await api.login({ email, password })
    setToken(resp.access_token)
    await fetchMe()
  }

  async function register(email: string, displayName: string, password: string) {
    const resp = await api.register({ email, display_name: displayName, password })
    setToken(resp.access_token)
    await fetchMe()
  }

  function logout() {
    setToken(null)
    user.value = null
  }

  return {
    token,
    user,
    loading,
    isLoggedIn,
    login,
    register,
    logout,
    fetchMe,
    setToken,
  }
})
