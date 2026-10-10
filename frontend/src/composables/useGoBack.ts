import { useRouter } from 'vue-router'

/**
 * Returns to the previous page of the app. A page opened directly (bookmark, new tab) has none,
 * so it goes to `fallback` instead of leaving the app.
 */
export function useGoBack(defaultFallback = '/calendar') {
  const router = useRouter()

  return function goBack(fallback = defaultFallback) {
    if (router.options.history.state.back) router.back()
    else router.push(fallback)
  }
}
