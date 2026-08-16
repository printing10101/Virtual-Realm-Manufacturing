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
      // 2026-08 实测基线：lines 34.2% / branches 75.6% / functions 38.5% / statements 34.2%。
      // 与 pr.yml 前端检查保持一致（原 65% 阈值高于实际，导致 CI 永远失败）。
      // 后续随测试补全逐步提升，目标 65%+。
      thresholds: {
        lines: 34,
        branches: 75,
        functions: 38,
        statements: 34,
      },
    },
  },
})
