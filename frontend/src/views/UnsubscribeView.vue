<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import * as api from '@/api'
import AppLogo from '@/components/AppLogo.vue'
import { errorMessage } from '@/services/errors'
import { useSettingsStore } from '@/stores/settings'

// The page the unsubscribe links in an email's footer lead to, signed in or not: for a kind of email, or
// for the emails about one event. It asks before it unsubscribes (mail scanners open links by
// themselves), and can take it back: the app has no switch for an event.
const props = defineProps<{ token: string }>()

const { t } = useI18n()
const settings = useSettingsStore()

const subscription = ref<api.Subscription | null>(null)
const invalid = ref(false)
const error = ref('')
const busy = ref(false)

/** The texts' values, and which of them: about an event, or about a kind of email. */
const texts = computed(() => {
  const value = subscription.value
  if (!value) return null
  if (value.event_title !== null) return { suffix: 'Event', title: value.event_title, email: value.email }
  return { suffix: '', kind: t(`emailNotifications.${value.kind}`), email: value.email }
})

onMounted(async () => {
  try {
    subscription.value = await api.getSubscription(props.token)
  } catch {
    invalid.value = true
  }
})

async function change(subscribed: boolean) {
  error.value = ''
  busy.value = true
  try {
    subscription.value = await (subscribed ? api.resubscribe(props.token) : api.unsubscribe(props.token))
  } catch (e) {
    error.value = errorMessage(e, t('app.actionFailed'))
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="min-h-full flex items-center justify-center bg-surface-muted p-6">
    <div class="w-full max-w-md bg-surface rounded-xl shadow-md p-8">
      <div class="flex items-center justify-center gap-3 mb-6">
        <AppLogo size="lg" />
        <h1 class="text-2xl font-bold text-gray-800">{{ settings.appName }}</h1>
      </div>

      <h2 class="text-lg font-medium text-gray-700 mb-4 text-center">{{ $t('unsubscribe.title') }}</h2>

      <p v-if="invalid" class="text-sm text-gray-700">{{ $t('unsubscribe.invalid') }}</p>

      <div v-else-if="subscription && texts" class="space-y-4 text-sm text-gray-700 [overflow-wrap:anywhere]">
        <div v-if="!subscription.subscribed" role="status" class="space-y-2">
          <p>{{ $t(`unsubscribe.done${texts.suffix}`, texts) }}</p>
          <p class="text-gray-500">{{ $t(`unsubscribe.undoHint${texts.suffix}`) }}</p>
        </div>
        <p v-else>{{ $t(`unsubscribe.question${texts.suffix}`, texts) }}</p>
        <p v-if="error" class="text-red-600 bg-red-50 dark:bg-red-900 dark:text-red-200 p-2 rounded">
          {{ error }}
        </p>
        <button
          v-if="subscription.subscribed"
          type="button"
          :disabled="busy"
          class="w-full py-2 px-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          @click="change(false)"
        >
          {{ $t('unsubscribe.confirm') }}
        </button>
        <button
          v-else
          type="button"
          :disabled="busy"
          class="w-full py-2 px-4 border border-line rounded-lg hover:bg-hover disabled:opacity-50 disabled:cursor-not-allowed"
          @click="change(true)"
        >
          {{ $t('unsubscribe.undo') }}
        </button>
      </div>

      <p v-if="invalid || subscription" class="mt-4 text-center text-sm">
        <RouterLink
          :to="{ path: '/account', query: { tab: 'emailNotifications' } }"
          class="text-blue-600 hover:underline"
        >
          {{ $t('unsubscribe.settings') }}
        </RouterLink>
      </p>
    </div>
  </div>
</template>
