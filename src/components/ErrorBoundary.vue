<template>
  <div
    v-if="error"
    class="error-boundary"
  >
    <div class="error-content">
      <el-icon
        class="error-icon"
        :size="64"
      >
        <WarningFilled />
      </el-icon>
      <h2>{{ t('errorBoundary.title') }}</h2>
      <p class="error-message">
        {{ error.message || t('errorBoundary.unknownError') }}
      </p>
      <div class="error-actions">
        <el-button
          type="primary"
          @click="reload"
        >
          {{ t('errorBoundary.reload') }}
        </el-button>
        <el-button @click="goHome">
          {{ t('errorBoundary.goHome') }}
        </el-button>
      </div>
      <details
        v-if="error.stack"
        class="error-details"
      >
        <summary>{{ t('errorBoundary.details') }}</summary>
        <pre>{{ error.stack }}</pre>
      </details>
    </div>
  </div>
  <slot v-else />
</template>

<script setup lang="ts">
import { ref, onErrorCaptured } from 'vue'
import { useI18n } from 'vue-i18n'
import { WarningFilled } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

const { t } = useI18n()
const router = useRouter()
const error = ref<Error | null>(null)

onErrorCaptured((err: Error) => {
  error.value = err
  console.error('ErrorBoundary caught error:', err)
  
  // 上报错误到监控系统（预留接口）
  reportError(err)
  
  return false // 阻止错误继续传播
})

function reload() {
  window.location.reload()
}

function goHome() {
  error.value = null
  router.push('/')
  ElMessage.success(t('errorBoundary.returnedHome'))
}

function reportError(err: Error) {
  // TODO: 集成错误监控服务（如 Sentry）
  console.warn('Error reporting not configured:', err.message)
}
</script>

<style scoped>
.error-boundary {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
  padding: 20px;
}

.error-content {
  background: white;
  border-radius: 12px;
  padding: 48px;
  max-width: 600px;
  text-align: center;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
}

.error-icon {
  color: #f56c6c;
  margin-bottom: 24px;
}

h2 {
  margin: 0 0 16px;
  color: #303133;
  font-size: 24px;
  font-weight: 600;
}

.error-message {
  margin: 0 0 32px;
  color: #606266;
  font-size: 16px;
  line-height: 1.6;
}

.error-actions {
  display: flex;
  gap: 16px;
  justify-content: center;
  margin-bottom: 24px;
}

.error-details {
  margin-top: 24px;
  text-align: left;
}

.error-details summary {
  cursor: pointer;
  color: #909399;
  font-size: 14px;
  margin-bottom: 12px;
  user-select: none;
}

.error-details pre {
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 16px;
  overflow-x: auto;
  font-size: 12px;
  line-height: 1.5;
  color: #606266;
  max-height: 300px;
}
</style>
