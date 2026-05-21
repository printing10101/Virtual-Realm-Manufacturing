<template>
  <Teleport to="body">
    <TransitionGroup
      name="error-notification"
      tag="div"
      class="error-notification-container"
    >
      <div
        v-for="notification in visibleNotifications"
        :key="notification.id"
        class="error-notification-card"
        :class="severityClass(notification.severity)"
        @click="toggleDetail(notification.id)"
      >
        <!-- 关闭按钮 -->
        <button
          class="error-close-btn"
          @click.stop="dismiss(notification.id)"
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.5"
          >
            <line
              x1="18"
              y1="6"
              x2="6"
              y2="18"
            /><line
              x1="6"
              y1="6"
              x2="18"
              y2="18"
            />
          </svg>
        </button>

        <!-- 严重程度图标 -->
        <div class="error-header">
          <span class="error-icon">
            <svg
              v-if="notification.severity === 'critical'"
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="currentColor"
            >
              <circle
                cx="12"
                cy="12"
                r="10"
                fill="#ff1744"
              />
              <text
                x="12"
                y="17"
                text-anchor="middle"
                fill="white"
                font-size="14"
                font-weight="bold"
              >!</text>
            </svg>
            <svg
              v-else-if="notification.severity === 'error'"
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="currentColor"
            >
              <polygon
                points="12,3 22,21 2,21"
                fill="#ff9800"
              />
              <text
                x="12"
                y="17"
                text-anchor="middle"
                fill="white"
                font-size="12"
                font-weight="bold"
              >!</text>
            </svg>
            <svg
              v-else
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="currentColor"
            >
              <polygon
                points="12,3 22,21 2,21"
                fill="#ffc107"
              />
              <text
                x="12"
                y="17"
                text-anchor="middle"
                fill="#333"
                font-size="12"
                font-weight="bold"
              >!</text>
            </svg>
          </span>
          <span class="error-code">{{ notification.errorCode || notification.code }}</span>
          <span class="error-message">{{ notification.message }}</span>
        </div>

        <!-- 详细信息 -->
        <div
          v-if="notification.expanded || notification.severity === 'critical'"
          class="error-body"
        >
          <p
            v-if="notification.detail"
            class="error-detail"
          >
            {{ notification.detail }}
          </p>
          <p
            v-if="notification.suggestion"
            class="error-suggestion"
          >
            <strong>建议：</strong>{{ notification.suggestion }}
          </p>
          <div
            v-if="notification.adjusted_values && Object.keys(notification.adjusted_values).length"
            class="error-adjusted"
          >
            <strong>已调整参数：</strong>
            <span
              v-for="(val, key) in notification.adjusted_values"
              :key="key"
              class="adjusted-item"
            >
              {{ key }}: {{ val }}
            </span>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div
          v-if="notification.recoverable"
          class="error-actions"
        >
          <button
            class="btn-accept"
            @click.stop="accept(notification)"
          >
            接受调整
          </button>
          <button
            class="btn-manual"
            @click.stop="manualEdit(notification)"
          >
            手动修改
          </button>
        </div>
      </div>
    </TransitionGroup>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

interface ErrorNotification {
  id: string
  code?: string | number
  errorCode?: string
  message: string
  severity: 'critical' | 'error' | 'warning'
  detail?: string
  suggestion?: string
  recoverable?: boolean
  adjusted_values?: Record<string, any>
  expanded?: boolean
  createdAt: number
}

const notifications = ref<ErrorNotification[]>([])
let nextId = 0

const visibleNotifications = computed(() =>
  [...notifications.value].sort((a, b) => b.createdAt - a.createdAt)
)

function severityClass(severity: string): string {
  return `severity-${severity}`
}

function push(notif: Omit<ErrorNotification, 'id' | 'createdAt' | 'expanded'>): string {
  const id = `err-${++nextId}`
  const notification: ErrorNotification = {
    ...notif,
    id,
    createdAt: Date.now(),
    expanded: notif.severity === 'critical',
  }
  notifications.value.push(notification)

  if (notif.severity !== 'warning') {
    setTimeout(() => {
      const idx = notifications.value.findIndex((n) => n.id === id)
      if (idx !== -1 && !notification.recoverable) {
        notifications.value.splice(idx, 1)
      }
    }, 15000)
  } else {
    setTimeout(() => {
      const idx = notifications.value.findIndex((n) => n.id === id)
      if (idx !== -1) {
        notifications.value.splice(idx, 1)
      }
    }, 8000)
  }

  return id
}

function dismiss(id: string): void {
  const idx = notifications.value.findIndex((n) => n.id === id)
  if (idx !== -1) {
    notifications.value.splice(idx, 1)
  }
}

function toggleDetail(id: string): void {
  const n = notifications.value.find((x) => x.id === id)
  if (n) {
    n.expanded = !n.expanded
  }
}

function accept(notification: ErrorNotification): void {
  if (notification.adjusted_values) {
    window.dispatchEvent(
      new CustomEvent('manufacturing-error-accepted', {
        detail: { id: notification.id, adjusted_values: notification.adjusted_values },
      })
    )
  }
  dismiss(notification.id)
}

function manualEdit(notification: ErrorNotification): void {
  window.dispatchEvent(
    new CustomEvent('manufacturing-error-manual', {
      detail: { id: notification.id, error_code: notification.errorCode || notification.code },
    })
  )
  dismiss(notification.id)
}

defineExpose({ push, dismiss })
</script>

<style scoped>
.error-notification-container {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 420px;
  pointer-events: none;
}

.error-notification-card {
  pointer-events: all;
  background: white;
  border-radius: 10px;
  padding: 16px 18px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.14);
  cursor: pointer;
  position: relative;
  transition: transform 0.2s, box-shadow 0.2s;
}

.error-notification-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 30px rgba(0, 0, 0, 0.18);
}

.severity-critical {
  border-left: 5px solid #ff1744;
  animation: pulse-red 2s infinite;
}

.severity-error {
  border-left: 5px solid #ff9800;
}

.severity-warning {
  border-left: 5px solid #ffc107;
}

@keyframes pulse-red {
  0%, 100% { box-shadow: 0 4px 24px rgba(255, 23, 68, 0.14); }
  50% { box-shadow: 0 4px 32px rgba(255, 23, 68, 0.28); }
}

.error-close-btn {
  position: absolute;
  top: 10px;
  right: 10px;
  background: none;
  border: none;
  cursor: pointer;
  color: #999;
  padding: 2px;
  border-radius: 4px;
  transition: color 0.15s, background 0.15s;
}

.error-close-btn:hover {
  color: #333;
  background: #f0f0f0;
}

.error-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}

.error-icon {
  flex-shrink: 0;
}

.error-code {
  font-size: 12px;
  font-weight: 600;
  color: #666;
  background: #f5f5f5;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Consolas', 'Courier New', monospace;
}

.error-message {
  font-size: 14px;
  font-weight: 600;
  color: #222;
}

.error-body {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #eee;
}

.error-detail {
  font-size: 12.5px;
  color: #555;
  line-height: 1.6;
  margin-bottom: 6px;
}

.error-suggestion {
  font-size: 12.5px;
  color: #1976d2;
  line-height: 1.6;
  margin-bottom: 6px;
}

.error-adjusted {
  font-size: 12px;
  color: #2e7d32;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

.adjusted-item {
  background: #e8f5e9;
  padding: 2px 8px;
  border-radius: 4px;
  font-family: 'Consolas', monospace;
  font-size: 11px;
}

.error-actions {
  margin-top: 12px;
  display: flex;
  gap: 10px;
}

.btn-accept,
.btn-manual {
  padding: 7px 16px;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  font-weight: 500;
  transition: background 0.2s;
}

.btn-accept {
  background: #4caf50;
  color: white;
}

.btn-accept:hover {
  background: #388e3c;
}

.btn-manual {
  background: #f5f5f5;
  color: #333;
  border: 1px solid #ddd;
}

.btn-manual:hover {
  background: #e0e0e0;
}

/* 进入/离开动画 */
.error-notification-enter-active {
  transition: all 0.3s ease-out;
}

.error-notification-leave-active {
  transition: all 0.25s ease-in;
}

.error-notification-enter-from {
  opacity: 0;
  transform: translateX(80px);
}

.error-notification-leave-to {
  opacity: 0;
  transform: translateX(120px);
}
</style>
