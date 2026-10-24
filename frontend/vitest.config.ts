import { fileURLToPath } from 'node:url'
import { mergeConfig, defineConfig, configDefaults } from 'vitest/config'
import viteConfig from './vite.config.ts'

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'jsdom',
      setupFiles: ['src/__tests__/setup.ts'],
      exclude: [...configDefaults.exclude, 'e2e/**'],
      root: fileURLToPath(new URL('./', import.meta.url)),
      coverage: {
        provider: 'v8',
        include: ['src/**'],
        exclude: ['src/main.ts', '**/*.d.ts', 'src/**/__tests__/**'],
        // Today's level, so it can only go up; the goal is 90 % (most components have no tests yet).
        thresholds: { lines: 34, statements: 33, functions: 25, branches: 26 },
      },
    },
  }),
)
