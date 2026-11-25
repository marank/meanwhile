import './assets/main.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { i18n } from './i18n'
import { setUnauthorizedHandler } from './api'
import { loginRoute } from './services/loginRedirect'
import { useAuthStore } from './stores/auth'
import { useThemeStore } from './stores/theme'

const app = createApp(App)

app.use(createPinia())
app.use(i18n)
app.use(router)

useThemeStore().init()

// An expired session ends up on the login page instead of failing every action.
setUnauthorizedHandler(() => {
  const auth = useAuthStore()
  if (!auth.isLoggedIn) return
  auth.clearSession()
  void router.push(loginRoute(router.currentRoute.value.fullPath))
})

app.mount('#app')
