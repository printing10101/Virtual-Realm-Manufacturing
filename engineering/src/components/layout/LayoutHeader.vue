<template>
  <header class="layout-header">
    <div class="header-search">
      <el-icon :size="16">
        <Search />
      </el-icon>
      <input
        type="text"
        :placeholder="t('appLayout.searchPlaceholder')"
        class="search-input"
      >
    </div>
    <div class="header-actions">
      <el-tooltip
        :content="t('appLayout.refresh')"
        placement="bottom"
      >
        <button
          class="header-btn"
          @click="emit('refresh')"
        >
          <el-icon :size="18">
            <Refresh />
          </el-icon>
        </button>
      </el-tooltip>
      <el-dropdown
        trigger="click"
        placement="bottom-end"
      >
        <button class="header-btn notification-btn">
          <el-icon :size="18">
            <Bell />
          </el-icon>
          <span class="notification-dot" />
        </button>
        <template #dropdown>
          <el-dropdown-menu class="notification-dropdown">
            <div class="notification-header">
              <span class="notification-title">{{ t('appLayout.notifications') }}</span>
              <el-button
                text
                size="small"
                @click="markAllRead"
              >
                {{ t('appLayout.markAllRead') }}
              </el-button>
            </div>
            <el-divider style="margin: 4px 0" />
            <div
              v-for="n in notifications"
              :key="n.id"
              class="notification-item"
              :class="{ unread: !n.read }"
            >
              <div
                class="notification-dot-indicator"
                :class="n.type"
              />
              <div class="notification-content">
                <span class="notification-text">{{ n.text }}</span>
                <span class="notification-time">{{ n.time }}</span>
              </div>
            </div>
            <el-divider style="margin: 4px 0" />
            <div class="notification-footer">
              <el-button
                text
                size="small"
              >
                {{ t('appLayout.viewAllNotifications') }}
              </el-button>
            </div>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      <BackendStatusIndicator />
      <el-dropdown
        trigger="click"
        @command="handleFileCommand"
      >
        <button class="header-btn file-btn">
          <el-icon :size="18">
            <Folder />
          </el-icon>
        </button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="new">
              <el-icon :size="16">
                <DocumentAdd />
              </el-icon>{{ t('appLayout.newProject') }}
            </el-dropdown-item>
            <el-dropdown-item command="open">
              <el-icon :size="16">
                <FolderOpened />
              </el-icon>{{ t('appLayout.openProject') }}
            </el-dropdown-item>
            <el-dropdown-item
              divided
              command="save"
            >
              <el-icon :size="16">
                <Document />
              </el-icon>{{ t('appLayout.save') }}
            </el-dropdown-item>
            <el-dropdown-item command="save-as">
              <el-icon :size="16">
                <CopyDocument />
              </el-icon>{{ t('appLayout.saveAs') }}
            </el-dropdown-item>
            <el-dropdown-item
              divided
              command="download"
            >
              <el-icon :size="16">
                <Download />
              </el-icon>{{ t('appLayout.downloadProject') }}
            </el-dropdown-item>
            <el-dropdown-item
              divided
              command="import-step"
            >
              <el-icon :size="16">
                <Upload />
              </el-icon>{{ t('appLayout.importStep') }}
            </el-dropdown-item>
            <el-dropdown-item command="import-dxf">
              <el-icon :size="16">
                <DocumentCopy />
              </el-icon>{{ t('appLayout.importDxf') }}
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      <span
        v-if="projectName"
        class="project-indicator"
      >
        {{ projectName }}
        <el-tag
          v-if="isModified"
          size="small"
          type="warning"
          effect="plain"
        >{{ t('appLayout.unsaved') }}</el-tag>
      </span>
    </div>
  </header>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Search, Refresh, Bell, Folder, DocumentAdd, FolderOpened,
  Document, CopyDocument, Download, Upload, DocumentCopy,
} from '@element-plus/icons-vue'
import BackendStatusIndicator from '@/components/BackendStatusIndicator.vue'
import http from '@/utils/http'
import { API_CONFIG, buildApiPath } from '@/config/api'
import { extractErrorMessage } from '@/utils/error-handler'

const { t } = useI18n()

const emit = defineEmits<{
  (e: 'file-command', cmd: string): void
  (e: 'refresh'): void
}>()

defineProps<{
  projectName?: string
  isModified?: boolean
}>()

const notifications = ref<Array<{ id: number; text: string; time: string; type: string; read: boolean }>>([])

async function fetchNotifications() {
  try {
    const resp = await http.get(buildApiPath(API_CONFIG.V1, '/notifications'))
    if (resp.data.code === 0 && resp.data.data) {
      notifications.value = resp.data.data.map((item: { notification_id: string; title: string; created_at: number; priority: string }, index: number) => ({
        id: index + 1,
        text: item.title,
        time: formatTime(item.created_at),
        type: mapPriorityToType(item.priority),
        read: false,
      }))
    }
  } catch (error) {
    console.warn('获取通知失败:', extractErrorMessage(error))
  }
}

function formatTime(timestamp: number): string {
  const now = Date.now()
  const diff = now - timestamp * 1000
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 60) return t('home.timeMinutesAgo', { n: minutes })
  if (hours < 24) return t('home.timeHoursAgo', { n: hours })
  return t('home.timeDaysAgo', { n: days })
}

function mapPriorityToType(priority: string): string {
  const priorityMap: Record<string, string> = {
    critical: 'error',
    high: 'warning',
    medium: 'info',
    low: 'success',
  }
  return priorityMap[priority] || 'info'
}

onMounted(() => {
  fetchNotifications()
})

function markAllRead() {
  notifications.value.forEach(n => n.read = true)
}

function handleFileCommand(cmd: string) {
  emit('file-command', cmd)
}
</script>

<style scoped>
.layout-header {
  height: var(--header-height);
  padding: 0 var(--page-padding);
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: var(--bg-header);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border-light);
  position: sticky;
  top: 0;
  z-index: 50;
  flex-shrink: 0;
  gap: 16px;
}

.header-search {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 14px;
  background-color: var(--bg-200);
  border-radius: var(--radius-md);
  border: 1px solid transparent;
  transition: border-color var(--transition-fast), background-color var(--transition-fast), box-shadow var(--transition-fast);
  width: 280px;
}

.header-search:focus-within {
  border-color: var(--accent-primary);
  background-color: var(--bg-0);
  box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.12);
}

.search-input {
  border: none;
  background: transparent;
  outline: none;
  font-size: 0.85rem;
  color: var(--text-primary);
  width: 100%;
  font-family: var(--font-sans);
}

.search-input::placeholder {
  color: var(--text-400);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.header-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: var(--text-500);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  position: relative;
}

.header-btn:hover {
  background-color: var(--bg-200);
  color: var(--text-primary);
}

.notification-btn {
  position: relative;
}

.notification-dot {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 8px;
  height: 8px;
  background-color: var(--error);
  border-radius: 50%;
  border: 2px solid var(--bg-primary);
}

.file-btn {
  width: 36px;
  height: 36px;
}

.project-indicator {
  font-size: 0.8rem;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 6px;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-left: 4px;
}

/* ===== Notification Dropdown ===== */
.notification-dropdown {
  width: 320px;
}

.notification-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px 4px;
}

.notification-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-primary);
}

.notification-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px 16px;
  cursor: pointer;
  transition: background-color var(--transition-fast);
}

.notification-item:hover {
  background-color: var(--bg-100);
}

.notification-item.unread {
  background-color: var(--info-bg);
}

.notification-dot-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 5px;
  flex-shrink: 0;
}

.notification-dot-indicator.error { background-color: var(--error); }
.notification-dot-indicator.success { background-color: var(--success); }
.notification-dot-indicator.info { background-color: var(--info); }
.notification-dot-indicator.warning { background-color: var(--warning); }

.notification-content {
  flex: 1;
  min-width: 0;
}

.notification-text {
  display: block;
  font-size: 0.8rem;
  color: var(--text-primary);
  line-height: 1.4;
}

.notification-time {
  display: block;
  font-size: 0.7rem;
  color: var(--text-400);
  margin-top: 2px;
}

.notification-footer {
  padding: 4px 16px 8px;
  text-align: center;
}
</style>