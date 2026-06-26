<template>
  <div
    class="health-check-panel"
    role="region"
    :aria-label="$t('healthCheck.ariaLabel')"
  >
    <div class="health-status-bar">
      <div class="status-summary">
        <el-tag
          v-if="checking"
          type="info"
          size="large"
          effect="dark"
        >
          <el-icon class="is-loading">
            <Loading />
          </el-icon>
          {{ $t('healthCheck.checking') }}
        </el-tag>
        <el-tag
          v-else-if="overallStatus === 'ok'"
          type="success"
          size="large"
          effect="dark"
        >
          {{ $t('healthCheck.allOk') }}
        </el-tag>
        <el-tag
          v-else-if="overallStatus === 'warning'"
          type="warning"
          size="large"
          effect="dark"
        >
          {{ $t('healthCheck.warningCount', { count: warningCount }) }}
        </el-tag>
        <el-tag
          v-else
          type="danger"
          size="large"
          effect="dark"
        >
          {{
            warningCount > 0
              ? $t('healthCheck.errorSummary', { errors: errorCount, warnings: '· ' + warningCount + ' ' + $t('healthCheck.warningCount', { count: '' }).replace(/\d+/, '').trim() })
              : $t('healthCheck.errorSummary', { errors: errorCount, warnings: '' })
          }}
        </el-tag>
      </div>
      <div class="status-actions">
        <el-button
          :loading="checking"
          :icon="RefreshRight"
          type="primary"
          size="small"
          @click="runAllChecks"
        >
          {{ $t('healthCheck.rerun') }}
        </el-button>
        <el-button
          :disabled="checking || items.length === 0"
          size="small"
          @click="copyDiagnostics"
        >
          <el-icon><CopyDocument /></el-icon>
          {{ $t('healthCheck.copyDiagnostics') }}
        </el-button>
      </div>
    </div>

    <div class="check-items">
      <div
        v-for="item in items"
        :key="item.id"
        class="check-card"
        :class="[
          'status-' + item.status,
          { expanded: expandedId === item.id }
        ]"
      >
        <div
          class="check-card-header"
          tabindex="0"
          role="button"
          :aria-expanded="expandedId === item.id"
          :aria-label="$t('healthCheck.checkItemAria', { name: item.name, status: statusLabel(item.status) })"
          @click="toggleExpand(item.id)"
          @keydown.enter="toggleExpand(item.id)"
          @keydown.space.prevent="toggleExpand(item.id)"
        >
          <div class="check-icon">
            <el-icon
              v-if="item.status === 'ok'"
              class="status-ok-icon"
            >
              <CircleCheckFilled />
            </el-icon>
            <el-icon
              v-else-if="item.status === 'warning'"
              class="status-warn-icon"
            >
              <WarningFilled />
            </el-icon>
            <el-icon
              v-else
              class="status-err-icon"
            >
              <CircleCloseFilled />
            </el-icon>
          </div>
          <div class="check-info">
            <span class="check-name">{{ item.name }}</span>
            <span class="check-message">{{ item.message }}</span>
          </div>
          <div class="check-meta">
            <el-tag
              v-if="item.version"
              size="small"
              type="info"
              effect="plain"
              class="version-tag"
            >
              {{ item.version }}
            </el-tag>
            <el-tag
              :type="statusTagType(item.status)"
              size="small"
              effect="plain"
            >
              {{ statusLabel(item.status) }}
            </el-tag>
          </div>
        </div>

        <el-collapse-transition>
          <div
            v-show="expandedId === item.id"
            class="check-card-body"
          >
            <div class="check-details">
              <pre class="detail-text">{{ item.details }}</pre>
            </div>
            <div
              v-if="item.status !== 'ok' && item.fix_description"
              class="check-fix"
            >
              <el-alert
                :title="item.fix_auto ? $t('healthCheck.fixAutoHint') : $t('healthCheck.fixManualHint')"
                :type="item.status === 'error' ? 'error' : 'warning'"
                :closable="false"
                show-icon
              >
                <p>{{ item.fix_description }}</p>
                <div class="fix-actions">
                  <el-button
                    v-if="item.fix_auto && item.fix_action"
                    type="primary"
                    size="small"
                    :loading="fixingId === item.id"
                    @click.stop="runAutoFix(item.id)"
                  >
                    {{ $t('healthCheck.oneClickFix') }}
                  </el-button>
                  <el-button
                    size="small"
                    :loading="singleCheckingId === item.id"
                    @click.stop="retrySingleCheck(item.id)"
                  >
                    {{ $t('healthCheck.retryItem') }}
                  </el-button>
                </div>
              </el-alert>
            </div>
          </div>
        </el-collapse-transition>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { invoke } from '@tauri-apps/api/core'
import { ElMessage } from 'element-plus'
import {
  Loading, RefreshRight, CopyDocument,
  CircleCheckFilled, CircleCloseFilled, WarningFilled
} from '@element-plus/icons-vue'

interface HealthItem {
  id: string
  name: string
  status: string
  message: string
  details: string
  version: string | null
  fix_action: string | null
  fix_description: string | null
  fix_auto: boolean
}

const items = ref<HealthItem[]>([])
const checking = ref(false)
const fixingId = ref<string | null>(null)
const singleCheckingId = ref<string | null>(null)
const expandedId = ref<string | null>(null)

const { t } = useI18n()

const overallStatus = computed(() => {
  if (items.value.length === 0) return ''
  const hasError = items.value.some(i => i.status === 'error')
  if (hasError) return 'error'
  const hasWarning = items.value.some(i => i.status === 'warning')
  if (hasWarning) return 'warning'
  return 'ok'
})

const errorCount = computed(() => items.value.filter(i => i.status === 'error').length)
const warningCount = computed(() => items.value.filter(i => i.status === 'warning').length)

function statusLabel(status: string) {
  switch (status) {
    case 'ok': return t('healthCheck.statusOk')
    case 'warning': return t('healthCheck.statusWarning')
    case 'error': return t('healthCheck.statusError')
    default: return status
  }
}

function statusTagType(status: string) {
  switch (status) {
    case 'ok': return 'success'
    case 'warning': return 'warning'
    case 'error': return 'danger'
    default: return 'info'
  }
}

function toggleExpand(id: string) {
  expandedId.value = expandedId.value === id ? null : id
}

async function runAllChecks() {
  checking.value = true
  expandedId.value = null
  try {
    const results = await invoke<HealthItem[]>('run_health_check')
    items.value = results
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : String(e)
    ElMessage.error(t('healthCheck.checkFailed', { message: errorMessage || t('common.unknownError') }))
  } finally {
    checking.value = false
  }
}

async function retrySingleCheck(id: string) {
  singleCheckingId.value = id
  try {
    const result = await invoke<HealthItem>('run_single_health_check', { component: id })
    const idx = items.value.findIndex(i => i.id === id)
    if (idx !== -1) {
      items.value[idx] = result
    }
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : String(e)
    ElMessage.error(t('healthCheck.singleCheckFailed', { message: errorMessage || t('common.unknownError') }))
  } finally {
    singleCheckingId.value = null
  }
}

async function runAutoFix(id: string) {
  fixingId.value = id
  try {
    const result = await invoke<string>('auto_fix_health', { component: id })
    ElMessage.success(result)
    await retrySingleCheck(id)
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : String(e)
    ElMessage.error(t('healthCheck.autoFixFailed', { message: errorMessage || t('common.unknownError') }))
  } finally {
    fixingId.value = null
  }
}

async function copyDiagnostics() {
  try {
    const text = await invoke<string>('get_diagnostics_text')
    await navigator.clipboard.writeText(text)
    ElMessage.success(t('healthCheck.diagnosticsCopied'))
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : String(e)
    ElMessage.error(t('healthCheck.copyFailed', { message: errorMessage || t('common.unknownError') }))
  }
}

defineExpose({ runAllChecks })
</script>

<style scoped>
.health-check-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.health-status-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 8px 0;
}

.status-summary {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-actions {
  display: flex;
  gap: 8px;
}

.check-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.check-card {
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  overflow: hidden;
  transition: all 0.25s ease;
  background: var(--el-bg-color);
}

.check-card.status-error {
  border-left: 3px solid var(--el-color-danger);
}

.check-card.status-warning {
  border-left: 3px solid var(--el-color-warning);
}

.check-card.status-ok {
  border-left: 3px solid var(--el-color-success);
}

.check-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.check-card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  cursor: pointer;
  user-select: none;
  transition: background 0.15s ease;
}

.check-card-header:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: -2px;
}

.check-card-header:hover {
  background: var(--el-fill-color-light);
}

.check-icon {
  flex-shrink: 0;
  font-size: 22px;
}

.status-ok-icon {
  color: var(--el-color-success);
}

.status-warn-icon {
  color: var(--el-color-warning);
}

.status-err-icon {
  color: var(--el-color-danger);
}

.check-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.check-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.check-message {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.check-meta {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 6px;
}

.version-tag {
  font-family: 'Cascadia Code', 'Fira Code', monospace;
}

.check-card-body {
  border-top: 1px solid var(--el-border-color-lighter);
  padding: 16px 16px 16px 50px;
}

.detail-text {
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.7;
  color: var(--el-text-color-regular);
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
  padding: 10px 12px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
}

.check-fix {
  margin-top: 12px;
}

.fix-actions {
  margin-top: 10px;
  display: flex;
  gap: 8px;
}

@media (max-width: 600px) {
  .health-status-bar {
    flex-direction: column;
    align-items: flex-start;
  }

  .check-card-header {
    flex-wrap: wrap;
    gap: 8px;
  }

  .check-meta {
    width: 100%;
    justify-content: flex-start;
    margin-top: 4px;
  }
}
</style>
