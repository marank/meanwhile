<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import * as api from '@/api'
import { useAction } from '@/composables/useAction'
import { useLoader } from '@/composables/useLoader'
import { formatDateTime } from '@/services/datetime'
import { nonEmpty } from '@/services/text'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{
  eventId: string
  /** May write comments. */
  canComment: boolean
  /** May delete comments of others. */
  canModerate: boolean
}>()

interface TimelineItem {
  key: string
  at: string
  text: string | null
  comment: api.EventComment | null
}

const auth = useAuthStore()
const { t } = useI18n()
const { busy, run } = useAction()
const comments = ref<api.EventComment[]>([])
const activity = ref<api.EventActivity[]>([])
const newComment = ref('')

const timeline = computed<TimelineItem[]>(() =>
  [
    ...activity.value.map((entry) => ({
      key: `a-${entry.id}`,
      at: entry.created_at,
      text: activityText(entry),
      comment: null,
    })),
    ...comments.value.map((comment) => ({ key: `c-${comment.id}`, at: comment.created_at, text: null, comment })),
  ].sort((a, b) => a.at.localeCompare(b.at)),
)

const { loading } = useLoader(async () => {
  ;[comments.value, activity.value] = await Promise.all([
    api.listComments(props.eventId),
    api.listActivity(props.eventId),
  ])
})

function occurrenceDate(entry: api.EventActivity): string {
  const occurrence = entry.details?.occurrence
  return occurrence ? formatDateTime(occurrence) : ''
}

function changedFields(entry: api.EventActivity): string {
  return (entry.details?.fields ?? []).map((field) => t(`activity.field.${field}`)).join(', ')
}

// The text for each kind of entry; kinds the app doesn't know yet show their name.
const activityTexts: Record<string, (entry: api.EventActivity, name: string) => string> = {
  created: (_, name) => t('activity.created', { name }),
  updated: (entry, name) =>
    t(entry.details?.status === 'pending' ? 'activity.updatedPending' : 'activity.updated', {
      name,
      fields: changedFields(entry),
    }),
  approved: (entry, name) => {
    const note = entry.details?.note
    return note ? t('activity.approvedWithNote', { name, note }) : t('activity.approved', { name })
  },
  rejected: (entry, name) => {
    const note = entry.details?.note
    return note ? t('activity.rejectedWithNote', { name, note }) : t('activity.rejected', { name })
  },
  cancelled: (_, name) => t('activity.cancelled', { name }),
  occurrence_changed: (entry, name) => t('activity.occurrenceChanged', { name, date: occurrenceDate(entry) }),
  occurrence_deleted: (entry, name) => t('activity.occurrenceDeleted', { name, date: occurrenceDate(entry) }),
  series_ended: (entry, name) => t('activity.seriesEnded', { name, date: occurrenceDate(entry) }),
}

function activityText(entry: api.EventActivity): string {
  const text = activityTexts[entry.action]
  return text ? text(entry, nonEmpty(entry.actor_name) ?? t('app.someone')) : entry.action
}

function canDelete(comment: api.EventComment): boolean {
  return props.canModerate || comment.author_id === auth.user?.id
}

async function postComment() {
  const body = newComment.value.trim()
  if (!body) return
  await run(async () => {
    await api.addComment(props.eventId, body)
    newComment.value = ''
    comments.value = await api.listComments(props.eventId)
  })
}

async function removeComment(comment: api.EventComment) {
  await run(async () => {
    await api.deleteComment(props.eventId, comment.id)
    comments.value = comments.value.filter((c) => c.id !== comment.id)
  })
}
</script>

<template>
  <div class="space-y-4">
    <p v-if="loading" class="text-sm text-gray-500">{{ $t('app.loading') }}</p>
    <p v-else-if="!timeline.length" class="text-sm text-gray-500">{{ $t('activity.empty') }}</p>
    <ul class="space-y-3">
      <li v-for="item in timeline" :key="item.key">
        <div v-if="item.comment === null" class="text-sm text-gray-600">
          <span>{{ item.text }}</span>
          <span class="ml-2 text-xs text-gray-400">{{ formatDateTime(item.at) }}</span>
        </div>
        <div v-else class="rounded-lg border border-line p-3">
          <div class="flex items-center justify-between">
            <span class="text-sm font-medium text-gray-800">{{ item.comment.author_name }}</span>
            <span class="flex items-center gap-2">
              <span class="text-xs text-gray-400">{{ formatDateTime(item.comment.created_at) }}</span>
              <button
                v-if="canDelete(item.comment)"
                type="button"
                :disabled="busy"
                class="text-xs text-red-600 hover:underline disabled:opacity-50"
                @click="removeComment(item.comment)"
              >
                {{ $t('app.delete') }}
              </button>
            </span>
          </div>
          <p class="mt-1 whitespace-pre-wrap text-sm text-gray-700">{{ item.comment.body }}</p>
        </div>
      </li>
    </ul>
    <div v-if="canComment" class="flex items-end gap-2">
      <textarea
        v-model="newComment"
        rows="2"
        :placeholder="$t('activity.commentPlaceholder')"
        :aria-label="$t('activity.commentPlaceholder')"
        class="flex-1 rounded-lg border px-3 py-2 text-sm"
      ></textarea>
      <button
        type="button"
        :disabled="busy || !newComment.trim()"
        class="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
        @click="postComment"
      >
        {{ $t('activity.comment') }}
      </button>
    </div>
  </div>
</template>
