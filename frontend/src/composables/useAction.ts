import { ref } from 'vue'
import { i18n } from '@/i18n'
import { errorMessage } from '@/services/errors'
import { toast } from '@/services/toast'

interface ActionOptions {
  /**
   * Toast shown when the action succeeds; omitted means no toast. A function is called afterwards,
   * for texts that depend on what the action changed (e.g. the language).
   */
  success?: string | (() => string)
  /** Toast shown when the server gives no explanation of its own. */
  failure?: string
  /** Custom error text, e.g. for bookings whose conflicts need a translated explanation. */
  describeError?: (error: unknown) => string
}

/**
 * Runs user-triggered actions one at a time and reports the outcome as a toast.
 * `run` resolves to whether the action succeeded.
 */
export function useAction() {
  const busy = ref(false)

  async function run(action: () => Promise<unknown>, options: ActionOptions = {}): Promise<boolean> {
    if (busy.value) return false
    busy.value = true
    try {
      await action()
      const success = typeof options.success === 'function' ? options.success() : options.success
      if (success) toast.success(success)
      return true
    } catch (error) {
      const fallback = options.failure ?? i18n.global.t('app.actionFailed')
      toast.error(options.describeError?.(error) ?? errorMessage(error, fallback))
      return false
    } finally {
      busy.value = false
    }
  }

  return { busy, run }
}
