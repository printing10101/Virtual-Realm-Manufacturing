<template>
  <div class="settings-page">
    <div class="page-header">
      <div class="page-header__title">
        <h1>{{ t('settings.pageTitle') }}</h1>
        <p class="subtitle">
          {{ t('settings.subtitle') }}
        </p>
      </div>
    </div>

    <div class="settings-layout">
      <div class="settings-nav">
        <div
          v-for="tab in tabs"
          :key="tab.key"
          class="settings-nav__item"
          :class="{ 'settings-nav__item--active': activeTab === tab.key }"
          @click="activeTab = tab.key"
        >
          <el-icon class="settings-nav__icon">
            <component :is="tab.icon" />
          </el-icon>
          <span class="settings-nav__label">{{ tab.label }}</span>
        </div>
      </div>
      <div class="settings-content">
        <KeepAlive>
          <component :is="currentComponent" />
        </KeepAlive>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, type Component } from 'vue'
import { useI18n } from 'vue-i18n'
import { Setting, Cpu, Document, Connection, Service } from '@element-plus/icons-vue'
import GeneralSettings from '@/components/settings/GeneralSettings.vue'
import AISettings from '@/components/settings/AISettings.vue'
import ProcessSettings from '@/components/settings/ProcessSettings.vue'
import UISettings from '@/components/settings/UISettings.vue'
import LLMEngineSettings from '@/components/settings/LLMEngineSettings.vue'

const { t } = useI18n()
const activeTab = ref('general')

const componentMap: Record<string, Component> = {
  general: GeneralSettings,
  ai: AISettings,
  engine: LLMEngineSettings,
  process: ProcessSettings,
  ui: UISettings,
}

const currentComponent = computed(() => componentMap[activeTab.value] || GeneralSettings)

const tabs = [
  { key: 'general', label: t('settings.navGeneral'), icon: Setting },
  { key: 'ai', label: t('settings.navAiMonitor'), icon: Cpu },
  { key: 'engine', label: t('settings.navAiEngine'), icon: Service },
  { key: 'process', label: t('settings.navLogAudit'), icon: Document },
  { key: 'ui', label: t('settings.navAdvanced'), icon: Connection },
]
</script>

<style scoped>
.settings-page {
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding: var(--page-padding);
}

.settings-layout {
  display: flex;
  gap: 24px;
  align-items: flex-start;
}

.settings-nav {
  width: 200px;
  flex-shrink: 0;
  background: var(--bg-0);
  border: 1px solid var(--bg-200);
  border-radius: var(--radius-lg);
  padding: 8px;
  position: sticky;
  top: 24px;
}

.settings-nav__item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.2s ease;
  color: var(--text-secondary);
  font-size: 14px;
  margin-bottom: 2px;
}

.settings-nav__item:hover {
  background: var(--bg-50);
  color: var(--text-primary);
}

.settings-nav__item--active {
  background: var(--brand-50, rgba(99, 102, 241, 0.08));
  color: var(--brand-600, var(--brand-500));
  font-weight: 600;
}

.settings-nav__icon {
  font-size: 18px;
  flex-shrink: 0;
}

.settings-nav__label {
  white-space: nowrap;
}

.settings-content {
  flex: 1;
  min-width: 0;
}

/* Deep overrides for child components */
.settings-content :deep(.el-button) {
  border-radius: var(--radius-md);
}

.settings-content :deep(.el-switch) {
  --el-switch-on-color: var(--brand-500);
}

.settings-content :deep(.el-form-item__label) {
  color: var(--text-secondary);
  font-weight: 500;
}

.settings-content :deep(.el-descriptions__label) {
  color: var(--text-secondary);
  font-weight: 500;
}

.settings-content :deep(.el-descriptions__content) {
  color: var(--text-primary);
}

.settings-content :deep(.el-table) {
  --el-table-border-color: var(--bg-100);
  --el-table-header-bg-color: var(--bg-50);
  --el-table-header-text-color: var(--text-secondary);
  --el-table-text-color: var(--text-primary);
  --el-table-row-hover-bg-color: var(--bg-50);
}

.settings-content :deep(.el-dialog) {
  border-radius: var(--radius-lg);
}

.settings-content :deep(.el-pagination) {
  --el-pagination-button-bg-color: var(--bg-0);
}

.settings-content :deep(.el-alert) {
  border-radius: var(--radius-md);
}

.settings-content :deep(.el-progress-bar__outer) {
  background-color: var(--bg-100);
}
</style>
