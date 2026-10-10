import { onMounted, ref } from 'vue'
import { i18n } from '@/i18n'
import { errorMessage } from '@/services/errors'
import { toast } from '@/services/toast'

/**
 * Loads a component's data when it mounts. `loading` starts out true, so nothing is rendered
 * from empty data before the first response; failures are reported as a toast.
 * Kept apart from useAction, so loading never blocks the user's actions.
 */
export function useLoader(loader: () => Promise<unknown>, options: { immediate?: boolean } = {}) {
  const loading = ref(options.immediate !== false)

  async function reload(): Promise<boolean> {
    loading.value = true
    try {
      await loader()
      return true
    } catch (error) {
      toast.error(errorMessage(error, i18n.global.t('app.loadFailed')))
      return false
    } finally {
      loading.value = false
    }
  }

  if (options.immediate !== false) onMounted(reload)

  return { loading, reload }
}
