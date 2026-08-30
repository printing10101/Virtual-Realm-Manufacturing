<template>
  <div class="cutting-experience-dashboard">
    <!-- Page Header -->
    <div class="page-header">
      <div class="page-header__title">
        <h1>{{ t('experience.pageTitle') }}</h1>
        <span class="page-header__subtitle">{{ t('experience.pageSubtitle') }}</span>
      </div>
      <div class="page-header__actions">
        <el-button @click="handleRefresh">
          {{ t('experience.btn.refresh') }}
        </el-button>
      </div>
    </div>

    <!-- Error Banner -->
    <el-alert
      v-if="store.hasError"
      :title="store.error"
      type="error"
      show-icon
      :closable="true"
      class="error-banner"
      @close="store.clearError"
    />

    <!-- Stats Cards -->
    <div class="stats-grid">
      <el-statistic :title="t('experience.stats.totalRecords')" :value="store.total">
        <template #suffix>{{ t('experience.unit.records') }}</template>
      </el-statistic>
      <el-statistic 
        :title="t('experience.stats.avgCycleTime')" 
        :value="store.stats?.avg_cycle_time_s || 0"
      >
        <template #suffix>{{ t('experience.unit.seconds') }}</template>
      </el-statistic>
      <el-statistic :title="t('experience.stats.okRate')" :value="store.stats?.ok_rate || 0">
        <template #suffix>%</template>
      </el-statistic>
      <el-statistic :title="t('experience.stats.anomalyRate')" :value="store.stats?.anomaly_rate || 0">
        <template #suffix>%</template>
      </el-statistic>
    </div>

    <!-- Data List Placeholder -->
    <div class="data-list-placeholder">
      <el-empty :description="t('experience.list.empty')" />
    </div>
  </div>
</template>

<script>
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCuttingExperienceStore } from '@/stores/cutting-experience'

export default {
  name: 'CuttingExperienceDashboard',
  setup() {
    const { t } = useI18n()
    const store = useCuttingExperienceStore()

    function handleRefresh() {
      store.fetchStats()
      store.queryExperiences(1)
    }

    return {
      t,
      store,
      handleRefresh,
    }
  },
}
</script>

<style scoped>
.cutting-experience-dashboard {
  padding: 16px 24px;
  height: 100%;
  overflow-y: auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.page-header__title h1 {
  margin: 0 0 4px 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.page-header__subtitle {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.page-header__actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.error-banner {
  margin-bottom: 16px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

.data-list-placeholder {
  min-height: 300px;
}
</style>
