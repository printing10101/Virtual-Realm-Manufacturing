<template>
  <div class="process-planning-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="page-header__title">
        <h1>{{ t('processPlanning.routePage.pageTitle') }}</h1>
        <p>{{ t('processPlanning.routePage.pageSubtitle') }}</p>
      </div>
      <div class="page-header__actions">
        <el-button
          type="primary"
          size="small"
          @click="handleCreate"
        >
          <el-icon :size="16">
            <Plus />
          </el-icon>
          {{ t('processPlanning.routePage.btnNewRoute') }}
        </el-button>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-input
        v-model="searchKeyword"
        :placeholder="t('processPlanning.routePage.searchPlaceholder')"
        clearable
        size="small"
        class="filter-search"
        :prefix-icon="Search"
      />
      <el-select
        v-model="filterType"
        :placeholder="t('processPlanning.routePage.filterTypePlaceholder')"
        size="small"
        class="filter-select"
      >
        <el-option
          :label="t('processPlanning.routePage.typeAll')"
          value="all"
        />
        <el-option
          :label="t('processPlanning.routePage.typeMachining')"
          value="machining"
        />
        <el-option
          :label="t('processPlanning.routePage.typeAssembly')"
          value="assembly"
        />
        <el-option
          :label="t('processPlanning.routePage.typeWelding')"
          value="welding"
        />
        <el-option
          :label="t('processPlanning.routePage.typeHeatTreatment')"
          value="heattreatment"
        />
      </el-select>
      <el-select
        v-model="filterStatus"
        :placeholder="t('processPlanning.routePage.filterStatusPlaceholder')"
        size="small"
        class="filter-select"
      >
        <el-option
          :label="t('processPlanning.routePage.statusAll')"
          value="all"
        />
        <el-option
          :label="t('processPlanning.routePage.statusPublished')"
          value="published"
        />
        <el-option
          :label="t('processPlanning.routePage.statusDraft')"
          value="draft"
        />
        <el-option
          :label="t('processPlanning.routePage.statusArchived')"
          value="archived"
        />
      </el-select>
    </div>

    <!-- 工艺路线卡片列表 -->
    <div
      v-if="loading"
      class="loading-state"
    >
      <el-icon
        class="loading-icon"
        :size="32"
      >
        <Clock />
      </el-icon>
      <span>{{ t('processPlanning.routePage.loading') }}</span>
    </div>
    <div
      v-else-if="loadError"
      class="empty-state"
    >
      <span>{{ t('processPlanning.routePage.loadFailed') }}</span>
      <el-button
        type="primary"
        text
        size="small"
        @click="fetchRoutes"
      >
        {{ t('processPlanning.routePage.btnReload') }}
      </el-button>
    </div>
    <div
      v-else-if="filteredRoutes.length === 0"
      class="empty-state"
    >
      <span>{{ t('processPlanning.routePage.emptyData') }}</span>
    </div>
    <div
      v-else
      class="card-grid"
    >
      <div
        v-for="route in filteredRoutes"
        :key="route.id"
        class="route-card"
        @click="openDetail(route)"
      >
        <div class="card-header">
          <span class="card-title">{{ route.name }}</span>
          <el-tag
            :type="statusTagType(route.status)"
            size="small"
            effect="light"
            class="status-tag"
          >
            {{ route.status }}
          </el-tag>
        </div>
        <p class="card-description">
          {{ route.description }}
        </p>
        <div class="card-meta">
          <span class="meta-item">
            <el-icon :size="14"><Operation /></el-icon>
            {{ route.steps?.length || 0 }}{{ t('processPlanning.routePage.stepCountSuffix') }}
          </span>
          <span class="meta-item">
            <el-icon :size="14"><Document /></el-icon>
            {{ route.version }}
          </span>
          <span class="meta-item">
            <el-icon :size="14"><Clock /></el-icon>
            {{ route.updated_at?.split('T')[0] || '-' }}
          </span>
        </div>
        <div
          class="card-actions"
          @click.stop
        >
          <el-button
            text
            type="primary"
            size="small"
            @click.stop="handleView(route)"
          >
            {{ t('processPlanning.routePage.btnView') }}
          </el-button>
          <el-button
            text
            type="primary"
            size="small"
            @click.stop="handleEdit(route)"
          >
            {{ t('processPlanning.routePage.btnEdit') }}
          </el-button>
          <el-button
            text
            type="primary"
            size="small"
            @click.stop="handleCopy(route)"
          >
            {{ t('processPlanning.routePage.btnCopy') }}
          </el-button>
          <el-button
            text
            type="danger"
            size="small"
            @click.stop="handleDelete(route)"
          >
            {{ t('processPlanning.routePage.btnDelete') }}
          </el-button>
        </div>
      </div>
    </div>

    <!-- 详情侧滑面板 -->
    <transition name="slide-panel">
      <div
        v-if="selectedRoute"
        class="detail-overlay"
        @click.self="closeDetail"
      >
        <div class="detail-panel">
          <div class="detail-header">
            <h3 class="detail-title">
              {{ selectedRoute.name }}
            </h3>
            <el-button
              text
              circle
              @click="closeDetail"
            >
              <el-icon :size="18">
                <Close />
              </el-icon>
            </el-button>
          </div>

          <div class="detail-status-row">
            <el-tag
              :type="statusTagType(selectedRoute.status)"
              size="small"
              effect="light"
            >
              {{ selectedRoute.status }}
            </el-tag>
            <span class="detail-version">{{ selectedRoute.version }}</span>
          </div>

          <p class="detail-description">
            {{ selectedRoute.description }}
          </p>

          <div class="detail-section-label">
            {{ t('processPlanning.routePage.stepListLabel') }}
          </div>
          <div class="step-list">
            <div
              v-for="(step, index) in selectedRoute.steps"
              :key="step.name + (step.tool_id ?? '') + index"
              class="step-item"
            >
              <div class="step-number">
                {{ index + 1 }}
              </div>
              <div class="step-content">
                <div class="step-name">
                  {{ step.name }}
                </div>
                <div class="step-duration">
                  {{ step.duration }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'
import {
  Plus,
  Search,
  Operation,
  Document,
  Clock,
  Close,
} from '@element-plus/icons-vue'
import http from '@/utils/http'
import { API_CONFIG } from '@/config/api'

const { t } = useI18n()

// ========================= 类型定义 =========================
interface ProcessStep {
  name: string
  description: string
  duration: string
  tool_id?: number
  parameters?: Record<string, unknown>
}

interface ProcessRoute {
  id: number
  name: string
  description: string
  status: string
  version: string
  material_type: string
  steps: ProcessStep[]
  created_at: string
  updated_at: string
}

// ========================= 数据 =========================
const routeList = ref<ProcessRoute[]>([])
const loading = ref(false)
const loadError = ref(false)

// 状态到中文的映射（用于筛选下拉框与后端 status 中文值之间的桥接）
const statusValueMap: Record<string, string> = {
  [t('processPlanning.routePage.statusPublished')]: 'published',
  [t('processPlanning.routePage.statusDraft')]: 'draft',
  [t('processPlanning.routePage.statusArchived')]: 'archived',
}

/** 从后端中文 status 反推英文值，供前端筛选逻辑使用 */
function statusToEnglish(cn: string): string {
  return statusValueMap[cn] || ''
}

// ========================= API 数据加载 =========================
async function fetchRoutes() {
  loading.value = true
  loadError.value = false
  try {
    const params: Record<string, string> = {}
    if (filterStatus.value !== 'all') {
      params.status = filterStatus.value
    }
    if (searchKeyword.value.trim()) {
      params.keyword = searchKeyword.value.trim()
    }
    const res = await http.get(API_CONFIG.PROCESS_ROUTES, { params })
    routeList.value = res.data.data || []
  } catch {
    loadError.value = true
    routeList.value = []
  } finally {
    loading.value = false
  }
}

// ========================= 筛选状态 =========================
const searchKeyword = ref('')
const filterType = ref('all')
const filterStatus = ref('all')

// ========================= 详情面板 =========================
const selectedRoute = ref<ProcessRoute | null>(null)

// ========================= 计算属性 =========================
const filteredRoutes = computed(() => {
  return routeList.value.filter(route => {
    const keyword = searchKeyword.value.trim().toLowerCase()
    if (keyword && !route.name.toLowerCase().includes(keyword) && !route.description.toLowerCase().includes(keyword)) {
      return false
    }
    if (filterType.value !== 'all' && route.material_type !== filterType.value) {
      return false
    }
    if (filterStatus.value !== 'all' && statusToEnglish(route.status) !== filterStatus.value) {
      return false
    }
    return true
  })
})

// ========================= 方法 =========================
function statusTagType(status: string): 'success' | 'warning' | 'info' {
  switch (status) {
    case t('processPlanning.routePage.statusPublished'):
    case 'published':
      return 'success'
    case t('processPlanning.routePage.statusDraft'):
    case 'draft':
      return 'warning'
    case t('processPlanning.routePage.statusArchived'):
    case 'archived':
      return 'info'
    default:
      return 'info'
  }
}

function openDetail(route: ProcessRoute) {
  selectedRoute.value = route
}

function closeDetail() {
  selectedRoute.value = null
}

async function handleCreate() {
  try {
    const res = await http.post(API_CONFIG.PROCESS_ROUTES, {
      name: t('processPlanning.routePage.defaultRouteName'),
      description: '',
      status: t('processPlanning.routePage.statusDraft'),
      steps: [],
    })
    const newRoute = res.data.data as ProcessRoute
    routeList.value.unshift(newRoute)
    ElMessage.success(t('processPlanning.routePage.msgCreateSuccess'))
  } catch {
    // http 拦截器已处理错误提示
  }
}

function handleView(route: ProcessRoute) {
  openDetail(route)
}

async function handleEdit(route: ProcessRoute) {
  try {
    const res = await http.put(`${API_CONFIG.PROCESS_ROUTES}/${route.id}`, {
      ...route,
    })
    const updated = res.data.data as ProcessRoute
    const idx = routeList.value.findIndex(r => r.id === route.id)
    if (idx !== -1) routeList.value[idx] = updated
    if (selectedRoute.value?.id === route.id) selectedRoute.value = updated
    ElMessage.success(t('processPlanning.routePage.msgUpdateSuccess', { name: route.name }))
  } catch {
    // http 拦截器已处理错误提示
  }
}

async function handleCopy(route: ProcessRoute) {
  try {
    const res = await http.post(API_CONFIG.PROCESS_ROUTES, {
      name: `${route.name}${t('processPlanning.routePage.copySuffix')}`,
      description: route.description,
      status: t('processPlanning.routePage.statusDraft'),
      version: route.version,
      material_type: route.material_type,
      steps: route.steps,
    })
    const copied = res.data.data as ProcessRoute
    routeList.value.unshift(copied)
    ElMessage.success(t('processPlanning.routePage.msgCopySuccess', { name: route.name }))
  } catch {
    // http 拦截器已处理错误提示
  }
}

function handleDelete(route: ProcessRoute) {
  ElMessageBox.confirm(
    t('processPlanning.routePage.msgDeleteConfirm', { name: route.name }),
    t('processPlanning.routePage.deleteConfirmTitle'),
    {
      confirmButtonText: t('processPlanning.routePage.btnConfirmDelete'),
      cancelButtonText: t('common.cancel'),
      type: 'warning',
    },
  ).then(async () => {
    try {
      await http.delete(`${API_CONFIG.PROCESS_ROUTES}/${route.id}`)
      routeList.value = routeList.value.filter(r => r.id !== route.id)
      if (selectedRoute.value?.id === route.id) {
        closeDetail()
      }
      ElMessage.success(t('processPlanning.routePage.msgDeleteSuccess', { name: route.name }))
    } catch {
      // http 拦截器已处理错误提示
    }
  }).catch(() => {
    // 用户取消
  })
}

// ========================= 生命周期 =========================
onMounted(() => {
  fetchRoutes()
})
</script>

<style scoped>
.process-planning-page {
  padding: var(--page-padding);
  max-width: var(--content-max-width);
  margin: 0 auto;
}

/* 筛选栏内控件宽度 */
.filter-search {
  width: 280px;
}

.filter-select {
  width: 160px;
}

/* 卡片网格 */
.card-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

/* 路线卡片 */
.route-card {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  padding: 20px;
  cursor: pointer;
  box-shadow: var(--shadow-sm);
  transition: box-shadow var(--transition-normal), border-color var(--transition-normal), transform var(--transition-fast);
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.route-card:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--border-medium);
  transform: translateY(-2px);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.4;
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.status-tag {
  flex-shrink: 0;
}

.card-description {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-tertiary);
  white-space: nowrap;
}

.card-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  padding-top: 12px;
  border-top: 1px solid var(--border-light);
}

/* 侧滑详情面板 */
.detail-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1000;
  background: var(--bg-overlay-light);
  display: flex;
  justify-content: flex-end;
}

.detail-panel {
  width: 400px;
  max-width: 90vw;
  height: 100%;
  background: var(--bg-primary);
  box-shadow: var(--shadow-xl);
  padding: 28px 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.detail-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-right: 8px;
}

.detail-status-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.detail-version {
  font-size: 13px;
  color: var(--text-tertiary);
  font-weight: 500;
}

.detail-description {
  margin: 0;
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.7;
}

.detail-section-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-accent);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-top: 8px;
}

.step-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.step-item {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 14px 0;
  border-bottom: 1px solid var(--border-light);
}

.step-item:last-child {
  border-bottom: none;
}

.step-number {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--accent-light);
  color: var(--accent-primary);
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.step-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.step-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.step-duration {
  font-size: 12px;
  color: var(--text-tertiary);
}

/* 侧滑动画 */
.slide-panel-enter-active,
.slide-panel-leave-active {
  transition: opacity var(--transition-normal);
}

.slide-panel-enter-active .detail-panel,
.slide-panel-leave-active .detail-panel {
  transition: transform var(--transition-normal);
}

.slide-panel-enter-from,
.slide-panel-leave-to {
  opacity: 0;
}

.slide-panel-enter-from .detail-panel,
.slide-panel-leave-to .detail-panel {
  transform: translateX(100%);
}

/* 加载与空状态 */
.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 60px 20px;
  color: var(--text-tertiary);
  font-size: 14px;
}

.loading-icon {
  animation: spin 1.2s linear infinite;
  color: var(--accent-primary);
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 响应式 */
@media (max-width: 900px) {
  .card-grid {
    grid-template-columns: 1fr;
  }

  .filter-search {
    width: 100%;
  }

  .filter-select {
    flex: 1;
    min-width: 120px;
  }
}

@media (max-width: 600px) {
  .process-planning-page {
    padding: 16px;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .filter-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-search,
  .filter-select {
    width: 100%;
  }
}
</style>
