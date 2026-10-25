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
        // A little below the level reached (about 98 %): high enough that untested features stand
        // out, low enough that a small change doesn't need tests written for the number's sake.
        thresholds: { lines: 95, statements: 95, functions: 95, branches: 90 },
      },
    },
  }),
)
