<template>
  <Teleport to="body">
    <Transition name="dialog-fade">
      <div v-if="visible" class="conflict-overlay" @click.self="handleClose">
        <div class="conflict-dialog">
          <div class="dialog-header" :class="severityClass">
            <div class="header-icon">
              <el-icon :size="24"><WarningFilled /></el-icon>
            </div>
            <h3>{{ dialogData.title }}</h3>
          </div>

          <div class="dialog-body">
            <div class="error-code">
              <el-tag :type="severityTag" size="small">{{ dialogData.severity }}</el-tag>
              <span class="code-text">{{ dialogData.code }}</span>
            </div>

            <div class="message-section">
              <p class="error-message">{{ dialogData.message }}</p>
            </div>

            <div v-if="dialogData.detail" class="detail-section">
              <h4>详细说明</h4>
              <p>{{ dialogData.detail }}</p>
            </div>

            <div v-if="dialogData.suggestion" class="suggestion-section">
              <h4>
                <el-icon><Opportunity /></el-icon>
                解决方案建议
              </h4>
              <p class="suggestion-text">{{ dialogData.suggestion }}</p>
            </div>
          </div>

          <div class="dialog-footer">
            <el-button type="primary" @click="handleClose">我知道了</el-button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { WarningFilled, Opportunity } from '@element-plus/icons-vue'
import type { ErrorDialogPayload } from '@/utils/http'

const visible = ref(false)
const dialogData = ref<ErrorDialogPayload>({
  title: '',
  code: '',
  message: '',
  severity: 'error',
  detail: '',
  suggestion: '',
  recoverable: false,
})

const severityClass = computed(() => {
  switch (dialogData.value.severity) {
    case 'critical': return 'severity-critical'
    case 'error': return 'severity-error'
    case 'warning': return 'severity-warning'
    default: return 'severity-error'
  }
})

const severityTag = computed(() => {
  switch (dialogData.value.severity) {
    case 'critical': return 'danger'
    case 'error': return 'danger'
    case 'warning': return 'warning'
    default: return 'danger'
  }
})

function handleError(event: CustomEvent<ErrorDialogPayload>) {
  dialogData.value = event.detail
  visible.value = true
}

function handleClose() {
  visible.value = false
}

onMounted(() => {
  window.addEventListener('manufacturing-error', handleError as EventListener)
})

onBeforeUnmount(() => {
  window.removeEventListener('manufacturing-error', handleError as EventListener)
})
</script>

<style lang="scss" scoped>
.conflict-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 3000;
}

.conflict-dialog {
  background: #fff;
  border-radius: 12px;
  width: 540px;
  max-width: 90vw;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.25);
}

.dialog-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 24px;
  border-radius: 12px 12px 0 0;
  color: #fff;

  &.severity-critical {
    background: linear-gradient(135deg, #ff1744, #d50000);
  }
  &.severity-error {
    background: linear-gradient(135deg, #ff9800, #e65100);
  }
  &.severity-warning {
    background: linear-gradient(135deg, #ffc107, #f9a825);
  }

  .header-icon {
    flex-shrink: 0;
  }

  h3 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
  }
}

.dialog-body {
  padding: 20px 24px;
}

.error-code {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;

  .code-text {
    font-family: monospace;
    font-size: 12px;
    color: #999;
  }
}

.message-section {
  margin-bottom: 16px;

  .error-message {
    margin: 0;
    font-size: 15px;
    color: #333;
    line-height: 1.6;
  }
}

.detail-section {
  margin-bottom: 16px;
  padding: 12px;
  background: #f5f5f5;
  border-radius: 8px;
  border-left: 3px solid #e0e0e0;

  h4 {
    margin: 0 0 6px;
    font-size: 13px;
    color: #666;
  }

  p {
    margin: 0;
    font-size: 13px;
    color: #555;
    line-height: 1.6;
  }
}

.suggestion-section {
  padding: 14px;
  background: #e3f2fd;
  border-radius: 8px;
  border-left: 3px solid #1976d2;

  h4 {
    display: flex;
    align-items: center;
    gap: 6px;
    margin: 0 0 8px;
    font-size: 14px;
    color: #1565c0;
  }

  .suggestion-text {
    margin: 0;
    font-size: 13px;
    color: #333;
    line-height: 1.7;
    white-space: pre-wrap;
  }
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  padding: 16px 24px;
  border-top: 1px solid #eee;
}

.dialog-fade-enter-active,
.dialog-fade-leave-active {
  transition: opacity 0.25s ease;
}

.dialog-fade-enter-from,
.dialog-fade-leave-to {
  opacity: 0;
}
</style>
