import './assets/main.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { i18n } from './i18n'
import { useAuthStore } from './stores/auth'
import { useThemeStore } from './stores/theme'

const app = createApp(App)

app.use(createPinia())
app.use(i18n)
app.use(router)

useThemeStore().init()
const auth = useAuthStore()
auth.fetchMe().then(() => {
  app.mount('#app')
})
