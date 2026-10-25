<script setup lang="ts">
import { CalendarPlus, Check, CircleHelp, Clock, MapPin, Repeat, User, X } from '@lucide/vue'
import { computed, ref, type Component } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import * as api from '@/api'
import AppLogo from '@/components/AppLogo.vue'
import { browserTimeZone, formatDateTime, formatLongDate, formatTime, monthName } from '@/services/datetime'
import { errorMessage } from '@/services/errors'
import { participantStatusLabel, recurrenceSummary } from '@/services/labels'
import { useSettingsStore } from '@/stores/settings'

type Answer = Exclude<api.ParticipantStatus, 'needs_action'>

// The page anyone with the link in an invitation email reaches, with or without an account: the event
// as the invitation has it, who else is invited, and the answer, which can be changed until it starts.
const props = defineProps<{ token: string }>()

const { t } = useI18n()
const route = useRoute()
const settings = useSettingsStore()

const invitation = ref<api.Invitation | null>(null)
const missing = ref(false)
const error = ref('')
const busy = ref(false)
// Counts given answers: the chosen button's icon is drawn anew for each, which plays its animation.
const answerCount = ref(0)

// The link in the email names an answer, but only a click here gives it: mail scanners open
// links by themselves.
const suggested = computed(() => {
  const answer = route.query.answer
  return answer === 'accepted' || answer === 'tentative' || answer === 'declined' ? answer : null
})

// The link from the email preselects an answer that only a click gives; until then, say it isn't saved.
const unsaved = computed(() => !!suggested.value && invitation.value?.status === 'needs_action')

const statusIcons: Record<api.ParticipantStatus, Component> = {
  accepted: Check,
  tentative: CircleHelp,
  declined: X,
  needs_action: Clock,
}
const statusColors: Record<api.ParticipantStatus, string> = {
  accepted: 'text-green-600 dark:text-green-400',
  tentative: 'text-amber-600 dark:text-amber-400',
  declined: 'text-red-600 dark:text-red-400',
  needs_action: 'text-gray-400',
}
// Each answer in its colour: outlined while not chosen, filled once it is.
const answerColors: Record<Answer, { open: string; chosen: string; suggested: string; glow: string }> = {
  accepted: {
    open: 'border-green-600 text-green-700 hover:bg-green-50 dark:border-green-500 dark:text-green-400 dark:hover:bg-green-950',
    chosen: 'border-green-600 bg-green-600 text-white',
    suggested: 'ring-green-600/40',
    glow: '#16a34a',
  },
  tentative: {
    open: 'border-amber-500 text-amber-700 hover:bg-amber-50 dark:text-amber-400 dark:hover:bg-amber-950',
    chosen: 'border-amber-500 bg-amber-500 text-white',
    suggested: 'ring-amber-500/40',
    glow: '#f59e0b',
  },
  declined: {
    open: 'border-red-600 text-red-700 hover:bg-red-50 dark:border-red-500 dark:text-red-400 dark:hover:bg-red-950',
    chosen: 'border-red-600 bg-red-600 text-white',
    suggested: 'ring-red-600/40',
    glow: '#dc2626',
  },
}

const answers = computed<Array<{ value: Answer; label: string }>>(() => [
  { value: 'accepted', label: t('notifications.accept') },
  { value: 'tentative', label: t('notifications.tentative') },
  { value: 'declined', label: t('notifications.decline') },
])

/** All-day values are midnight UTC: the calendar day, the same in every zone. */
function day(value: string, allDay: boolean): Date {
  if (!allDay) return new Date(value)
  const [year, month, date] = value.slice(0, 10).split('-').map(Number)
  return new Date(year!, month! - 1, date)
}

const start = computed(() => invitation.value && day(invitation.value.start, invitation.value.all_day))

// The day, written out, and the time below it; an event over several days names both.
const when = computed(() => {
  const event = invitation.value
  if (!event || !start.value) return null
  const end = day(event.end, event.all_day)
  if (event.all_day) {
    const sameDay = start.value.toDateString() === end.toDateString()
    return {
      date: sameDay ? formatLongDate(start.value) : `${formatLongDate(start.value)} –\n${formatLongDate(end)}`,
      time: t('event.allDay'),
    }
  }
  if (start.value.toDateString() !== end.toDateString()) {
    return { date: `${formatDateTime(start.value)} –\n${formatDateTime(end)}`, time: '' }
  }
  return { date: formatLongDate(start.value), time: `${formatTime(start.value)} – ${formatTime(end)}` }
})

const repeats = computed(() =>
  invitation.value?.rrule && start.value ? recurrenceSummary(invitation.value.rrule, start.value) : '',
)
// Times are shown in the reader's zone; say so where the event was planned in another.
const otherZone = computed(() =>
  invitation.value && !invitation.value.all_day && invitation.value.timezone !== browserTimeZone()
    ? browserTimeZone()
    : '',
)
const icsUrl = computed(() => api.invitationIcsUrl(props.token))
const mapUrl = computed(
  () => `https://www.openstreetmap.org/search?query=${encodeURIComponent(invitation.value?.location ?? '')}`,
)

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
    answerCount.value++
  } catch (e) {
    error.value = errorMessage(e, t('app.actionFailed'))
  } finally {
    busy.value = false
  }
}

void load()
</script>

<template>
  <div class="min-h-full bg-surface-muted px-4 py-6 sm:py-12">
    <div class="mx-auto w-full max-w-lg">
      <div class="mb-4 flex items-center gap-2 px-1">
        <AppLogo />
        <span class="font-semibold text-gray-700">{{ settings.appName }}</span>
      </div>

      <div class="overflow-hidden rounded-xl bg-surface shadow-md">
        <p v-if="missing" class="p-6 text-center text-sm text-gray-600 sm:p-8">{{ $t('rsvp.notFound') }}</p>
        <p v-else-if="!invitation" class="p-6 text-center text-sm text-gray-500 sm:p-8">{{ $t('app.loading') }}</p>

        <template v-else>
          <p
            v-if="invitation.cancelled"
            class="bg-red-50 px-6 py-3 text-sm font-medium text-red-700 sm:px-8 dark:bg-red-900 dark:text-red-200"
            role="status"
          >
            {{ $t('rsvp.cancelled') }}
          </p>

          <div class="p-6 sm:p-8">
            <p class="text-xs font-semibold uppercase tracking-wide text-gray-500">
              {{
                invitation.organizer_name ? $t('rsvp.from', { name: invitation.organizer_name }) : $t('rsvp.invitation')
              }}
            </p>
            <h1
              class="mt-1 text-2xl font-semibold text-gray-800"
              :class="{ 'line-through decoration-2 opacity-60': invitation.cancelled }"
            >
              {{ invitation.title || $t('reminders.untitled') }}
            </h1>

            <div v-if="start && when" class="mt-5 flex items-start gap-4">
              <!-- A leaf of a tear-off calendar: month and day at a glance. -->
              <div
                class="flex w-14 shrink-0 flex-col overflow-hidden rounded-lg border border-line text-center"
                aria-hidden="true"
              >
                <span class="bg-blue-600 py-0.5 text-xs font-semibold uppercase text-white">
                  {{ monthName(start.getMonth() + 1, 'short') }}
                </span>
                <span class="py-1 text-xl font-semibold text-gray-800">{{ start.getDate() }}</span>
              </div>
              <div class="min-w-0 text-sm">
                <p class="whitespace-pre-line font-medium text-gray-800" data-when>{{ when.date }}</p>
                <p v-if="when.time" class="text-gray-600">{{ when.time }}</p>
                <p v-if="repeats" class="mt-1 flex items-center gap-1.5 text-gray-600">
                  <Repeat :size="14" aria-hidden="true" />{{ repeats }}
                </p>
                <p v-if="otherZone" class="mt-1 text-xs text-gray-500">
                  {{ $t('rsvp.yourTimeZone', { zone: otherZone }) }}
                </p>
              </div>
            </div>

            <dl class="mt-5 space-y-3 text-sm">
              <div v-if="invitation.location" class="flex items-start gap-3">
                <dt class="mt-0.5 text-gray-400"><MapPin :size="16" :aria-label="$t('event.location')" /></dt>
                <dd class="min-w-0">
                  <a
                    :href="mapUrl"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="text-gray-800 underline decoration-gray-300 underline-offset-2 hover:decoration-gray-500"
                    :title="$t('rsvp.showMap')"
                    >{{ invitation.location }}</a
                  >
                </dd>
              </div>
              <div v-if="invitation.organizer_name" class="flex items-start gap-3">
                <dt class="mt-0.5 text-gray-400"><User :size="16" :aria-label="$t('rsvp.organizer')" /></dt>
                <dd class="min-w-0 text-gray-800">{{ invitation.organizer_name }}</dd>
              </div>
            </dl>

            <p
              v-if="invitation.description"
              class="mt-5 whitespace-pre-line border-t border-line pt-5 text-sm text-gray-700"
            >
              {{ invitation.description }}
            </p>

            <section v-if="invitation.participants.length" class="mt-5 border-t border-line pt-5">
              <h2 class="text-sm font-semibold text-gray-700">
                {{ $t('rsvp.participants', { count: invitation.participants.length }) }}
              </h2>
              <ul class="mt-2 space-y-1.5 text-sm" data-participants>
                <li
                  v-for="(person, index) in invitation.participants"
                  :key="index"
                  class="flex items-center gap-2"
                  :data-status="person.status"
                >
                  <component
                    :is="statusIcons[person.status]"
                    :size="16"
                    class="shrink-0"
                    :class="statusColors[person.status]"
                    aria-hidden="true"
                  />
                  <span class="min-w-0 flex-1 truncate text-gray-800">
                    <!-- Others by name only: anyone with the link sees this page. -->
                    <span :class="{ 'text-gray-500': !person.name }">{{ person.name || $t('rsvp.guest') }}</span>
                    <span v-if="person.you" class="text-gray-500"> ({{ $t('rsvp.you') }})</span>
                  </span>
                  <span class="shrink-0 text-xs text-gray-500">{{ participantStatusLabel(person.status) }}</span>
                </li>
              </ul>
            </section>
          </div>

          <div v-if="!invitation.cancelled" class="border-t border-line bg-surface-muted/50 p-6 sm:px-8">
            <div class="flex items-baseline gap-2">
              <h2 class="text-sm font-semibold text-gray-700">{{ $t('rsvp.yourAnswer') }}</h2>
              <span v-if="unsaved" class="text-xs text-gray-400" data-unsaved>{{ $t('rsvp.notSaved') }}</span>
            </div>
            <div class="mt-3 grid grid-cols-3 gap-2" role="group" :aria-label="$t('rsvp.yourAnswer')">
              <button
                v-for="option in answers"
                :key="option.value"
                type="button"
                :disabled="busy"
                :aria-pressed="invitation.status === option.value"
                :data-suggested="(invitation.status === 'needs_action' && suggested === option.value) || undefined"
                class="flex items-center justify-center gap-1.5 rounded-lg border-[1.5px] px-2 py-2.5 text-sm font-medium transition duration-200 active:scale-[0.97] disabled:cursor-wait"
                :style="{ '--answer-glow': answerColors[option.value].glow }"
                :class="[
                  { 'answer-glow': invitation.status === option.value && answerCount > 0 },
                  invitation.status === option.value
                    ? answerColors[option.value].chosen
                    : ['bg-surface', answerColors[option.value].open],
                  invitation.status === 'needs_action' && suggested === option.value
                    ? ['ring-4', answerColors[option.value].suggested]
                    : '',
                ]"
                @click="answer(option.value)"
              >
                <component
                  :is="statusIcons[option.value]"
                  :key="invitation.status === option.value ? answerCount : -1"
                  :size="16"
                  :class="{ 'answer-pop': invitation.status === option.value && answerCount > 0 }"
                  aria-hidden="true"
                />
                <!-- Chosen, it says what was answered: "Accepted" rather than "Accept". -->
                {{ invitation.status === option.value ? participantStatusLabel(option.value) : option.label }}
              </button>
            </div>
            <p v-if="error" class="mt-3 text-sm text-red-600">{{ error }}</p>
          </div>

          <div
            class="flex flex-wrap items-center justify-between gap-3 border-t border-line px-6 py-4 text-xs text-gray-500 sm:px-8"
          >
            <span>{{ $t('rsvp.invitedAs', { email: invitation.email }) }}</span>
            <a
              v-if="!invitation.cancelled"
              :href="icsUrl"
              download="invite.ics"
              class="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-surface-muted"
            >
              <CalendarPlus :size="16" aria-hidden="true" />{{ $t('rsvp.addToCalendar') }}
            </a>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* The answer just chosen: its icon springs in, and a soft glow in its colour spreads once around the
   button. Calm, and only once per click. */
@media (prefers-reduced-motion: no-preference) {
  .answer-pop {
    animation: answer-pop 550ms cubic-bezier(0.34, 1.56, 0.64, 1);
  }

  .answer-glow {
    animation: answer-glow 700ms ease-out;
  }
}

@keyframes answer-pop {
  0% {
    transform: scale(0) rotate(-45deg);
  }
  60% {
    transform: scale(1.35) rotate(0);
  }
  100% {
    transform: none;
  }
}

@keyframes answer-glow {
  from {
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--answer-glow) 55%, transparent);
  }
  to {
    box-shadow: 0 0 0 10px color-mix(in srgb, var(--answer-glow) 0%, transparent);
  }
}
</style>
