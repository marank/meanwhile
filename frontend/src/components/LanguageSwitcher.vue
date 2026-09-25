<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { locale } = useI18n()

function setLanguage(lang: string) {
  locale.value = lang
}
</script>

<template>
  <div class="flex items-center gap-2">
    <button
      @click="setLanguage('en')"
      :class="{ 'font-bold underline': locale === 'en' }"
      class="text-sm text-gray-600 hover:text-gray-900"
    >
      EN
    </button>
    <span class="text-gray-300">|</span>
    <button
      @click="setLanguage('de')"
      :class="{ 'font-bold underline': locale === 'de' }"
      class="text-sm text-gray-600 hover:text-gray-900"
    >
      DE
    </button>
  </div>
</template>
