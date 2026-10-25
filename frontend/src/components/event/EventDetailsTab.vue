<script setup lang="ts">
import { useId } from 'vue'
import type * as api from '@/api'
import AppSwitch from '@/components/AppSwitch.vue'
import SearchableSelect from '@/components/SearchableSelect.vue'
import type { useEventForm } from '@/composables/useEventForm'

/** The event's title, place, description, time, category and resource. */
defineProps<{
  calendarId: string
  /** The calendar takes all-day events only. */
  forceAllDay: boolean
  endBeforeStart: boolean
  locationRequiresApproval: boolean
  resourceRequiresApproval: boolean
}>()

const emit = defineEmits<{
  selectLocation: [value: string | null, option: api.SearchResult | null]
  selectResource: [value: string | null, option: api.SearchResult | null]
}>()

// The parent owns the form; its fields are changed in place.
const form = defineModel<ReturnType<typeof useEventForm>['form']>('form', { required: true })

const fieldId = useId()
</script>

<template>
  <div class="space-y-4 sm:space-y-6">
    <section class="space-y-3">
      <label class="block">
        <span class="block text-sm font-medium text-gray-700">{{ $t('event.title') }}</span>
        <input v-model="form.title" class="mt-1 w-full rounded-lg border px-3 py-2" />
      </label>

      <div>
        <div class="flex items-baseline justify-between gap-2">
          <label :for="`${fieldId}-location`" class="block text-sm font-medium text-gray-700">{{
            $t('event.location')
          }}</label>
          <span v-if="locationRequiresApproval" class="text-xs text-amber-600 dark:text-amber-400">{{
            $t('event.approvalRequired')
          }}</span>
        </div>
        <SearchableSelect
          :model-value="form.location || null"
          :input-id="`${fieldId}-location`"
          entity="locations"
          :calendar-id="calendarId"
          allow-free-text
          live-free-text
          open-on-focus
          clearable
          class="mt-1"
          :placeholder="$t('event.locationPlaceholder')"
          @select="(value, option) => emit('selectLocation', value, option)"
        />
      </div>

      <label class="block">
        <span class="block text-sm font-medium text-gray-700">{{ $t('event.description') }}</span>
        <textarea v-model="form.description" class="mt-1 w-full rounded-lg border px-3 py-2" rows="3"></textarea>
      </label>
    </section>

    <section class="space-y-3 border-t border-line pt-4 sm:pt-5">
      <AppSwitch v-model="form.allDay" :label="$t('event.allDay')" :disabled="forceAllDay" />
      <p v-if="forceAllDay" class="text-xs text-gray-500">{{ $t('event.allDayRequired') }}</p>

      <div class="grid items-end gap-3 sm:grid-cols-[1fr_auto_1fr]">
        <div>
          <label :for="`${fieldId}-start`" class="block text-sm font-medium text-gray-700">{{
            $t('event.start')
          }}</label>
          <div class="mt-1 flex gap-2">
            <input
              :id="`${fieldId}-start`"
              v-model="form.startDate"
              type="date"
              class="min-w-0 flex-1 rounded-lg border px-2 py-1.5"
            />
            <input
              v-if="!form.allDay"
              v-model="form.startTime"
              type="time"
              :aria-label="`${$t('event.start')} (${$t('event.time')})`"
              class="w-28 rounded-lg border px-2 py-1.5"
            />
          </div>
        </div>
        <span class="hidden pb-2 text-gray-400 sm:block" aria-hidden="true">–</span>
        <div>
          <label :for="`${fieldId}-end`" class="block text-sm font-medium text-gray-700">{{ $t('event.end') }}</label>
          <div class="mt-1 flex gap-2">
            <input
              :id="`${fieldId}-end`"
              v-model="form.endDate"
              type="date"
              :aria-invalid="endBeforeStart"
              class="min-w-0 flex-1 rounded-lg border px-2 py-1.5"
            />
            <input
              v-if="!form.allDay"
              v-model="form.endTime"
              type="time"
              :aria-label="`${$t('event.end')} (${$t('event.time')})`"
              :aria-invalid="endBeforeStart"
              class="w-28 rounded-lg border px-2 py-1.5"
            />
          </div>
        </div>
      </div>
      <p v-if="endBeforeStart" class="text-xs text-red-600" role="alert">{{ $t('event.endBeforeStart') }}</p>
    </section>

    <section class="space-y-3 border-t border-line pt-4 sm:pt-5">
      <div class="grid gap-3 sm:grid-cols-2">
        <div>
          <label :for="`${fieldId}-category`" class="block text-sm font-medium text-gray-700">{{
            $t('event.category')
          }}</label>
          <SearchableSelect
            v-model="form.categoryId"
            :input-id="`${fieldId}-category`"
            entity="categories"
            :calendar-id="calendarId"
            open-on-focus
            clearable
            class="mt-1"
            :placeholder="$t('event.noCategory')"
          />
        </div>

        <div>
          <div class="flex items-baseline justify-between gap-2">
            <label :for="`${fieldId}-resource`" class="block text-sm font-medium text-gray-700">{{
              $t('event.resource')
            }}</label>
            <span v-if="resourceRequiresApproval" class="text-xs text-amber-600 dark:text-amber-400">{{
              $t('event.approvalRequired')
            }}</span>
          </div>
          <SearchableSelect
            v-model="form.resourceId"
            :input-id="`${fieldId}-resource`"
            entity="resources"
            :calendar-id="calendarId"
            open-on-focus
            clearable
            class="mt-1"
            :placeholder="$t('event.noResource')"
            @select="(value, option) => emit('selectResource', value, option)"
          />
        </div>
      </div>
    </section>
  </div>
</template>
