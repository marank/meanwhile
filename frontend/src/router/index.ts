import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

declare module 'vue-router' {
  interface RouteMeta {
    /** Reachable without a session; logged-in users are sent to the calendar instead. */
    public?: boolean
    /** Reachable with and without a session. */
    anyone?: boolean
    /** Shown without navbar and sidebar, unless the page asks for them (`standaloneFramed`). */
    standalone?: boolean
    /** Only for administrators. */
    admin?: boolean
    /**
     * How deep in the app the page is: the calendar 0, pages opened from it (settings, notifications) 1.
     * On phones a deeper page slides in over the one below (App.vue). Pages without one change at once.
     */
    layer?: number
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
      // The link in the email allauth sends (HEADLESS_FRONTEND_URLS); the key authorizes the reset.
      // The invitation to an account without a password links here too, with ?invite=1.
      path: '/reset-password/:resetKey',
      name: 'reset-password',
      component: () => import('@/views/ResetPasswordView.vue'),
      props: (route) => ({ resetKey: route.params.resetKey, invite: route.query.invite === '1' }),
      meta: { anyone: true },
    },
    {
      // The event an invitation is for, and the answer to it, from the link in its email; the token is the key.
      path: '/invitation/:token',
      name: 'invitation',
      component: () => import('@/views/InvitationView.vue'),
      props: true,
      meta: { anyone: true, standalone: true },
    },
    {
      // The unsubscribe link in an email's footer; the token names the person and the kind of email.
      path: '/unsubscribe/:token',
      name: 'unsubscribe',
      component: () => import('@/views/UnsubscribeView.vue'),
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
      meta: { layer: 0 },
    },
    {
      path: '/calendar/:calendarId/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue'),
      props: true,
      meta: { layer: 1 },
    },
    {
      // An event, open over the calendar: where notifications lead.
      path: '/event/:eventId',
      name: 'event',
      component: () => import('@/views/CalendarView.vue'),
      props: true,
      meta: { layer: 0 },
    },
    {
      path: '/calendar/folder/:folderId',
      name: 'folder',
      component: () => import('@/views/CalendarView.vue'),
      props: true,
      meta: { layer: 0 },
    },
    {
      path: '/notifications',
      name: 'notifications',
      component: () => import('@/views/NotificationsView.vue'),
      meta: { layer: 1 },
    },
    {
      path: '/account',
      name: 'account',
      component: () => import('@/views/AccountView.vue'),
      meta: { layer: 1 },
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('@/views/AdminView.vue'),
      meta: { admin: true, layer: 1 },
    },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  // Pages open to anyone don't ask for the session (which, signed out, the server answers with 401).
  if (to.meta.anyone) {
    await auth.prepareCsrf().catch(() => {})
    return
  }
  await auth.init()
  if (!to.meta.public && !auth.isLoggedIn) return '/login'
  if (to.meta.public && auth.isLoggedIn) return '/calendar'
  if (to.meta.admin && !auth.isAdmin) return '/calendar'
})

export default router
