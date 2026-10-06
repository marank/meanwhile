<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import * as api from '@/api'
import { useAuthStore } from '@/stores/auth'
import { confirm } from '@/services/dialog'
import { formatDateTime } from '@/services/datetime'
import { buildRrule as serializeRrule, parseRrule as parseRruleValue, type RecurrenceEnd, type RecurrenceFrequency, type RecurrenceMonthMode } from '@/services/rrule'
import { useI18n } from 'vue-i18n'
import { Plus } from 'lucide-vue-next'
import SearchableSelect from '@/components/SearchableSelect.vue'

interface PendingParticipant {
  tempId: string
  user_id?: string
  email: string
  display_name: string
  status: api.EventParticipant['status']
}

const props = defineProps<{
  calendarId: string
  eventId?: string | null
  defaultStart?: Date
  defaultEnd?: Date
  defaultAllDay?: boolean
}>()

const emit = defineEmits<{
  (e: 'saved'): void
  (e: 'cancel'): void
  (e: 'deleted'): void
}>()

const auth = useAuthStore()
const { t } = useI18n()
const busy = ref(false)
const error = ref('')
const selectedResourceOption = ref<api.SearchResult | null>(null)
const forceAllDay = ref(false)
const calendar = ref<api.Calendar | null>(null)

const title = ref('')
const description = ref('')
const allDay = ref(false)
const startDate = ref('')
const startTime = ref('09:00')
const endDate = ref('')
const endTime = ref('10:00')
const resourceId = ref<string | null>(null)
const categoryId = ref<string | null>(null)
const activeTab = ref<'details' | 'recurrence' | 'participants' | 'activity'>('details')
const recurrenceEnabled = ref(false)
const showRecurrenceCount = ref(false)
const recurrenceFrequency = ref<RecurrenceFrequency>('WEEKLY')
const recurrenceInterval = ref(1)
const recurrenceWeekdays = ref<string[]>([])
const recurrenceMonthMode = ref<RecurrenceMonthMode>('date')
const recurrenceMonthDay = ref(1)
const recurrenceMonthOrdinal = ref('1')
const recurrenceMonthWeekday = ref('MO')
const preserveAdvancedMonthlyRule = ref(false)
const recurrenceEnd = ref<RecurrenceEnd>('never')
const recurrenceUntil = ref('')
const recurrenceCount = ref(10)
const extraRuleParts = ref<string[]>([])

const tabs = computed(() =>
  props.eventId
    ? (['details', 'recurrence', 'participants', 'activity'] as const)
    : (['details', 'recurrence', 'participants'] as const),
)

const comments = ref<api.EventComment[]>([])
const activityEntries = ref<api.EventActivity[]>([])
const activityLoaded = ref(false)
const activityBusy = ref(false)
const newComment = ref('')
const participants = ref<api.EventParticipant[]>([])
const pendingParticipants = ref<PendingParticipant[]>([])
const participantValue = ref<string | null>(null)
const participantIsUser = ref(false)
const selectedParticipantOption = ref<api.SearchResult | null>(null)
const participantsBusy = ref(false)
const eventCreatorId = ref('')
const eventCreatorName = ref('')
const eventCreatedAt = ref('')
const eventUpdatedAt = ref('')

const myRole = computed(() => calendar.value?.my_membership?.role || '')
const canModifyEvent = computed(() =>
  ['owner', 'editor'].includes(myRole.value) || eventCreatorId.value === auth.user?.id,
)
const isReadonly = computed(() => props.eventId ? !canModifyEvent.value : false)
const canManageParticipants = computed(() => !props.eventId || canModifyEvent.value)
const participantStatuses: api.EventParticipant['status'][] = [
  'needs_action',
  'accepted',
  'declined',
  'tentative',
]
const resourceRequiresApproval = computed(
  () => selectedResourceOption.value?.meta?.requires_approval === true,
)

interface ParticipantListItem {
  key: string
  id?: string
  tempId?: string
  user_id?: string | null
  email: string
  display_name: string | null
  status: api.EventParticipant['status']
}

const participantItems = computed<ParticipantListItem[]>(() => [
  ...participants.value.map((p) => ({
    key: p.id,
    id: p.id,
    user_id: p.user_id,
    email: p.email,
    display_name: p.display_name,
    status: p.status,
  })),
  ...pendingParticipants.value.map((p) => ({
    key: p.tempId,
    tempId: p.tempId,
    user_id: p.user_id || null,
    email: p.email,
    display_name: p.display_name,
    status: p.status,
  })),
])

const groupedParticipants = computed(() => {
  const groups: Record<api.EventParticipant['status'], ParticipantListItem[]> = {
    needs_action: [],
    accepted: [],
    declined: [],
    tentative: [],
  }
  for (const item of participantItems.value) {
    groups[item.status].push(item)
  }
  return participantStatuses
    .map((status) => ({ status, items: groups[status] }))
    .filter((g) => g.items.length)
})

function onResourceSelect(_value: string | null, option: api.SearchResult | null) {
  selectedResourceOption.value = option
}

interface TimelineItem {
  key: string
  at: string
  text: string | null
  comment: api.EventComment | null
  canDelete: boolean
}

const timeline = computed<TimelineItem[]>(() => [
  ...activityEntries.value.map((entry) => ({
    key: `a-${entry.id}`,
    at: entry.created_at,
    text: activityText(entry),
    comment: null,
    canDelete: false,
  })),
  ...comments.value.map((comment) => ({
    key: `c-${comment.id}`,
    at: comment.created_at,
    text: null,
    comment,
    canDelete: canDeleteComment(comment),
  })),
].sort((a, b) => a.at.localeCompare(b.at)))

function activityText(entry: api.EventActivity): string {
  const name = entry.actor_name || t('app.someone')
  const fields = (entry.details?.fields || []).map((f) => t(`activity.field.${f}`)).join(', ')
  const note = entry.details?.note
  switch (entry.action) {
    case 'created':
      return t('activity.created', { name })
    case 'updated':
      return entry.details?.status === 'pending'
        ? t('activity.updatedPending', { name, fields })
        : t('activity.updated', { name, fields })
    case 'approved':
      return note ? t('activity.approvedWithNote', { name, note }) : t('activity.approved', { name })
    case 'rejected':
      return note ? t('activity.rejectedWithNote', { name, note }) : t('activity.rejected', { name })
    case 'cancelled':
      return t('activity.cancelled', { name })
    default:
      return entry.action
  }
}

function canDeleteComment(comment: api.EventComment): boolean {
  return comment.author_id === auth.user?.id || ['owner', 'editor'].includes(myRole.value)
}

async function loadActivity() {
  if (!auth.token || !props.eventId || activityLoaded.value) return
  activityBusy.value = true
  try {
    const [c, a] = await Promise.all([
      api.listComments(auth.token, props.eventId),
      api.listActivity(auth.token, props.eventId),
    ])
    comments.value = c
    activityEntries.value = a
    activityLoaded.value = true
  } finally {
    activityBusy.value = false
  }
}

async function postComment() {
  if (!auth.token || !props.eventId || !newComment.value.trim()) return
  activityBusy.value = true
  try {
    await api.addComment(auth.token, props.eventId, newComment.value)
    newComment.value = ''
    comments.value = await api.listComments(auth.token, props.eventId)
  } finally {
    activityBusy.value = false
  }
}

async function removeComment(comment: api.EventComment) {
  if (!auth.token) return
  await api.deleteComment(auth.token, comment.id)
  comments.value = comments.value.filter((c) => c.id !== comment.id)
}

function participantStatusLabel(status: api.EventParticipant['status']) {
  const keys: Record<api.EventParticipant['status'], string> = {
    needs_action: 'statusNeedsAction',
    accepted: 'statusAccepted',
    declined: 'statusDeclined',
    tentative: 'statusTentative',
  }
  return t(`event.${keys[status]}`)
}

function participantStatusClass(status: api.EventParticipant['status']) {
  return {
    needs_action: 'bg-gray-100 text-gray-700',
    accepted: 'bg-green-100 text-green-700',
    declined: 'bg-red-100 text-red-700',
    tentative: 'bg-amber-100 text-amber-700',
  }[status]
}

function participantError(e: unknown) {
  const apiError = e as { detail?: { detail?: string }; message?: string }
  error.value = apiError.detail?.detail || apiError.message || 'Participant update failed'
}

async function loadParticipants() {
  if (!auth.token || !props.eventId) return
  participantsBusy.value = true
  error.value = ''
  try {
    participants.value = await api.listEventParticipants(auth.token, props.eventId)
  } catch (e: unknown) {
    participantError(e)
  } finally {
    participantsBusy.value = false
  }
}

const isEmail = (value: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)

function onParticipantSelect(_value: string | null, option: api.SearchResult | null) {
  participantIsUser.value = !!option
  selectedParticipantOption.value = option
}

async function addParticipant() {
  const value = participantValue.value?.trim()
  if (!auth.token || !value) return
  const email = participantIsUser.value
    ? (selectedParticipantOption.value?.subtitle || value)
    : value
  const displayName = participantIsUser.value
    ? selectedParticipantOption.value?.label || email
    : email
  if (pendingParticipants.value.some((p) => p.email.toLowerCase() === email.toLowerCase())) return
  if (participants.value.some((p) => p.email.toLowerCase() === email.toLowerCase())) return

  if (!props.eventId) {
    pendingParticipants.value.push({
      tempId: crypto.randomUUID(),
      user_id: participantIsUser.value ? value : undefined,
      email,
      display_name: displayName,
      status: 'needs_action',
    })
    participantValue.value = null
    participantIsUser.value = false
    selectedParticipantOption.value = null
    return
  }

  participantsBusy.value = true
  error.value = ''
  try {
    const data: api.EventParticipantCreate = { status: 'needs_action' }
    if (participantIsUser.value) {
      data.user_id = value
    } else {
      data.email = value
    }
    await api.addEventParticipant(auth.token, props.eventId, data)
    participantValue.value = null
    participantIsUser.value = false
    selectedParticipantOption.value = null
    await loadParticipants()
  } catch (e: unknown) {
    participantError(e)
  } finally {
    participantsBusy.value = false
  }
}

async function removeParticipant(participant: api.EventParticipant) {
  if (!auth.token || !props.eventId) return
  participantsBusy.value = true
  error.value = ''
  try {
    await api.removeEventParticipant(auth.token, props.eventId, participant.id)
    await loadParticipants()
  } catch (e: unknown) {
    participantError(e)
  } finally {
    participantsBusy.value = false
  }
}

function removePendingParticipant(tempId: string) {
  pendingParticipants.value = pendingParticipants.value.filter((p) => p.tempId !== tempId)
}

function removeParticipantItem(item: ParticipantListItem) {
  if (item.tempId) removePendingParticipant(item.tempId)
  else if (item.id) removeParticipant(item as unknown as api.EventParticipant)
}

watch(activeTab, (tab) => {
  if (tab === 'activity') loadActivity()
  if (tab === 'participants') loadParticipants()
})
const weekdays = [
  { value: 'MO', key: 'monday' },
  { value: 'TU', key: 'tuesday' },
  { value: 'WE', key: 'wednesday' },
  { value: 'TH', key: 'thursday' },
  { value: 'FR', key: 'friday' },
  { value: 'SA', key: 'saturday' },
  { value: 'SU', key: 'sunday' },
]

function applyRrule(value: string) {
  const rule = parseRruleValue(value, recurrenceMonthDay.value)
  if (!rule) return
  recurrenceEnabled.value = true
  recurrenceFrequency.value = rule.frequency
  recurrenceInterval.value = rule.interval
  recurrenceWeekdays.value = rule.weekdays
  recurrenceMonthMode.value = rule.monthMode
  recurrenceMonthDay.value = rule.monthDay
  recurrenceMonthOrdinal.value = rule.monthOrdinal
  recurrenceMonthWeekday.value = rule.monthWeekday
  recurrenceEnd.value = rule.end
  recurrenceUntil.value = rule.until
  recurrenceCount.value = rule.count
  preserveAdvancedMonthlyRule.value = rule.preserveAdvancedMonthlyRule
  extraRuleParts.value = rule.extraParts
}

function currentRrule() {
  return serializeRrule(recurrenceEnabled.value ? {
    frequency: recurrenceFrequency.value,
    interval: recurrenceInterval.value,
    weekdays: recurrenceWeekdays.value,
    monthMode: recurrenceMonthMode.value,
    monthDay: recurrenceMonthDay.value,
    monthOrdinal: recurrenceMonthOrdinal.value,
    monthWeekday: recurrenceMonthWeekday.value,
    end: recurrenceEnd.value,
    until: recurrenceUntil.value,
    count: recurrenceCount.value,
    preserveAdvancedMonthlyRule: preserveAdvancedMonthlyRule.value,
    extraParts: extraRuleParts.value,
  } : null)
}

function toggleWeekday(day: string) {
  recurrenceWeekdays.value = recurrenceWeekdays.value.includes(day)
    ? recurrenceWeekdays.value.filter((value) => value !== day)
    : [...recurrenceWeekdays.value, day]
}

function selectStartWeekday() {
  if (!recurrenceWeekdays.value.length && startDate.value) {
    const day = new Date(`${startDate.value}T00:00:00`).getDay()
    recurrenceWeekdays.value = [['SU', 'MO', 'TU', 'WE', 'TH', 'FR', 'SA'][day]!]
  }
}

onMounted(async () => {
  if (!auth.token) return
  const cal = await api.getCalendar(auth.token, props.calendarId)
  calendar.value = cal
  forceAllDay.value = cal.force_all_day
  if (forceAllDay.value) allDay.value = true
  if (props.eventId) {
    const event = await api.getEvent(auth.token, props.eventId)
    eventCreatorId.value = event.creator_id
    eventCreatorName.value = event.creator_name || event.creator_email || ''
    eventCreatedAt.value = event.created_at
    eventUpdatedAt.value = event.updated_at
    title.value = event.title
    description.value = event.description || ''
    allDay.value = forceAllDay.value || event.all_day
    const s = new Date(event.start)
    const e = new Date(event.end)
    startDate.value = allDay.value ? toAllDayDateInput(event.start) : toDateInput(s)
    endDate.value = allDay.value ? toAllDayDateInput(event.end) : toDateInput(e)
    startTime.value = allDay.value ? '00:00' : toTimeInput(s)
    endTime.value = allDay.value ? '00:00' : toTimeInput(e)
    resourceId.value = event.resource_id || null
    categoryId.value = event.category_id || null
    showRecurrenceCount.value = event.show_recurrence_count
    recurrenceMonthDay.value = Number(startDate.value.slice(8, 10))
    applyRrule(event.rrule || '')
  } else if (props.defaultStart) {
    const s = props.defaultStart
    const isAllDay = props.defaultAllDay !== undefined ? props.defaultAllDay : false
    allDay.value = forceAllDay.value || isAllDay
    if (props.defaultEnd) {
      const e = props.defaultEnd
      startDate.value = allDay.value ? toAllDayDateInput(s.toISOString()) : toDateInput(s)
      endDate.value = allDay.value ? toAllDayDateInput(e.toISOString()) : toDateInput(e)
      startTime.value = allDay.value ? '00:00' : toTimeInput(s)
      endTime.value = allDay.value ? '00:00' : toTimeInput(e)
    } else {
      const e = new Date(s.getTime() + 60 * 60 * 1000)
      startDate.value = toDateInput(s)
      endDate.value = toDateInput(e)
      startTime.value = toTimeInput(s)
      endTime.value = toTimeInput(e)
    }
    recurrenceMonthDay.value = Number(startDate.value.slice(8, 10))
  }
  selectStartWeekday()
})

function toDateInput(d: Date) {
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().split('T')[0]!
}
function toAllDayDateInput(value: string) {
  return value.slice(0, 10)
}
function toTimeInput(d: Date) {
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(11, 16)
}
function buildDate(dateStr: string, timeStr: string) {
  return new Date(`${dateStr}T${timeStr}`)
}
function buildAllDayDate(dateStr: string) {
  return new Date(`${dateStr}T00:00:00.000Z`)
}

async function save() {
  if (!auth.token) return
  busy.value = true
  error.value = ''
  try {
    const start = allDay.value
      ? buildAllDayDate(startDate.value)
      : buildDate(startDate.value, startTime.value)
    const end = allDay.value
      ? buildAllDayDate(endDate.value)
      : buildDate(endDate.value, endTime.value)
    const body: any = {
      title: title.value,
      description: description.value || undefined,
      start: start.toISOString(),
      end: end.toISOString(),
      all_day: allDay.value,
      show_recurrence_count: recurrenceEnabled.value && showRecurrenceCount.value,
      rrule: currentRrule(),
      category_id: categoryId.value || null,
      resource_id: resourceId.value || undefined,
    }
    if (props.eventId) {
      await api.updateEvent(auth.token, props.eventId, body)
    } else {
      if (pendingParticipants.value.length) {
        body.participants = pendingParticipants.value.map((p) => ({
          user_id: p.user_id,
          email: p.email,
          status: p.status,
        }))
      }
      await api.createEvent(auth.token, props.calendarId, body)
    }
    emit('saved')
  } catch (e: any) {
    error.value = e.detail?.detail || e.message || 'Failed to save event'
  } finally {
    busy.value = false
  }
}

async function remove() {
  if (!props.eventId || !auth.token) return
  const ok = await confirm(t('app.deleteEventText'), t('app.deleteEventTitle'))
  if (!ok) return
  await api.deleteEvent(auth.token, props.eventId)
  emit('deleted')
}

function cancel() {
  emit('cancel')
}
</script>

<template>
  <div class="modal-backdrop fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
    <div class="modal-panel bg-white border border-transparent rounded-xl shadow-xl w-full max-w-xl p-6 max-h-[90vh] flex flex-col">
      <h3 class="text-lg font-semibold text-gray-800">
        {{ eventId ? $t('app.edit') : $t('app.add') }}
      </h3>

      <div class="flex gap-1 border-b border-gray-200 mt-4 mb-5">
        <button
          v-for="tab in tabs"
          :key="tab"
          type="button"
          @click="activeTab = tab"
          class="px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors"
          :class="activeTab === tab ? 'border-blue-600 text-blue-700' : 'border-transparent text-gray-500 hover:text-gray-700'"
        >
          {{ $t(`event.${tab}`) }}
        </button>
      </div>

      <div class="overflow-y-auto px-1">
        <fieldset class="contents" :disabled="isReadonly">
          <div v-if="activeTab === 'details'" class="space-y-3">
          <div>
            <label class="block text-sm font-medium text-gray-700">{{ $t('event.title') }}</label>
            <input v-model="title" class="w-full border rounded-lg px-3 py-2 mt-1" />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700">{{ $t('event.description') }}</label>
            <textarea v-model="description" class="w-full border rounded-lg px-3 py-2 mt-1" rows="2"></textarea>
          </div>

          <div>
            <label class="flex items-center gap-2 text-sm">
              <input type="checkbox" v-model="allDay" :disabled="forceAllDay" />
              {{ $t('event.allDay') }}
            </label>
            <p v-if="forceAllDay" class="text-xs text-gray-500 mt-1">{{ $t('event.allDayRequired') }}</p>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-medium text-gray-700">{{ $t('event.start') }}</label>
              <input type="date" v-model="startDate" class="w-full border rounded-lg px-2 py-1 mt-1" />
              <input v-if="!allDay" type="time" v-model="startTime" class="w-full border rounded-lg px-2 py-1 mt-1" />
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-700">{{ $t('event.end') }}</label>
              <input type="date" v-model="endDate" class="w-full border rounded-lg px-2 py-1 mt-1" />
              <input v-if="!allDay" type="time" v-model="endTime" class="w-full border rounded-lg px-2 py-1 mt-1" />
            </div>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700">{{ $t('event.category') }}</label>
            <SearchableSelect
              v-model="categoryId"
              entity="categories"
              :calendar-id="calendarId"
              :default-limit="20"
              open-on-focus
              clearable
              class="mt-1"
              :placeholder="$t('event.noCategory')"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700">{{ $t('event.bookResource') }}</label>
            <SearchableSelect
              v-model="resourceId"
              entity="resources"
              :calendar-id="calendarId"
              :default-limit="20"
              open-on-focus
              clearable
              class="mt-1"
              :placeholder="$t('event.noResource')"
              @select="onResourceSelect"
            />
            <p v-if="resourceRequiresApproval" class="text-xs text-amber-600 mt-1">
              {{ $t('event.resourceRequiresApproval') }}
            </p>
          </div>
        </div>

        <div v-else-if="activeTab === 'recurrence'" class="space-y-5">
          <label class="flex items-start gap-3 rounded-lg border border-gray-200 p-4 cursor-pointer">
            <input type="checkbox" v-model="recurrenceEnabled" class="mt-0.5" />
            <span>
              <span class="block text-sm font-medium text-gray-800">{{ $t('event.repeatEvent') }}</span>
              <span class="block text-xs text-gray-500 mt-0.5">{{ $t('event.repeatHelp') }}</span>
            </span>
          </label>

          <div v-if="recurrenceEnabled" class="space-y-5">
            <label class="flex items-start gap-3 rounded-lg bg-gray-50 p-3 cursor-pointer">
              <input type="checkbox" v-model="showRecurrenceCount" class="mt-0.5" />
              <span>
                <span class="block text-sm font-medium text-gray-800">{{ $t('event.showRecurrenceCount') }}</span>
                <span class="block text-xs text-gray-500 mt-0.5">{{ $t('event.showRecurrenceCountHelp') }}</span>
              </span>
            </label>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ $t('event.frequency') }}</label>
              <div class="flex items-center gap-3">
                <span class="text-sm text-gray-600">{{ $t('event.every') }}</span>
                <input v-model.number="recurrenceInterval" type="number" min="1" class="w-20 border rounded-lg px-3 py-2" />
                <select v-model="recurrenceFrequency" class="flex-1 border rounded-lg px-3 py-2">
                  <option value="DAILY">{{ $t('event.days') }}</option>
                  <option value="WEEKLY">{{ $t('event.weeks') }}</option>
                  <option value="MONTHLY">{{ $t('event.months') }}</option>
                  <option value="YEARLY">{{ $t('event.years') }}</option>
                </select>
              </div>
            </div>

            <div v-if="recurrenceFrequency === 'WEEKLY'">
              <label class="block text-sm font-medium text-gray-700 mb-2">{{ $t('event.repeatOn') }}</label>
              <div class="flex gap-2">
                <button
                  v-for="day in weekdays"
                  :key="day.value"
                  type="button"
                  @click="toggleWeekday(day.value)"
                  class="h-9 w-9 rounded-full text-xs font-semibold border transition-colors"
                  :class="recurrenceWeekdays.includes(day.value) ? 'bg-blue-600 border-blue-600 text-white' : 'border-gray-300 text-gray-600 hover:bg-gray-50'"
                  :title="$t(`event.${day.key}`)"
                >
                  {{ $t(`event.${day.key}Short`) }}
                </button>
              </div>
            </div>

            <div v-if="recurrenceFrequency === 'MONTHLY'">
              <label class="block text-sm font-medium text-gray-700 mb-2">{{ $t('event.monthlyOn') }}</label>
              <div class="space-y-3">
                <label class="flex items-center gap-3 text-sm">
                  <input v-model="recurrenceMonthMode" @change="preserveAdvancedMonthlyRule = false" type="radio" value="date" />
                  <span>{{ $t('event.dayOfMonth') }}</span>
                  <input v-model.number="recurrenceMonthDay" @input="preserveAdvancedMonthlyRule = false" type="number" min="1" max="31" :disabled="recurrenceMonthMode !== 'date'" class="w-20 border rounded-lg px-3 py-2 disabled:bg-gray-100" />
                </label>
                <label class="flex items-center gap-3 text-sm">
                  <input v-model="recurrenceMonthMode" @change="preserveAdvancedMonthlyRule = false" type="radio" value="weekday" />
                  <select v-model="recurrenceMonthOrdinal" :disabled="recurrenceMonthMode !== 'weekday'" class="border rounded-lg px-3 py-2 disabled:bg-gray-100">
                    <option value="1">{{ $t('event.first') }}</option>
                    <option value="2">{{ $t('event.second') }}</option>
                    <option value="3">{{ $t('event.third') }}</option>
                    <option value="4">{{ $t('event.fourth') }}</option>
                    <option value="-1">{{ $t('event.last') }}</option>
                  </select>
                  <select v-model="recurrenceMonthWeekday" :disabled="recurrenceMonthMode !== 'weekday'" class="flex-1 border rounded-lg px-3 py-2 disabled:bg-gray-100">
                    <option v-for="day in weekdays" :key="day.value" :value="day.value">{{ $t(`event.${day.key}`) }}</option>
                  </select>
                </label>
              </div>
              <p v-if="recurrenceMonthMode === 'date'" class="text-xs text-gray-500 mt-2">{{ $t('event.monthDayHelp') }}</p>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">{{ $t('event.ends') }}</label>
              <div class="space-y-2">
                <label class="flex items-center gap-2 text-sm">
                  <input v-model="recurrenceEnd" type="radio" value="never" />
                  {{ $t('event.never') }}
                </label>
                <label class="flex items-center gap-2 text-sm">
                  <input v-model="recurrenceEnd" type="radio" value="until" />
                  <span class="w-16">{{ $t('event.onDate') }}</span>
                  <input v-model="recurrenceUntil" type="date" :disabled="recurrenceEnd !== 'until'" class="border rounded-lg px-2 py-1 disabled:bg-gray-100" />
                </label>
                <label class="flex items-center gap-2 text-sm">
                  <input v-model="recurrenceEnd" type="radio" value="count" />
                  <span class="w-16">{{ $t('event.after') }}</span>
                  <input v-model.number="recurrenceCount" type="number" min="1" :disabled="recurrenceEnd !== 'count'" class="w-20 border rounded-lg px-2 py-1 disabled:bg-gray-100" />
                  {{ $t('event.occurrences') }}
                </label>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="activeTab === 'participants'" class="space-y-4 pb-4">
          <p v-if="participantsBusy && !participantItems.length" class="text-sm text-gray-500">{{ $t('app.loading') }}</p>
          <p v-else-if="!participantItems.length" class="text-sm text-gray-500">{{ $t('event.noParticipants') }}</p>
          <div v-else class="space-y-3">
            <div v-for="group in groupedParticipants" :key="group.status">
              <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                {{ participantStatusLabel(group.status) }}
              </p>
              <ul class="divide-y divide-gray-200 rounded-lg border border-gray-200">
                <li v-for="participant in group.items" :key="participant.key" class="flex items-center justify-between gap-3 p-3">
                  <div class="min-w-0">
                    <p class="truncate text-sm font-medium text-gray-800">
                      {{ participant.display_name || participant.email }}
                    </p>
                    <p v-if="participant.display_name && participant.display_name !== participant.email" class="truncate text-xs text-gray-500">{{ participant.email }}</p>
                  </div>
                  <button
                    v-if="canManageParticipants"
                    type="button"
                    :disabled="participantsBusy"
                    class="text-xs text-red-600 hover:underline disabled:opacity-50"
                    @click="removeParticipantItem(participant)"
                  >
                    {{ $t('app.delete') }}
                  </button>
                </li>
              </ul>
            </div>
          </div>

          <form v-if="canManageParticipants" class="flex items-end gap-2 border-t border-gray-200 pt-4" @submit.prevent="addParticipant">
            <label class="min-w-0 flex-1 text-xs font-medium text-gray-700">
              {{ $t('event.participantEmail') }}
              <SearchableSelect
                v-model="participantValue"
                entity="users"
                :min-search-length="2"
                allow-free-text
                :free-text-validator="isEmail"
                class="mt-1"
                @select="onParticipantSelect"
              />
            </label>
            <button
              type="submit"
              :disabled="participantsBusy || !participantValue?.trim()"
              :aria-label="$t('event.addParticipant')"
              class="px-3 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
            >
              <Plus :size="18" />
            </button>
          </form>
        </div>

        <div v-else-if="activeTab === 'activity'" class="space-y-4">
          <p v-if="activityBusy && !timeline.length" class="text-sm text-gray-500">{{ $t('app.loading') }}</p>
          <p v-else-if="!timeline.length" class="text-sm text-gray-500">{{ $t('activity.empty') }}</p>
          <ul class="space-y-3">
            <li v-for="item in timeline" :key="item.key">
              <div v-if="item.comment === null" class="text-sm text-gray-600">
                <span>{{ item.text }}</span>
                <span class="text-xs text-gray-400 ml-2">{{ formatDateTime(item.at) }}</span>
              </div>
              <div v-else class="rounded-lg border border-gray-200 p-3">
                <div class="flex items-center justify-between">
                  <span class="text-sm font-medium text-gray-800">{{ item.comment.author_name }}</span>
                  <span class="flex items-center gap-2">
                    <span class="text-xs text-gray-400">{{ formatDateTime(item.comment.created_at) }}</span>
                    <button
                      v-if="item.canDelete"
                      @click="removeComment(item.comment)"
                      class="text-xs text-red-600 hover:underline"
                    >
                      {{ $t('app.delete') }}
                    </button>
                  </span>
                </div>
                <p class="text-sm text-gray-700 mt-1 whitespace-pre-wrap">{{ item.comment.body }}</p>
              </div>
            </li>
          </ul>
          <div v-if="myRole && myRole !== 'viewer'" class="flex gap-2 items-end">
            <textarea
              v-model="newComment"
              rows="2"
              :placeholder="$t('activity.commentPlaceholder')"
              class="flex-1 border rounded-lg px-3 py-2 text-sm"
            ></textarea>
            <button
              @click="postComment"
              :disabled="activityBusy || !newComment.trim()"
              class="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:opacity-50"
            >
              {{ $t('activity.comment') }}
            </button>
          </div>
        </div>

        <p v-if="error" class="text-sm text-red-600 bg-red-50 dark:bg-red-900 dark:text-red-200 p-2 rounded mt-4">{{ error }}</p>
        </fieldset>
      </div>

      <div v-if="eventId && eventCreatedAt" class="mt-4 text-xs text-gray-500">
        {{ t('event.createdBy', { name: eventCreatorName, date: formatDateTime(eventCreatedAt) }) }}
        <span v-if="eventUpdatedAt && eventUpdatedAt !== eventCreatedAt">
          , {{ t('event.editedBy', { date: formatDateTime(eventUpdatedAt) }) }}
        </span>
      </div>

      <div class="flex items-center justify-between mt-6">
        <button v-if="eventId && canModifyEvent" @click="remove" class="text-red-600 hover:underline text-sm">{{ $t('app.delete') }}</button>
        <div v-else></div>
        <div class="flex gap-3">
          <button @click="cancel" class="px-4 py-2 rounded-lg border border-gray-300 hover:bg-gray-50">{{ $t('app.cancel') }}</button>
          <button
            v-if="!eventId || canModifyEvent"
            @click="save"
            :disabled="busy"
            class="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {{ $t('app.save') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
