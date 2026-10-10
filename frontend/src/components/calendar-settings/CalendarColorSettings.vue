<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ColorPaletteSelect from '@/components/ColorPaletteSelect.vue'
import SegmentedControl from '@/components/SegmentedControl.vue'
import {
  calendarColorPalettes,
  colorFields,
  colorRoles,
  matchingPalette,
  paletteColors,
  type CalendarColorFields,
} from '@/services/calendarColors'

withDefaults(defineProps<{ disabled?: boolean }>(), { disabled: false })

// The parent owns this form object; its fields are edited in place.
const colors = defineModel<CalendarColorFields>({ required: true })

const { t } = useI18n()

const selectedPalette = computed(() => matchingPalette(colors.value))
// Calendars with their own colors open in the advanced mode; presets in the simple one.
const advanced = ref(selectedPalette.value === null)

const paletteOptions = computed(() =>
  calendarColorPalettes.map((palette) => ({
    id: palette.id,
    label: t(`palette.${palette.id}`),
    colors: [palette.light.base, palette.light.today, palette.light.event],
  })),
)

function applyPalette(id: string | null) {
  const palette = calendarColorPalettes.find((item) => item.id === id)
  if (palette) Object.assign(colors.value, paletteColors(palette))
}
</script>

<template>
  <div class="space-y-3">
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div class="w-full sm:w-1/2 sm:pr-1.5">
        <ColorPaletteSelect
          :model-value="selectedPalette?.id ?? null"
          :options="paletteOptions"
          :label="$t('app.colorPresets')"
          :placeholder="$t('app.colorPresetCustom')"
          :disabled="disabled"
          @update:model-value="applyPalette"
        />
      </div>
      <SegmentedControl
        v-model="advanced"
        :label="$t('app.colorMode')"
        :options="[
          { value: false, label: $t('app.colorModePreset') },
          { value: true, label: $t('app.colorModeAdvanced') },
        ]"
      />
    </div>

    <template v-if="advanced">
      <div class="overflow-hidden rounded-lg border border-line">
        <table class="w-full text-sm">
          <thead class="bg-surface-muted text-left text-xs uppercase text-gray-500">
            <tr>
              <th class="px-4 py-2">{{ $t('app.usage') }}</th>
              <th class="px-4 py-2">{{ $t('app.themeLight') }}</th>
              <th class="px-4 py-2">{{ $t('app.themeDark') }}</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-line">
            <tr v-for="role in colorRoles" :key="role">
              <td class="px-4 py-2 font-medium text-gray-800">{{ $t(`colorRole.${role}`) }}</td>
              <td v-for="theme in ['light', 'dark'] as const" :key="theme" class="px-4 py-2">
                <input
                  v-model="colors[colorFields[role][theme]]"
                  type="color"
                  :disabled="disabled"
                  :aria-label="`${$t(`colorRole.${role}`)} (${$t(theme === 'light' ? 'app.themeLight' : 'app.themeDark')})`"
                  class="h-8 w-14 rounded border border-line"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="text-xs text-gray-500">{{ $t('app.colorAdvancedHelp') }}</p>
    </template>
  </div>
</template>
