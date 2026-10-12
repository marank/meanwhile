import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import tailwindcss from '@tailwindcss/vite'

// The backend behind the dev proxy; BACKEND_URL in docker-compose.dev.yml.
const backendUrl = process.env.BACKEND_URL ?? 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), tailwindcss(), vueDevTools()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: backendUrl,
        changeOrigin: true,
      },
      '/ics': {
        target: backendUrl,
        changeOrigin: true,
      },
      '/.well-known/caldav': {
        target: backendUrl,
        changeOrigin: true,
      },
      '/caldav': {
        target: backendUrl,
        changeOrigin: true,
      },
      // Live updates; the dev server passes the WebSocket upgrade on.
      '/ws': {
        target: backendUrl,
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
