import { globalIgnores } from 'eslint/config'
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript'
import pluginVue from 'eslint-plugin-vue'
import skipFormatting from '@vue/eslint-config-prettier/skip-formatting'
import sonarjs from 'eslint-plugin-sonarjs'

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
  // Type-aware: unawaited promises, conditions the types settle, `??` over `||`,
  // exhaustive switches.
  vueTsConfigs.recommendedTypeChecked,
  {
    rules: {
      // Optional props declared through TypeScript are meant to be undefined when not passed.
      'vue/require-default-prop': 'off',
      '@typescript-eslint/no-unnecessary-condition': 'error',
      '@typescript-eslint/prefer-nullish-coalescing': 'error',
      '@typescript-eslint/switch-exhaustiveness-check': 'error',
    },
  },
  {
    // The linter types imported components as `any` and widens literals differently from vue-tsc,
    // so in single-file components it calls needed assertions unnecessary.
    name: 'project/vue-types',
    files: ['**/*.vue'],
    rules: {
      '@typescript-eslint/no-unnecessary-type-assertion': 'off',
      '@typescript-eslint/no-redundant-type-constituents': 'off',
    },
  },
  {
    // `expect(store.method)` hands a mocked method to the matcher without calling it.
    name: 'project/tests',
    files: ['**/__tests__/**'],
    rules: { '@typescript-eslint/unbound-method': 'off' },
  },
  // Formatting is Prettier's job.
  skipFormatting,

  // Limits on tangle, not on length (no max-lines or max-statements).
  {
    name: 'project/readability',
    files: ['src/**/*.{ts,vue}'],
    plugins: { sonarjs },
    rules: {
      complexity: ['error', 15],
      'sonarjs/cognitive-complexity': ['error', 15],
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
