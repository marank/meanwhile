<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { FileText, Link2, Paperclip, X } from '@lucide/vue'
import type * as api from '@/api'
import type { PendingAttachment } from '@/composables/useEventExtras'
import { formatSize, isWebAddress } from '@/services/attachments'

/** The event's files and links; what is added or removed here is sent when the event is saved. */
const props = defineProps<{
  eventId?: string | null
  canManage: boolean
}>()

/** The saved attachments, loaded by the dialog; null while loading. */
const saved = defineModel<api.Attachment[] | null>('saved', { default: null })
const pending = defineModel<PendingAttachment[]>('pending', { required: true })
/** Saved attachments removed in the dialog; removed when the event is saved. */
const removed = defineModel<string[]>('removed', { required: true })

const { locale } = useI18n()

interface Item {
  key: string
  kind: 'file' | 'link'
  name: string
  /** Where it opens; none for what isn't saved yet. */
  url: string | null
  size: number | null
  addedBy: string | null
  pending: boolean
  remove: () => void
}

const items = computed<Item[]>(() => [
  ...(saved.value ?? [])
    .filter((attachment) => !removed.value.includes(attachment.id))
    .map((attachment) => ({
      key: attachment.id,
      kind: attachment.kind,
      name: attachment.name,
      url: attachment.url,
      size: attachment.kind === 'file' ? attachment.size : null,
      addedBy: attachment.added_by_name,
      pending: false,
      remove: () => (removed.value = [...removed.value, attachment.id]),
    })),
  ...pending.value.map((attachment) => ({
    key: attachment.tempId,
    kind: attachment.kind,
    name: attachment.name,
    url: null,
    size: attachment.kind === 'file' ? attachment.file.size : null,
    addedBy: null,
    pending: true,
    remove: () => (pending.value = pending.value.filter((p) => p.tempId !== attachment.tempId)),
  })),
])

// New events have no saved attachments to wait for.
const loading = computed(() => !!props.eventId && saved.value === null)

function addFiles(event: Event) {
  const input = event.target as HTMLInputElement
  const files = [...(input.files ?? [])]
  pending.value = [
    ...pending.value,
    ...files.map((file) => ({ tempId: crypto.randomUUID(), kind: 'file' as const, name: file.name, file })),
  ]
  // The same file can be picked again, e.g. after removing it.
  input.value = ''
}

const linkUrl = ref('')
const linkName = ref('')
const linkInvalid = ref(false)

function addLink() {
  const url = linkUrl.value.trim()
  if (!isWebAddress(url)) {
    linkInvalid.value = true
    return
  }
  pending.value = [
    ...pending.value,
    { tempId: crypto.randomUUID(), kind: 'link', url, name: linkName.value.trim() || url },
  ]
  linkUrl.value = ''
  linkName.value = ''
  linkInvalid.value = false
}
</script>

<template>
  <div class="space-y-4 pb-4">
    <p v-if="loading" class="text-sm text-gray-500">{{ $t('app.loading') }}</p>
    <p v-else-if="!items.length" class="text-sm text-gray-500">{{ $t('attachments.none') }}</p>
    <ul v-else class="divide-y divide-line rounded-lg border border-line">
      <li
        v-for="item in items"
        :key="item.key"
        class="flex items-center gap-3 p-3"
        :data-kind="item.kind"
        :data-pending="item.pending || undefined"
      >
        <component :is="item.kind === 'file' ? FileText : Link2" :size="18" class="shrink-0 text-gray-500" />
        <div class="min-w-0 flex-1">
          <!-- Files download (the server sends them as downloads); links open in a tab of their own. -->
          <a
            v-if="item.url"
            :href="item.url"
            v-bind="item.kind === 'link' ? { target: '_blank', rel: 'noopener noreferrer' } : { download: item.name }"
            class="block truncate text-sm font-medium text-blue-700 hover:underline dark:text-blue-400"
            >{{ item.name }}</a
          >
          <p v-else class="truncate text-sm font-medium text-gray-800">{{ item.name }}</p>
          <p class="truncate text-xs text-gray-500">
            <span v-if="item.size !== null">{{ formatSize(item.size, locale) }}</span>
            <span v-if="item.size !== null && (item.pending || item.addedBy)"> · </span>
            <span v-if="item.pending">{{ $t('attachments.pending') }}</span>
            <span v-else-if="item.addedBy">{{ $t('attachments.addedBy', { name: item.addedBy }) }}</span>
          </p>
        </div>
        <button
          v-if="canManage"
          type="button"
          class="rounded p-1 text-gray-500 hover:bg-hover hover:text-red-600"
          :aria-label="$t('attachments.removeNamed', { name: item.name })"
          :title="$t('attachments.remove')"
          @click="item.remove()"
        >
          <X :size="16" />
        </button>
      </li>
    </ul>

    <template v-if="canManage">
      <div class="space-y-1">
        <label
          class="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-line px-3 py-2 text-sm hover:bg-hover focus-within:ring-2 focus-within:ring-blue-500"
        >
          <Paperclip :size="16" />
          {{ $t('attachments.addFiles') }}
          <input type="file" multiple class="sr-only" @change="addFiles" />
        </label>
        <p class="text-xs text-gray-500">{{ $t('attachments.hint') }}</p>
      </div>

      <form
        class="grid gap-2 border-t border-line pt-4 sm:grid-cols-[2fr_1fr_auto] sm:items-end"
        @submit.prevent="addLink"
      >
        <label class="block text-xs font-medium text-gray-700">
          {{ $t('attachments.linkUrl') }}
          <input
            v-model="linkUrl"
            type="url"
            inputmode="url"
            :placeholder="$t('attachments.linkUrlPlaceholder')"
            :aria-invalid="linkInvalid"
            class="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
            @input="linkInvalid = false"
          />
        </label>
        <label class="block text-xs font-medium text-gray-700">
          {{ $t('attachments.linkName') }}
          <input v-model="linkName" class="mt-1 w-full rounded-lg border px-3 py-2 text-sm" />
        </label>
        <button
          type="submit"
          :disabled="!linkUrl.trim()"
          class="rounded-lg border border-line px-3 py-2 text-sm hover:bg-hover disabled:opacity-50"
        >
          {{ $t('attachments.addLink') }}
        </button>
        <p v-if="linkInvalid" class="text-xs text-red-600 sm:col-span-3" role="alert">
          {{ $t('attachments.invalidUrl') }}
        </p>
      </form>
    </template>
  </div>
</template>
