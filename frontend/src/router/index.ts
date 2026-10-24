import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

declare module 'vue-router' {
  interface RouteMeta {
    /** Reachable without a session; logged-in users are sent to the calendar instead. */
    public?: boolean
    /** Reachable with and without a session. */
    anyone?: boolean
    /** Only for administrators. */
    admin?: boolean
  }
}

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
      path: '/forgot-password',
      name: 'forgot-password',
      component: () => import('@/views/ResetPasswordView.vue'),
      meta: { public: true },
    },
    {
      // Answering an invitation from the link in its email; the token is the key.
      path: '/rsvp/:token',
      name: 'rsvp',
      component: () => import('@/views/RsvpView.vue'),
      props: true,
      meta: { anyone: true },
    },
    {
      path: '/',
      redirect: '/calendar',
    },
    {
      path: '/calendar/:calendarId?',
      name: 'calendar',
      component: () => import('@/views/CalendarView.vue'),
      props: true,
    },
    {
      path: '/calendar/folder/:folderId',
      name: 'folder',
      component: () => import('@/views/CalendarView.vue'),
      props: true,
    },
    {
      path: '/notifications',
      name: 'notifications',
      component: () => import('@/views/NotificationsView.vue'),
    },
    {
      path: '/settings/:calendarId',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue'),
      props: true,
    },
    {
      path: '/account',
      name: 'account',
      component: () => import('@/views/AccountView.vue'),
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('@/views/AdminView.vue'),
      meta: { admin: true },
    },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  await auth.init()
  if (to.meta.anyone) return
  if (!to.meta.public && !auth.isLoggedIn) return '/login'
  if (to.meta.public && auth.isLoggedIn) return '/calendar'
  if (to.meta.admin && !auth.isAdmin) return '/calendar'
})

export default router
