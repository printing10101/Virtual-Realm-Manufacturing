<template>
  <div class="quality-inspection-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="page-header__title">
        <h1 class="page-title">
          {{ t('qualityInspection.pageTitle') }}
        </h1>
        <p class="page-subtitle">
          {{ t('qualityInspection.pageSubtitle') }}
        </p>
      </div>
      <div class="page-header__actions">
        <el-button
          type="primary"
          size="small"
          :icon="Plus"
          @click="handleNewInspection"
        >
          {{ t('qualityInspection.btnNewInspection') }}
        </el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-row">
      <div
        v-for="stat in statsCards"
        :key="stat.label"
        class="stat-card"
        :class="'stat-card--' + stat.type"
      >
        <div class="stat-card__icon">
          <el-icon :size="24">
            <component :is="stat.icon" />
          </el-icon>
        </div>
        <div class="stat-card__content">
          <span class="stat-card__value">{{ stat.value }}</span>
          <span class="stat-card__label">{{ stat.label }}</span>
        </div>
      </div>
    </div>

    <!-- 检测记录 -->
    <div class="content-card">
      <div class="content-card__header">
        <span class="content-card__title">{{ t('qualityInspection.recordsTitle') }}</span>
        <div style="display: flex; gap: 8px;">
          <el-select
            v-model="resultFilter"
            :placeholder="t('qualityInspection.filterResult')"
            size="small"
            style="width: 130px"
          >
            <el-option
              :label="t('qualityInspection.filterAll')"
              value="all"
            />
            <el-option
              :label="t('qualityInspection.filterPass')"
              value="pass"
            />
            <el-option
              :label="t('qualityInspection.filterFail')"
              value="fail"
            />
          </el-select>
          <el-input
            v-model="searchKeyword"
            :placeholder="t('qualityInspection.searchPlaceholder')"
            clearable
            size="small"
            style="width: 180px"
          />
        </div>
      </div>
      <div class="content-card__body">
        <el-table
          v-loading="loading"
          :data="records"
          style="width: 100%"
          stripe
          :empty-text="loadError ? t('qualityInspection.emptyLoadFailed') : t('qualityInspection.emptyRecords')"
        >
          <el-table-column
            prop="id"
            :label="t('qualityInspection.colId')"
            width="120"
          />
          <el-table-column
            prop="product_name"
            :label="t('qualityInspection.colProductName')"
            min-width="180"
          />
          <el-table-column
            prop="batch"
            :label="t('qualityInspection.colBatch')"
            width="140"
          />
          <el-table-column
            :label="t('qualityInspection.colResult')"
            width="100"
          >
            <template #default="{ row }">
              <el-tag
                :type="resultTagType(row.result)"
                size="small"
                effect="light"
              >
                {{ row.result }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            prop="inspector"
            :label="t('qualityInspection.colInspector')"
            width="100"
          />
          <el-table-column
            prop="created_at"
            :label="t('qualityInspection.colTime')"
            width="170"
          />
          <el-table-column
            :label="t('qualityInspection.colAction')"
            width="100"
            fixed="right"
          >
            <template #default="{ row }">
              <el-button
                type="primary"
                text
                size="small"
                @click="handleViewDetail(row as InspectionRecord)"
              >
                {{ t('qualityInspection.btnView') }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, type Component } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Checked, DataLine, WarningFilled } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import http from '@/utils/http'
import { API_CONFIG } from '@/config/api'

const { t } = useI18n()

// ========================= 类型定义 =========================
interface InspectionRecord {
  id: string | number
  product_name: string
  batch: string
  result: string
  inspector: string
  created_at: string
  remark?: string
  updated_at?: string
}

interface StatsCard {
  label: string
  value: string | number
  icon: Component
  type: string
}

// ========================= 状态 =========================
const loading = ref(false)
const loadError = ref(false)
const searchKeyword = ref('')
const resultFilter = ref('all')

const records = ref<InspectionRecord[]>([])
const statsData = ref({ total: 0, pass: 0, fail: 0, pass_rate: 0 })

// ========================= 计算属性 =========================
const statsCards = computed<StatsCard[]>(() => {
  return [
    { label: t('qualityInspection.statToday'), value: statsData.value.total, icon: Checked, type: 'default' },
    { label: t('qualityInspection.statPassRate'), value: statsData.value.pass_rate + '%', icon: DataLine, type: 'success' },
    { label: t('qualityInspection.statAbnormal'), value: statsData.value.fail, icon: WarningFilled, type: 'danger' },
  ]
})

// ========================= 方法 =========================
function resultTagType(result: string): 'success' | 'danger' | 'warning' {
  const map: Record<string, 'success' | 'danger' | 'warning'> = {
    [t('qualityInspection.filterPass')]: 'success',
    [t('qualityInspection.filterFail')]: 'danger',
  }
  return map[result] || 'info'
}

async function fetchStats() {
  try {
    const res = await http.get(API_CONFIG.QUALITY + '/stats/summary')
    if (res.data.code === 0 && res.data.data) {
      statsData.value = res.data.data
    }
  } catch (e: unknown) {
    // 统计加载失败不影响记录列表，但需记录便于排查
    console.warn('[QualityInspection] fetchStats failed:', e)
  }
}

async function fetchRecords() {
  loading.value = true
  loadError.value = false
  try {
    const params: Record<string, string> = {}
    if (resultFilter.value !== 'all') {
      params.result = resultFilter.value === 'pass' ? t('qualityInspection.filterPass') : t('qualityInspection.filterFail')
    }
    if (searchKeyword.value.trim()) {
      params.keyword = searchKeyword.value.trim()
    }
    const res = await http.get(API_CONFIG.QUALITY + '/inspections', { params })
    if (res.data.code === 0 && res.data.data) {
      records.value = res.data.data
    } else {
      records.value = []
      loadError.value = true
    }
  } catch {
    records.value = []
    loadError.value = true
  } finally {
    loading.value = false
  }
}

function handleNewInspection() {
  ElMessage.success(t('qualityInspection.msgNewInspectionWip'))
}

function handleViewDetail(row: InspectionRecord) {
  ElMessage.info(t('qualityInspection.msgViewDetail', { id: row.id }))
}

// ========================= 防抖处理 =========================
let debounceTimer: ReturnType<typeof setTimeout> | null = null
function debouncedFetchRecords() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    fetchRecords()
  }, 300)
}

// ========================= 生命周期 =========================
onMounted(() => {
  fetchRecords()
  fetchStats()
})

onUnmounted(() => {
  // 清理防抖定时器，避免组件卸载后定时器仍触发状态更新
  if (debounceTimer) {
    clearTimeout(debounceTimer)
    debounceTimer = null
  }
})

// 筛选/搜索变化时防抖请求
watch([resultFilter, searchKeyword], () => {
  debouncedFetchRecords()
})
</script>

<style scoped>
.quality-inspection-page {
  padding: var(--page-padding);
  max-width: var(--content-max-width);
  margin: 0 auto;
}

/* 统计卡片图标颜色 */
.stat-card--success .stat-card__icon {
  background: var(--success-bg);
  color: var(--success);
}

.stat-card--warning .stat-card__icon {
  background: var(--warning-bg);
  color: var(--warning);
}

.stat-card--danger .stat-card__icon {
  background: var(--error-bg);
  color: var(--error);
}
</style>
