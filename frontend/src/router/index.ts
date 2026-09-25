import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/LoginView.vue'),
      props: { mode: 'register' },
      meta: { public: true },
    },
    {
      path: '/',
      redirect: '/calendar',
    },
    {
      path: '/calendar',
      name: 'calendar',
      component: () => import('@/views/CalendarView.vue'),
    },
    {
      path: '/approvals',
      name: 'approvals',
      component: () => import('@/views/ApprovalsView.vue'),
    },
    {
      path: '/settings/:calendarId',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue'),
    },
    {
      path: '/account',
      name: 'account',
      component: () => import('@/views/AccountView.vue'),
    },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  const hasToken = !!auth.token
  if (!to.meta.public && !hasToken) return '/login'
  if (to.meta.public && hasToken) return '/calendar'
})

export default router
