import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  test: {
    environment: 'happy-dom',
    globals: true,
    include: ['src/**/*.{test,spec}.{ts,js}'],
    setupFiles: ['src/tests/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['src/**/*.{ts,vue}'],
      exclude: [
        'src/**/*.{test,spec}.{ts,js}',
        'src/types/**',
        'src/main.ts',
        'src/router/**',
        'node_modules/**',
        'dist/**',
        'src/tests/**',
      ],
      thresholds: {
        global: {
          branches: 60,
          functions: 65,
          lines: 70,
          statements: 70,
        },
      },
    },
  },
})