<template>
  <div>
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

    <el-card class="version-card">
      <template #header>
        <div class="card-header">
          {{ $t('settings.versionInfo') }}
          <el-tag
            :type="versionStore.isConsistent ? 'success' : 'danger'"
            size="small"
          >
            {{ versionStore.isConsistent ? $t('settings.versionConsistent') : $t('settings.versionInconsistent') }}
          </el-tag>
        </div>
      </template>
      <el-descriptions
        :column="1"
        border
      >
        <el-descriptions-item :label="$t('settings.frontendVersion')">
          {{ versionStore.frontendVersion }}
          <span
            v-if="versionStore.frontendCommit"
            class="commit-hash"
          >
            ({{ versionStore.frontendCommit }})
          </span>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('settings.rustBackendVersion')">
          {{ versionStore.rustVersion || $t('settings.loading') }}
          <span
            v-if="versionStore.rustCommit"
            class="commit-hash"
          >
            ({{ versionStore.rustCommit }})
          </span>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('settings.pythonSidecarVersion')">
          {{ versionStore.pythonVersion || $t('settings.notConnected') }}
          <span
            v-if="versionStore.pythonCommit"
            class="commit-hash"
          >
            ({{ versionStore.pythonCommit }})
          </span>
        </el-descriptions-item>
      </el-descriptions>
      <div class="refresh-btn">
        <el-button
          size="small"
          :loading="versionStore.isLoading"
          @click="refreshVersions"
        >
          {{ $t('settings.refreshVersion') }}
        </el-button>
      </div>
    </el-card>

    <el-card class="settings-card">
      <template #header>
        {{ $t('settings.systemSettings') }}
      </template>
      <el-form
        :model="store.settings"
        label-width="140px"
      >
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
          <el-select v-model="store.settings.localModel">
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
          <el-select v-model="store.settings.device">
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
        <el-form-item :label="$t('settings.offlineMode')">
          <el-switch v-model="store.settings.offlineMode" />
        </el-form-item>
        <el-form-item :label="$t('settings.language')">
          <el-select
            v-model="currentLocale"
            style="width: 160px;"
            @change="handleLocaleChange"
          >
            <el-option
              label="中文"
              value="zh-CN"
            />
            <el-option
              label="English"
              value="en"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            @click="store.saveSettings()"
          >
            {{ $t('settings.saveSettings') }}
          </el-button>
          <el-button @click="store.resetSettings()">
            {{ $t('common.reset') }}
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { useSettingsStore } from '@/stores/settings'
import { useVersionStore } from '@/stores/version'
import { useSettings } from '@/composables/useSettings'

const store = useSettingsStore()
const versionStore = useVersionStore()
const { currentLocale, handleLocaleChange } = useSettings()

function refreshVersions() {
  versionStore.fetchVersionInfo()
  versionStore.checkConsistency()
}
</script>

<style scoped>
.version-card {
  margin-bottom: 24px;
}

.version-warning {
  margin-bottom: 16px;
}

.settings-card {
  margin-bottom: 24px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.commit-hash {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-left: 8px;
  font-family: monospace;
}

.refresh-btn {
  margin-top: 16px;
  text-align: right;
}
</style>
