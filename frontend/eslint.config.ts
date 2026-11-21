import { globalIgnores } from 'eslint/config'
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript'
import pluginVue from 'eslint-plugin-vue'
import skipFormatting from '@vue/eslint-config-prettier/skip-formatting'
import sonarjs from 'eslint-plugin-sonarjs'
import pluginVueA11y from 'eslint-plugin-vuejs-accessibility'
import comments from '@eslint-community/eslint-plugin-eslint-comments'
import vitest from '@vitest/eslint-plugin'

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
  // Alt texts, labelled form fields, keyboard access for whatever reacts to clicks.
  ...pluginVueA11y.configs['flat/recommended'],
  {
    // A label that wraps its field, or points at it with `for`, is enough for browsers and screen readers.
    // Our select components render a native button or input, which a wrapping label names.
    rules: {
      'vuejs-accessibility/label-has-for': [
        'error',
        { required: { some: ['nesting', 'id'] }, controlComponents: ['AppSelect', 'SearchableSelect', 'RoleSelect'] },
      ],
    },
  },
  {
    // Comboboxes: focus stays in the field, which handles the arrow keys and Enter and points at the
    // active option with aria-activedescendant; the options themselves take no focus.
    name: 'project/comboboxes',
    files: [
      'src/components/AccessGrantSearch.vue',
      'src/components/SearchableSelect.vue',
      'src/components/AppSelect.vue',
    ],
    rules: {
      'vuejs-accessibility/interactive-supports-focus': 'off',
      'vuejs-accessibility/mouse-events-have-key-events': 'off',
      'vuejs-accessibility/click-events-have-key-events': 'off',
    },
  },
  {
    // The overlay behind the menu closes it on a click; the keyboard closes it with Escape. Set here:
    // a comment before the root element would turn the component into a fragment.
    name: 'project/context-menu-overlay',
    files: ['src/components/ContextMenu.vue'],
    rules: {
      'vuejs-accessibility/click-events-have-key-events': 'off',
      'vuejs-accessibility/no-static-element-interactions': 'off',
    },
  },
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

  // No silenced checks: every disable names its rules and says why; unused ones fail.
  { name: 'project/linter', linterOptions: { reportUnusedDisableDirectives: 'error' } },
  {
    name: 'project/no-silencing',
    files: ['src/**/*.{ts,vue}'],
    plugins: { '@eslint-community/eslint-comments': comments },
    rules: {
      '@eslint-community/eslint-comments/no-unlimited-disable': 'error',
      '@eslint-community/eslint-comments/require-description': 'error',
      '@typescript-eslint/ban-ts-comment': ['error', { 'ts-expect-error': 'allow-with-description' }],
    },
  },
  // Tests that test: every test asserts, no `.only` or skipped test is committed.
  {
    name: 'project/test-assertions',
    files: ['src/**/*.spec.ts'],
    plugins: { vitest },
    rules: {
      'vitest/expect-expect': 'error',
      'vitest/no-focused-tests': 'error',
      'vitest/no-disabled-tests': 'error',
    },
  },

  // Limits on tangle, not on length (no max-lines or max-statements).
  {
    name: 'project/readability',
    files: ['src/**/*.{ts,vue}'],
    plugins: { sonarjs },
    rules: {
      complexity: ['error', 15],
      'sonarjs/cognitive-complexity': ['error', 15],
      'max-depth': ['error', 4],
      // Unescaped HTML is an XSS hole; a real exception names its reason.
      'vue/no-v-html': 'error',
      'vue/no-unused-properties': ['error', { groups: ['props', 'data', 'computed', 'methods', 'setup'] }],
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
