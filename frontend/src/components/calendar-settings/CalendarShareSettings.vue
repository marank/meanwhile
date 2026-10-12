<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Check, Copy, RotateCw, X } from 'lucide-vue-next'
import * as api from '@/api'
import SettingsPanel from '@/components/SettingsPanel.vue'
import { useAction } from '@/composables/useAction'
import { useLoader } from '@/composables/useLoader'
import { confirm } from '@/services/dialog'
import { useAuthStore } from '@/stores/auth'
import { useCalendarStore } from '@/stores/calendars'

const props = defineProps<{ calendar: api.Calendar; canManage: boolean }>()
const emit = defineEmits<{ updated: [calendar: api.Calendar] }>()

const { t } = useI18n()
const auth = useAuthStore()
const calendarStore = useCalendarStore()
const { busy, run } = useAction()
const feedUrl = ref('')
const urlPath = ref(props.calendar.url_path ?? '')
const origin = window.location.origin

const calendarUrl = computed(() => `${origin}/calendar/${urlPath.value || props.calendar.id}`)
const caldavUrl = computed(() => `${window.location.origin}/caldav/${auth.user?.email}/${props.calendar.id}`)

const { loading } = useLoader(async () => {
  feedUrl.value = (await api.getFeedUrl(props.calendar.id)).feed_url
})

async function saveCalendarUrl() {
  await run(
    async () => {
      const calendar = await calendarStore.updateCalendar(props.calendar.id, { url_path: urlPath.value || null })
      urlPath.value = calendar.url_path ?? ''
      emit('updated', calendar)
    },
    { success: t('app.calendarUrlSaved') },
  )
}

async function clearCalendarUrl() {
  urlPath.value = ''
  await saveCalendarUrl()
}

async function copyUrl(url: string) {
  await run(() => navigator.clipboard.writeText(url), { success: t('app.urlCopied') })
}

async function rotateFeed() {
  if (!(await confirm(t('app.rotateFeedText'), t('app.rotateFeedTitle')))) return
  await run(
    async () => {
      feedUrl.value = (await api.rotateFeedToken(props.calendar.id)).feed_url
    },
    { success: t('app.feedRotated') },
  )
}
</script>

<template>
  <SettingsPanel :title="$t('app.share')" :description="$t('app.shareDescription')" :loading="loading">
    <div class="space-y-6">
      <form @submit.prevent="saveCalendarUrl">
        <label for="calendar-url" class="mb-1 block font-semibold text-gray-700">{{ $t('app.calendarUrl') }}</label>
        <p class="mb-2 text-sm text-gray-500">{{ $t('app.calendarUrlHelp') }}</p>
        <div
          class="flex min-h-11 w-full items-center overflow-hidden rounded-lg border border-line bg-input focus-within:border-blue-500 focus-within:ring-1 focus-within:ring-blue-500"
        >
          <span class="shrink-0 pl-3 text-sm text-gray-500">{{ `${origin}/calendar/` }}</span>
          <input
            id="calendar-url"
            v-model="urlPath"
            type="text"
            :placeholder="$t('app.calendarUrlPlaceholder')"
            :disabled="!canManage || busy"
            pattern="[a-z0-9]+(?:-[a-z0-9]+)*"
            maxlength="100"
            class="min-h-11 min-w-0 flex-1 border-0 px-1 py-3 text-sm shadow-none focus:shadow-none disabled:cursor-not-allowed disabled:opacity-60"
          />
          <button
            v-if="canManage"
            type="submit"
            :disabled="busy"
            :title="$t('app.save')"
            :aria-label="$t('app.save')"
            class="self-stretch border-l border-line px-2.5 text-blue-600 transition-colors hover:bg-hover disabled:opacity-50"
          >
            <Check :size="17" />
          </button>
          <button
            v-if="canManage"
            type="button"
            :disabled="busy || !urlPath"
            :title="$t('app.clear')"
            :aria-label="$t('app.clear')"
            class="self-stretch border-l border-line px-2.5 text-gray-500 transition-colors hover:bg-hover hover:text-gray-800 disabled:opacity-50"
            @click="clearCalendarUrl"
          >
            <X :size="17" />
          </button>
          <button
            type="button"
            :disabled="busy"
            :title="$t('app.copyUrl')"
            :aria-label="$t('app.copyUrl')"
            class="self-stretch border-l border-line px-2.5 text-gray-500 transition-colors hover:bg-hover hover:text-gray-800 disabled:opacity-50"
            @click="copyUrl(calendarUrl)"
          >
            <Copy :size="17" />
          </button>
        </div>
      </form>
      <div>
        <h3 class="mb-1 font-semibold text-gray-700">{{ $t('app.feedUrl') }}</h3>
        <p class="mb-2 text-sm text-gray-500">{{ $t('app.feedUrlHelp') }}</p>
        <div class="flex min-h-11 overflow-hidden rounded-lg border bg-surface-muted">
          <code class="min-w-0 flex-1 break-all p-3 text-sm">{{ feedUrl }}</code>
          <button
            type="button"
            :disabled="busy || !feedUrl"
            :title="$t('app.copyUrl')"
            :aria-label="$t('app.copyUrl')"
            class="shrink-0 border-l border-line px-3 text-gray-500 transition-colors hover:bg-hover hover:text-gray-800 disabled:opacity-50"
            @click="copyUrl(feedUrl)"
          >
            <Copy :size="17" />
          </button>
        </div>
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
        <p class="mb-2 text-sm text-gray-500">{{ $t('app.caldavUrlHelp') }}</p>
        <div class="flex min-h-11 overflow-hidden rounded-lg border bg-surface-muted">
          <code class="min-w-0 flex-1 break-all p-3 text-sm">{{ caldavUrl }}</code>
          <button
            type="button"
            :disabled="busy"
            :title="$t('app.copyUrl')"
            :aria-label="$t('app.copyUrl')"
            class="shrink-0 border-l border-line px-3 text-gray-500 transition-colors hover:bg-hover hover:text-gray-800 disabled:opacity-50"
            @click="copyUrl(caldavUrl)"
          >
            <Copy :size="17" />
          </button>
        </div>
      </div>
    </div>
  </SettingsPanel>
</template>
