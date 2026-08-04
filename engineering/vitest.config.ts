import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  // 注意：不引入 vite.config 的 AutoImport/Components(ElementPlusResolver)。
  // 引入后 <el-*> 会被解析为真实 element-plus 组件，而测试环境（happy-dom）
  // 无法完整渲染，实测引入后失败数 275 → 324（净增）。el-* 组件在测试中
  // 依赖 @vue/test-utils 的 config.global.stubs（见 src/tests/setup.ts）。
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  test: {
    environment: 'happy-dom',
    setupFiles: ['src/tests/setup.ts'],
    include: ['src/**/*.{test,spec}.ts'],
    coverage: {
      provider: 'v8',
      thresholds: {
        lines: 65,
        branches: 65,
        functions: 65,
        statements: 65,
      },
    },
  },
})
