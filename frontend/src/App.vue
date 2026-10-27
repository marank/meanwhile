<script setup lang="ts">
import { computed, onMounted, ref, watchEffect } from 'vue'
import { useRoute } from 'vue-router'
import AppNavbar from './components/AppNavbar.vue'
import CalendarSidebar from './components/CalendarSidebar.vue'
import DialogHost from './components/DialogHost.vue'
import ToastHost from './components/ToastHost.vue'
import { useBackSwipe } from './composables/useBackSwipe'
import { useMediaQuery } from './composables/useMediaQuery'
import { usePageTransition } from './composables/usePageTransition'
import { standaloneFramed } from './services/pageFrame'
import { useAuthStore } from './stores/auth'
import { useSettingsStore } from './stores/settings'

const auth = useAuthStore()
const settings = useSettingsStore()
const route = useRoute()

// Pages slide, fade or rise when they change (usePageTransition); in the home-screen app on phones, a
// swipe from the left edge goes back (useBackSwipe).
const main = ref<HTMLElement | null>(null)
const isPhone = useMediaQuery('(width < 40rem)')
const reducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)')
const homeScreenApp = useMediaQuery('(display-mode: standalone)')
const backSwipe = useBackSwipe({ scroller: main, enabled: () => isPhone.value && homeScreenApp.value })
const transition = usePageTransition({
  scroller: main,
  isPhone: () => isPhone.value,
  reducedMotion: () => reducedMotion.value,
  swiping: () => backSwipe.swiping.value,
})
// While pages move sideways, the one off to the side mustn't make the area scroll sideways.
const pagesMoving = ref(0)
const canSwipeBack = computed(() => isPhone.value && homeScreenApp.value && (route.meta.layer ?? 0) > 0)

// Signed in, pages come with navbar and sidebar; pages meant for anyone with a link may come without.
const framed = computed(() => auth.isLoggedIn && (!route.meta.standalone || standaloneFramed.value))

onMounted(settings.load)

watchEffect(() => {
  document.title = settings.appName
})

watchEffect(() => {
  const url = settings.faviconUrl
  if (!url) return
  // The page comes with ours in two formats; browsers would keep using the SVG one.
  const [link, ...others] = document.querySelectorAll<HTMLLinkElement>('link[rel="icon"]')
  others.forEach((other) => other.remove())
  const icon = link ?? document.head.appendChild(Object.assign(document.createElement('link'), { rel: 'icon' }))
  icon.removeAttribute('type')
  icon.removeAttribute('sizes')
  icon.href = url
})
</script>

<template>
  <!-- Added to the home screen, iOS runs the app edge to edge (viewport-fit=cover): keep clear of the
       status bar, the notch, the rounded corners and the home indicator. -->
  <div
    class="flex h-full flex-col pl-[env(safe-area-inset-left)] pr-[env(safe-area-inset-right)]"
    :class="{ 'pt-[var(--safe-top)]': !framed }"
  >
    <AppNavbar v-if="framed" />
    <div class="relative flex flex-1 overflow-hidden">
      <CalendarSidebar v-if="framed" />
      <main
        ref="main"
        class="relative min-w-0 flex-1 overflow-auto bg-surface-muted p-1 pb-[max(0.25rem,env(safe-area-inset-bottom))] sm:p-4 sm:pb-[max(1rem,env(safe-area-inset-bottom))]"
        :class="{ 'overflow-x-hidden': pagesMoving > 0, 'touch-pan-y': canSwipeBack }"
        v-on="backSwipe.handlers"
      >
        <router-view v-slot="{ Component }">
          <Transition
            :name="`page-${transition.name.value}`"
            :css="transition.name.value !== 'none'"
            @before-enter="pagesMoving++"
            @after-enter="pagesMoving--"
            @enter-cancelled="pagesMoving--"
            @before-leave="transition.beforeLeave"
            @after-leave="transition.afterLeave"
          >
            <KeepAlive :include="backSwipe.kept.value">
              <component :is="Component" />
            </KeepAlive>
          </Transition>
        </router-view>
      </main>
    </div>
    <DialogHost />
    <ToastHost />
  </div>
</template>
