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
        // The level reached so far, so it can only go up; the goal is 90 %.
        thresholds: { lines: 98, statements: 97, functions: 96, branches: 93 },
      },
    },
  }),
)
