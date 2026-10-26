<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Pencil, Trash2 } from '@lucide/vue'
import * as api from '@/api'
import IconButton from '@/components/IconButton.vue'
import SettingsPanel from '@/components/SettingsPanel.vue'
import { useAction } from '@/composables/useAction'
import { useLoader } from '@/composables/useLoader'
import { confirm } from '@/services/dialog'

interface CategoryForm {
  id: string | null
  name: string
  description: string
  color: string
}

const props = defineProps<{
  calendarId: string
  canManage: boolean
}>()

const { t } = useI18n()
const { busy, run } = useAction()
const categories = ref<api.Category[]>([])
// null while the list is shown
const form = ref<CategoryForm | null>(null)

const { loading } = useLoader(load)

async function load() {
  categories.value = await api.listCategories(props.calendarId)
}

function startAdd() {
  form.value = { id: null, name: '', description: '', color: '#64748b' }
}

function startEdit(category: api.Category) {
  form.value = { id: category.id, name: category.name, description: category.description, color: category.color }
}

async function save() {
  const value = form.value
  if (!value?.name) return
  const data = { name: value.name, description: value.description, color: value.color }
  const saved = await run(
    async () => {
      if (value.id) await api.updateCategory(props.calendarId, value.id, data)
      else await api.createCategory(props.calendarId, data)
      await load()
    },
    { failure: t('app.saveFailed') },
  )
  if (saved) form.value = null
}

async function remove(id: string) {
  if (!(await confirm(t('app.deleteCategoryText'), t('app.deleteCategoryTitle')))) return
  await run(
    async () => {
      await api.deleteCategory(props.calendarId, id)
      await load()
    },
    { failure: t('app.deleteFailed') },
  )
}
</script>

<template>
  <SettingsPanel :title="$t('app.categories')" :description="$t('app.categoriesDescription')" :loading="loading" flush>
    <template v-if="!form && canManage" #actions>
      <button
        type="button"
        class="rounded-lg bg-blue-600 px-3 py-2 text-sm text-white hover:bg-blue-700"
        @click="startAdd"
      >
        {{ $t('app.add') }}
      </button>
    </template>

    <div v-if="!form" class="overflow-x-auto">
      <table class="stacked-table w-full text-sm">
        <thead class="bg-surface-muted text-left text-xs uppercase text-gray-500">
          <tr>
            <th class="w-16 px-4 py-2">{{ $t('app.color') }}</th>
            <th class="px-4 py-2">{{ $t('app.nameLabel') }}</th>
            <th class="px-4 py-2">{{ $t('event.description') }}</th>
            <th class="px-4 py-2 text-right">{{ $t('app.actions') }}</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-line">
          <tr v-for="category in categories" :key="category.id" class="group hover:bg-hover">
            <td class="px-4 py-2" data-lead>
              <span class="block h-5 w-5 rounded" :style="{ backgroundColor: category.color }"></span>
            </td>
            <td class="px-4 py-2 font-medium text-gray-800">{{ category.name }}</td>
            <td class="px-4 py-2 text-gray-500" :data-empty="!category.description || undefined">
              {{ category.description || '—' }}
            </td>
            <td class="px-4 py-2" data-actions>
              <div v-if="canManage" class="row-actions flex justify-end gap-1">
                <IconButton :label="$t('app.edit')" tone="primary" @click="startEdit(category)">
                  <Pencil :size="18" :stroke-width="2.25" />
                </IconButton>
                <IconButton :label="$t('app.delete')" tone="danger" :disabled="busy" @click="remove(category.id)">
                  <Trash2 :size="18" :stroke-width="2.25" />
                </IconButton>
              </div>
            </td>
          </tr>
          <tr v-if="!categories.length">
            <td colspan="4" class="px-6 py-8 text-center text-gray-500">{{ $t('app.noCategories') }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-else>
      <div class="border-b border-line px-6 py-4">
        <h3 class="font-semibold text-gray-700">{{ form.id ? $t('app.editCategory') : $t('app.addCategory') }}</h3>
      </div>
      <div class="space-y-4 p-6">
        <label class="block">
          <span class="mb-1 block text-sm font-medium text-gray-700">{{ $t('app.nameLabel') }}</span>
          <input v-model="form.name" class="w-full rounded-lg border border-line px-3 py-2" />
        </label>
        <label class="block">
          <span class="mb-1 block text-sm font-medium text-gray-700">{{ $t('event.description') }}</span>
          <textarea
            v-model="form.description"
            rows="3"
            class="w-full rounded-lg border border-line px-3 py-2"
          ></textarea>
        </label>
        <label class="block">
          <span class="mb-1 block text-sm font-medium text-gray-700">{{ $t('app.color') }}</span>
          <input v-model="form.color" type="color" class="h-10 w-16 rounded border border-line" />
        </label>
        <div class="flex justify-end gap-3">
          <button type="button" class="rounded-lg border border-line px-4 py-2 hover:bg-hover" @click="form = null">
            {{ $t('app.cancel') }}
          </button>
          <button
            type="button"
            :disabled="!form.name || busy"
            class="rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
            @click="save"
          >
            {{ $t('app.save') }}
          </button>
        </div>
      </div>
    </div>
  </SettingsPanel>
</template>
