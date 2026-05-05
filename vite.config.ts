import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig({
  plugins: [
    vue(),
    AutoImport({
      resolvers: [ElementPlusResolver()],
    }),
    Components({
      resolvers: [ElementPlusResolver()],
    }),
  ],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
  },
  envPrefix: ['VITE_', 'TAURI_'],
  build: {
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          // Three.js 相关单独分包
          if (id.includes('node_modules/three') || id.includes('three/examples')) {
            return 'three-vendor'
          }
          
          // ECharts 按需分包，只打包实际使用的部分
          if (id.includes('node_modules/echarts')) {
            return 'echarts-vendor'
          }
          
          // Element Plus 单独分包
          if (id.includes('node_modules/element-plus')) {
            return 'element-plus-vendor'
          }
          
          // Vue 相关框架库
          if (id.includes('node_modules/vue') || 
              id.includes('node_modules/vue-router') || 
              id.includes('node_modules/pinia')) {
            return 'framework-vendor'
          }
          
          // 其他第三方库
          if (id.includes('node_modules')) {
            return 'vendor'
          }
          
          // 业务代码按页面分割
          if (id.includes('src/views/')) {
            const match = id.match(/src\/views\/([A-Za-z0-9]+)/)
            if (match) {
              return `view-${match[1].toLowerCase()}`
            }
          }
          
          // 公共组件单独分包
          if (id.includes('src/components/')) {
            return 'components'
          }
        },
        // Chunk 文件命名规则
        chunkFileNames: 'assets/js/[name]-[hash].js',
        entryFileNames: 'assets/js/[name]-[hash].js',
        assetFileNames: 'assets/[ext]/[name]-[hash].[ext]',
      },
    },
    // 启用代码分割
    sourcemap: false,
    // 压缩选项
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true,
        drop_debugger: true,
      },
    },
  },
  // 优化依赖预构建
  optimizeDeps: {
    include: [
      'vue',
      'vue-router',
      'pinia',
      'element-plus',
      'axios',
    ],
    exclude: [
      'three',
      'echarts',
    ],
  },
})
