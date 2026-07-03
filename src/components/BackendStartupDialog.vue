<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { useBackendStatus } from '@/composables/useBackendStatus'

const { t } = useI18n()

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'retry'): void
}>()

const { state, restart, stop, tauriMode, loading } = useBackendStatus()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const isError = computed(
  () => state.status === 'failed' || state.status === 'crashed',
)

const isStarting = computed(() => state.status === 'starting')

const shouldShow = computed(
  () => tauriMode.value && (isError.value || isStarting.value),
)

const errorTitle = computed(() => {
  if (state.status === 'crashed') return t('backendStartup.crashed')
  if (state.status === 'failed') return t('backendStartup.failed')
  return t('backendStartup.starting')
})

function onRetry() {
  restart().then(() => {
    if (state.status !== 'failed' && state.status !== 'crashed') {
      ElMessage.success(t('backendStartup.restarting'))
    }
  })
  emit('retry')
}

function onClose() {
  visible.value = false
}

function onStop() {
  stop()
}
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="errorTitle"
    :show-close="!isStarting"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    width="480px"
    align-center
    append-to-body
  >
    <div class="startup-content">
      <!-- 启动中 -->
      <template v-if="isStarting">
        <div class="status-icon starting">
          <el-icon class="rotating">
            <Loading />
          </el-icon>
        </div>
        <p class="status-msg">
          {{ state.message }}
        </p>
        <el-progress
          :percentage="state.progress"
          :stroke-width="10"
          :show-text="true"
          status="warning"
        />
        <p class="status-hint">
          {{ t('backendStartup.firstLaunchHint') }}
        </p>
      </template>

      <!-- 错误 -->
      <template v-else-if="isError">
        <div class="status-icon error">
          <el-icon><CircleCloseFilled /></el-icon>
        </div>
        <p class="status-msg error">
          {{ state.message }}
        </p>
        <el-alert
          v-if="state.last_error"
          type="error"
          :title="t('backendStartup.errorDetails')"
          :closable="false"
          show-icon
        >
          <pre class="error-detail">{{ state.last_error }}</pre>
        </el-alert>
        <p class="status-hint">
          {{ t('backendStartup.errorHint') }}
        </p>
      </template>
    </div>

    <template #footer>
      <template v-if="isStarting">
        <el-button
          :loading="true"
          type="info"
          plain
          disabled
        >
          {{ t('backendStartup.startingBtn') }}
        </el-button>
      </template>
      <template v-else>
        <el-button @click="onClose">
          {{ t('backendStartup.close') }}
        </el-button>
        <el-button
          plain
          @click="onStop"
        >
          {{ t('backendStartup.stopBackend') }}
        </el-button>
        <el-button
          type="primary"
          :loading="loading"
          @click="onRetry"
        >
          {{ t('backendStartup.retry') }}
        </el-button>
      </template>
    </template>
  </el-dialog>
</template>

<script lang="ts">
import { Loading, CircleCloseFilled } from '@element-plus/icons-vue'
export default { components: { Loading, CircleCloseFilled } }
</script>

<style scoped>
.startup-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 12px 0;
  gap: 16px;
}
.status-icon {
  font-size: 56px;
  line-height: 1;
}
.status-icon.starting { color: var(--warning); }
.status-icon.error { color: var(--error); }
.rotating {
  animation: rotate 1.4s linear infinite;
}
@keyframes rotate {
  to { transform: rotate(360deg); }
}
.status-msg {
  font-size: 15px;
  font-weight: 500;
  margin: 0;
  color: var(--text-primary);
}
.status-msg.error {
  color: var(--error);
}
.status-hint {
  font-size: 12px;
  color: var(--text-tertiary);
  margin: 0;
  max-width: 360px;
}
.error-detail {
  margin: 0;
  padding: 8px 12px;
  background: var(--bg-secondary);
  border-radius: 4px;
  font-size: 12px;
  font-family: 'Consolas', 'Monaco', monospace;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 160px;
  overflow: auto;
  color: var(--error);
}
</style>
