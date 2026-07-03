<template>
  <div class="general-settings">
    <!-- 版本不一致警告 -->
    <el-alert
      v-if="versionStore.inconsistencyDetails && !versionStore.isConsistent"
      :title="$t('settings.versionWarningTitle')"
      type="error"
      :closable="false"
      show-icon
      class="version-warning"
    >
      <div>
        {{ $t('settings.versionWarningMsg') }}
        <ul v-if="versionStore.inconsistencyDetails">
          <li
            v-for="(detail, idx) in versionStore.inconsistencyDetails"
            :key="idx"
          >
            {{ detail }}
          </li>
        </ul>
      </div>
    </el-alert>

    <!-- 版本信息 - stat-card 网格 -->
    <div class="content-card">
      <div class="content-card__header">
        <span class="content-card__title">
          <el-icon style="margin-right: 6px;"><InfoFilled /></el-icon>
          {{ $t('settings.versionInfo') }}
        </span>
        <el-tag
          :type="versionStore.isConsistent ? 'success' : 'danger'"
          size="small"
        >
          {{ versionStore.isConsistent ? $t('settings.versionConsistent') : $t('settings.versionInconsistent') }}
        </el-tag>
      </div>
      <div class="content-card__body">
        <div class="version-grid">
          <div class="version-card">
            <div class="version-card__icon">
              <el-icon :size="24">
                <Monitor />
              </el-icon>
            </div>
            <div class="version-card__info">
              <span class="version-card__label">{{ $t('settings.frontendVersion') }}</span>
              <span class="version-card__value">{{ versionStore.frontendVersion }}</span>
              <span
                v-if="versionStore.frontendCommit"
                class="version-card__hash"
              >{{ versionStore.frontendCommit }}</span>
            </div>
          </div>
          <div class="version-card">
            <div class="version-card__icon">
              <el-icon :size="24">
                <Cpu />
              </el-icon>
            </div>
            <div class="version-card__info">
              <span class="version-card__label">{{ $t('settings.rustBackendVersion') }}</span>
              <span class="version-card__value">{{ versionStore.rustVersion || $t('settings.loading') }}</span>
              <span
                v-if="versionStore.rustCommit"
                class="version-card__hash"
              >{{ versionStore.rustCommit }}</span>
            </div>
          </div>
          <div class="version-card">
            <div class="version-card__icon">
              <el-icon :size="24">
                <Coin />
              </el-icon>
            </div>
            <div class="version-card__info">
              <span class="version-card__label">{{ $t('settings.pythonSidecarVersion') }}</span>
              <span class="version-card__value">{{ versionStore.pythonVersion || $t('settings.notConnected') }}</span>
              <span
                v-if="versionStore.pythonCommit"
                class="version-card__hash"
              >{{ versionStore.pythonCommit }}</span>
            </div>
          </div>
          <div class="version-card version-card--action">
            <el-button
              size="small"
              :loading="versionStore.isLoading"
              @click="refreshVersions"
            >
              <el-icon
                v-if="!versionStore.isLoading"
                style="margin-right: 4px;"
              >
                <Refresh />
              </el-icon>
              {{ $t('settings.refreshVersion') }}
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 系统设置 -->
    <div class="content-card">
      <div class="content-card__header">
        <span class="content-card__title">
          <el-icon style="margin-right: 6px;"><Setting /></el-icon>
          {{ $t('settings.systemSettings') }}
        </span>
      </div>
      <div class="content-card__body">
        <el-form
          :model="store.settings"
          label-width="140px"
          class="settings-form"
        >
          <div class="form-section">
            <div class="form-section__title">
              <el-icon><Connection /></el-icon>
              <span>{{ $t('settings.aiModeConfig') }}</span>
            </div>
            <el-form-item :label="$t('settings.aiMode')">
              <el-radio-group v-model="store.settings.aiMode">
                <el-radio value="local">
                  {{ $t('settings.localMode') }}
                </el-radio>
                <el-radio value="cloud">
                  {{ $t('settings.cloudMode') }}
                </el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item :label="$t('settings.localModel')">
              <el-select
                v-model="store.settings.localModel"
                style="width: 200px;"
              >
                <el-option
                  label="qwen2.5:7b"
                  value="qwen2.5:7b"
                />
                <el-option
                  label="qwen2.5:14b"
                  value="qwen2.5:14b"
                />
              </el-select>
            </el-form-item>
            <el-form-item :label="$t('settings.computeDevice')">
              <el-select
                v-model="store.settings.device"
                style="width: 200px;"
              >
                <el-option
                  label="CPU"
                  value="cpu"
                />
                <el-option
                  :label="$t('settings.gpuCuda')"
                  value="cuda"
                />
              </el-select>
            </el-form-item>
          </div>

          <el-divider />

          <div class="form-section">
            <div class="form-section__title">
              <el-icon><Tools /></el-icon>
              <span>{{ $t('settings.generalPreferences') }}</span>
            </div>
            <el-form-item :label="$t('settings.offlineMode')">
              <el-switch v-model="store.settings.offlineMode" />
            </el-form-item>
            <el-form-item :label="$t('settings.language')">
              <el-select
                v-model="currentLocale"
                style="width: 200px;"
                @change="handleLocaleChange"
              >
                <el-option
                  :label="$t('settings.languageChinese')"
                  value="zh-CN"
                />
                <el-option
                  :label="$t('settings.languageEnglish')"
                  value="en"
                />
              </el-select>
            </el-form-item>
          </div>

          <div class="form-actions">
            <el-button
              type="primary"
              @click="store.saveSettings()"
            >
              <el-icon style="margin-right: 4px;">
                <Check />
              </el-icon>
              {{ $t('settings.saveSettings') }}
            </el-button>
            <el-button @click="store.resetSettings()">
              <el-icon style="margin-right: 4px;">
                <RefreshLeft />
              </el-icon>
              {{ $t('common.reset') }}
            </el-button>
          </div>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useSettingsStore } from '@/stores/settings'
import { useVersionStore } from '@/stores/version'
import { useSettings } from '@/composables/useSettings'
import {
  InfoFilled, Monitor, Cpu, Coin, Refresh,
  Setting, Connection, Tools, Check, RefreshLeft
} from '@element-plus/icons-vue'

const store = useSettingsStore()
const versionStore = useVersionStore()
const { currentLocale, handleLocaleChange } = useSettings()

function refreshVersions() {
  versionStore.fetchVersionInfo()
  versionStore.checkConsistency()
}
</script>

<style scoped>
.version-warning {
  margin-bottom: 16px;
}

.version-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr) auto;
  gap: 12px;
  align-items: stretch;
}

.version-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
  background: var(--bg-50);
  border-radius: var(--radius-md);
  border: 1px solid var(--bg-100);
  transition: border-color 0.2s;
}

.version-card:hover {
  border-color: var(--bg-200);
}

.version-card--action {
  display: flex;
  align-items: center;
  justify-content: center;
}

.version-card__icon {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  background: var(--bg-0);
  color: var(--brand-500);
  flex-shrink: 0;
  border: 1px solid var(--bg-100);
}

.version-card__info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.version-card__label {
  font-size: 12px;
  color: var(--text-tertiary);
}

.version-card__value {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.version-card__hash {
  font-size: 11px;
  color: var(--text-tertiary);
  font-family: monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.form-section {
  padding: 4px 0;
}

.form-section__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--bg-100);
}

.form-section__title .el-icon {
  color: var(--brand-500);
  font-size: 16px;
}

.form-actions {
  display: flex;
  gap: 8px;
  padding-top: 8px;
  margin-top: 8px;
  border-top: 1px solid var(--bg-100);
}

.settings-form :deep(.el-form-item) {
  margin-bottom: 20px;
}

.settings-form :deep(.el-divider) {
  border-color: var(--bg-100);
  margin: 4px 0;
}
</style>
