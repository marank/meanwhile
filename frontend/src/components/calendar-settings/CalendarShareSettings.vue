<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RotateCw } from 'lucide-vue-next'
import * as api from '@/api'
import SettingsPanel from '@/components/SettingsPanel.vue'
import { useAction } from '@/composables/useAction'
import { useLoader } from '@/composables/useLoader'
import { confirm } from '@/services/dialog'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{ calendarId: string }>()

const { t } = useI18n()
const auth = useAuthStore()
const { busy, run } = useAction()
const feedUrl = ref('')

const caldavUrl = computed(() => `${window.location.origin}/caldav/${auth.user?.email}/${props.calendarId}`)

const { loading } = useLoader(async () => {
  feedUrl.value = (await api.getFeedUrl(props.calendarId)).feed_url
})

async function rotateFeed() {
  if (!(await confirm(t('app.rotateFeedText'), t('app.rotateFeedTitle')))) return
  await run(
    async () => {
      feedUrl.value = (await api.rotateFeedToken(props.calendarId)).feed_url
    },
    { success: t('app.feedRotated') },
  )
}
</script>

<template>
  <SettingsPanel :title="$t('app.share')" :description="$t('app.shareDescription')" :loading="loading">
    <div class="space-y-6">
      <div>
        <h3 class="mb-1 font-semibold text-gray-700">{{ $t('app.feedUrl') }}</h3>
        <code class="block break-all rounded-lg border bg-surface-muted p-3 text-sm">{{ feedUrl }}</code>
        <button
          type="button"
          :disabled="busy"
          class="mt-2 inline-flex items-center gap-2 text-sm text-blue-600 hover:underline"
          @click="rotateFeed"
        >
          <RotateCw :size="16" />{{ $t('app.regenerateToken') }}
        </button>
      </div>
      <div>
        <h3 class="mb-1 font-semibold text-gray-700">{{ $t('app.caldavUrl') }}</h3>
        <code class="block break-all rounded-lg border bg-surface-muted p-3 text-sm">{{ caldavUrl }}</code>
      </div>
    </div>
  </SettingsPanel>
</template>
