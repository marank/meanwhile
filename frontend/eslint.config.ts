import { globalIgnores } from 'eslint/config'
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript'
import pluginVue from 'eslint-plugin-vue'
import skipFormatting from '@vue/eslint-config-prettier/skip-formatting'

// Import boundaries: components call the API through src/api/<area>.ts, shared code never
// reaches into a page, and src/utils stays pure.
const apiClient = { group: ['@/api/client', '**/api/client'], message: 'Call the area modules in src/api.' }
const pages = { group: ['@/views/*', '**/views/*'], message: 'Shared code must not depend on a page.' }
// utils may still import the generated payload types (@/api/types).
const impure = {
  group: ['@/components/*', '**/components/*', '@/api/*', '!@/api/types'],
  message: 'utils stay pure: no components, no API calls.',
}

export default defineConfigWithVueTs(
  {
    name: 'app/files-to-lint',
    files: ['**/*.{ts,mts,vue}'],
  },

  globalIgnores(['**/dist/**', '**/coverage/**']),

  pluginVue.configs['flat/recommended'],
  vueTsConfigs.recommended,
  {
    rules: {
      // Optional props declared through TypeScript are meant to be undefined when not passed.
      'vue/require-default-prop': 'off',
    },
  },
  // Formatting is Prettier's job.
  skipFormatting,

  // Limits on tangle, not on length (no max-lines or max-statements).
  {
    name: 'project/readability',
    files: ['src/**/*.{ts,vue}'],
    rules: {
      complexity: ['error', 15],
      'max-depth': ['error', 4],
      'no-restricted-imports': ['error', { patterns: [apiClient] }],
    },
  },
  // Later blocks replace the rule's options, so each lists every pattern that applies.
  { name: 'project/api', files: ['src/api/**'], rules: { 'no-restricted-imports': 'off' } },
  {
    name: 'project/shared',
    files: ['src/components/**', 'src/composables/**', 'src/services/**', 'src/stores/**'],
    ignores: ['**/__tests__/**'],
    rules: { 'no-restricted-imports': ['error', { patterns: [apiClient, pages] }] },
  },
  {
    name: 'project/utils',
    files: ['src/utils/**'],
    rules: { 'no-restricted-imports': ['error', { patterns: [apiClient, pages, impure] }] },
  },
)
