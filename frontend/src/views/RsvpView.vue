<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import * as api from '@/api'
import AppLogo from '@/components/AppLogo.vue'
import { formatDate, formatDateTime, formatTime } from '@/services/datetime'
import { errorMessage } from '@/services/errors'
import { participantStatusLabel } from '@/services/labels'
import { useSettingsStore } from '@/stores/settings'

type Answer = Exclude<api.ParticipantStatus, 'needs_action'>

// The page anyone with the link in an invitation email reaches, with or without an account.
const props = defineProps<{ token: string }>()

const { t } = useI18n()
const route = useRoute()
const settings = useSettingsStore()

const invitation = ref<api.Invitation | null>(null)
const missing = ref(false)
const error = ref('')
const busy = ref(false)
const answered = ref(false)

// The link in the email names an answer, but only a click here gives it: mail scanners open
// links by themselves.
const suggested = computed(() => {
  const answer = route.query.answer
  return answer === 'accepted' || answer === 'tentative' || answer === 'declined' ? answer : null
})

const answers = computed<Array<{ value: Answer; label: string }>>(() => [
  { value: 'accepted', label: t('notifications.accept') },
  { value: 'tentative', label: t('notifications.tentative') },
  { value: 'declined', label: t('notifications.decline') },
])

const when = computed(() => {
  const event = invitation.value
  if (!event) return ''
  if (event.all_day) {
    const first = formatDate(event.start)
    const last = formatDate(event.end)
    return first === last ? first : `${first} – ${last}`
  }
  const sameDay = formatDate(event.start) === formatDate(event.end)
  return `${formatDateTime(event.start)} – ${sameDay ? formatTime(event.end) : formatDateTime(event.end)}`
})

async function load() {
  try {
    invitation.value = await api.getInvitation(props.token)
  } catch {
    missing.value = true
  }
}

async function answer(status: Answer) {
  error.value = ''
  busy.value = true
  try {
    invitation.value = await api.answerInvitation(props.token, status)
    answered.value = true
  } catch (e) {
    error.value = errorMessage(e, t('app.actionFailed'))
  } finally {
    busy.value = false
  }
}

void load()
</script>

<template>
  <div class="min-h-full flex items-center justify-center bg-surface-muted p-6">
    <div class="w-full max-w-md bg-surface rounded-xl shadow-md p-8">
      <div class="flex items-center justify-center gap-3 mb-6">
        <AppLogo size="lg" />
        <h1 class="text-2xl font-bold text-gray-800">{{ settings.appName }}</h1>
      </div>

      <p v-if="missing" class="text-sm text-gray-600 text-center">{{ $t('rsvp.notFound') }}</p>

      <template v-else-if="invitation">
        <p class="text-xs font-semibold uppercase tracking-wide text-gray-500">{{ $t('rsvp.title') }}</p>
        <h2 class="mt-1 text-xl font-semibold text-gray-800">{{ invitation.title || $t('reminders.untitled') }}</h2>
        <dl class="mt-3 space-y-1 text-sm text-gray-700">
          <div>
            <dt class="sr-only">{{ $t('event.start') }}</dt>
            <dd>{{ when }}</dd>
          </div>
          <div v-if="invitation.rrule" class="text-gray-500">{{ $t('rsvp.repeats') }}</div>
          <div v-if="invitation.location">
            <dt class="sr-only">{{ $t('event.location') }}</dt>
            <dd>{{ invitation.location }}</dd>
          </div>
        </dl>
        <p v-if="invitation.description" class="mt-3 whitespace-pre-line text-sm text-gray-600">
          {{ invitation.description }}
        </p>
        <p class="mt-4 text-sm text-gray-500">
          {{ $t('rsvp.invitedBy', { name: invitation.organizer_name, email: invitation.email }) }}
        </p>

        <p
          v-if="invitation.cancelled"
          class="mt-6 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900 dark:text-red-200"
        >
          {{ $t('rsvp.cancelled') }}
        </p>
        <div v-else class="mt-6 border-t border-line pt-4">
          <p v-if="answered" class="mb-3 text-sm font-medium text-green-700 dark:text-green-300">
            {{ $t('rsvp.answered') }}
          </p>
          <p v-else-if="invitation.status !== 'needs_action'" class="mb-3 text-sm text-gray-600">
            {{ $t('rsvp.current', { answer: participantStatusLabel(invitation.status) }) }}
          </p>
          <p v-else class="mb-3 text-sm text-gray-600">{{ $t('rsvp.confirmHint') }}</p>
          <div class="flex flex-wrap gap-2" role="group" :aria-label="$t('rsvp.yourAnswer')">
            <button
              v-for="option in answers"
              :key="option.value"
              type="button"
              :disabled="busy"
              :aria-pressed="invitation.status === option.value"
              class="rounded-lg px-4 py-2 text-sm disabled:opacity-50"
              :class="
                invitation.status === option.value ||
                (invitation.status === 'needs_action' && suggested === option.value)
                  ? 'bg-blue-600 text-white hover:bg-blue-700'
                  : 'border border-line text-gray-700 hover:bg-surface-muted'
              "
              @click="answer(option.value)"
            >
              {{ option.label }}
            </button>
          </div>
          <p v-if="error" class="mt-3 text-sm text-red-600">{{ error }}</p>
        </div>
      </template>
    </div>
  </div>
</template>
