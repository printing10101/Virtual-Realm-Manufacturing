<template>
  <div class="material-management-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="page-header__title">
        <h1 class="page-title">
          {{ t('materialManagement.pageTitle') }}
        </h1>
        <p class="page-subtitle">
          {{ t('materialManagement.pageSubtitle') }}
        </p>
      </div>
      <div class="page-header__actions">
        <el-button
          type="primary"
          size="small"
          :icon="Plus"
          @click="handleStockIn"
        >
          {{ t('materialManagement.btnStockIn') }}
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

    <!-- 物料列表 -->
    <div class="content-card">
      <div class="content-card__header">
        <span class="content-card__title">{{ t('materialManagement.sectionMaterialList') }}</span>
        <div style="display: flex; gap: 8px;">
          <el-select
            v-model="statusFilter"
            :placeholder="t('materialManagement.placeholderStatus')"
            size="small"
            style="width: 130px"
            @change="fetchMaterials"
          >
            <el-option
              :label="t('materialManagement.labelStatusAll')"
              value="all"
            />
            <el-option
              :label="t('materialManagement.labelStatusNormal')"
              :value="t('materialManagement.labelStatusNormal')"
            />
            <el-option
              :label="t('materialManagement.labelStatusLow')"
              :value="t('materialManagement.labelStatusLow')"
            />
            <el-option
              :label="t('materialManagement.labelStatusOut')"
              :value="t('materialManagement.labelStatusOut')"
            />
          </el-select>
          <el-select
            v-model="categoryFilter"
            :placeholder="t('materialManagement.placeholderCategory')"
            size="small"
            style="width: 130px"
            @change="fetchMaterials"
          >
            <el-option
              :label="t('materialManagement.labelCategoryAll')"
              value="all"
            />
            <el-option
              :label="t('materialManagement.labelCategoryRaw')"
              :value="t('materialManagement.labelCategoryRaw')"
            />
            <el-option
              :label="t('materialManagement.labelCategorySemi')"
              :value="t('materialManagement.labelCategorySemi')"
            />
            <el-option
              :label="t('materialManagement.labelCategoryFinished')"
              :value="t('materialManagement.labelCategoryFinished')"
            />
          </el-select>
          <el-input
            v-model="searchKeyword"
            :placeholder="t('materialManagement.placeholderSearch')"
            clearable
            size="small"
            style="width: 180px"
            @clear="fetchMaterials"
            @keyup.enter="fetchMaterials"
          />
        </div>
      </div>
      <div class="content-card__body">
        <el-table
          v-loading="loading"
          :data="materials"
          style="width: 100%"
          stripe
          :empty-text="loadError ? t('materialManagement.emptyTextError') : t('materialManagement.emptyText')"
        >
          <el-table-column
            prop="code"
            :label="t('materialManagement.colMaterialCode')"
            width="120"
          />
          <el-table-column
            prop="name"
            :label="t('materialManagement.colMaterialName')"
            min-width="180"
          />
          <el-table-column
            :label="t('materialManagement.colCategory')"
            width="100"
          >
            <template #default="{ row }">
              <span class="category-text">{{ row.category }}</span>
            </template>
          </el-table-column>
          <el-table-column
            prop="quantity"
            :label="t('materialManagement.colQuantity')"
            width="110"
          >
            <template #default="{ row }">
              <span :class="{ 'text-danger': row.status === t('materialManagement.labelStatusOut'), 'text-warning': row.status === t('materialManagement.labelStatusLow') }">
                {{ row.quantity }}
              </span>
            </template>
          </el-table-column>
          <el-table-column
            prop="safe_quantity"
            :label="t('materialManagement.colSafeQuantity')"
            width="110"
          />
          <el-table-column
            :label="t('materialManagement.colStatus')"
            width="100"
          >
            <template #default="{ row }">
              <el-tag
                :type="stockStatusTagType(row.status)"
                size="small"
                effect="light"
              >
                {{ row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            :label="t('materialManagement.colActions')"
            width="180"
            fixed="right"
          >
            <template #default="{ row }">
              <el-button
                type="primary"
                text
                size="small"
                @click="handleViewDetail(row as Material)"
              >
                {{ t('materialManagement.btnDetail') }}
              </el-button>
              <el-button
                type="primary"
                text
                size="small"
                @click="handleStockIn(row as Material)"
              >
                {{ t('materialManagement.btnStockInRow') }}
              </el-button>
              <el-button
                v-if="row.status === t('materialManagement.labelStatusOut')"
                type="warning"
                text
                size="small"
                @click="handlePurchase(row as Material)"
              >
                {{ t('materialManagement.btnPurchase') }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- 入库登记弹窗 -->
    <el-dialog
      v-model="stockInDialogVisible"
      :title="t('materialManagement.dialogStockInTitle')"
      width="460px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form label-width="90px" @submit.prevent>
        <el-form-item :label="t('materialManagement.fieldMaterial')" required>
          <el-select
            v-model="stockInForm.material_id"
            :placeholder="t('materialManagement.placeholderSelectMaterial')"
            style="width: 100%"
            filterable
          >
            <el-option
              v-for="m in materials"
              :key="m.id"
              :label="`${m.code} - ${m.name}`"
              :value="m.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('materialManagement.fieldQuantity')" required>
          <el-input-number
            v-model="stockInForm.quantity"
            :min="1"
            :max="100000"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item :label="t('materialManagement.fieldRemark')">
          <el-input
            v-model="stockInForm.remark"
            :placeholder="t('materialManagement.placeholderRemark')"
            maxlength="200"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="stockInDialogVisible = false">
          {{ t('materialManagement.btnCancel') }}
        </el-button>
        <el-button type="primary" :loading="stockInSubmitting" @click="submitStockIn">
          {{ t('materialManagement.btnSubmit') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 采购申请弹窗 -->
    <el-dialog
      v-model="purchaseDialogVisible"
      :title="t('materialManagement.dialogPurchaseTitle')"
      width="460px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form label-width="90px" @submit.prevent>
        <el-form-item :label="t('materialManagement.fieldMaterial')" required>
          <el-input :model-value="purchaseMaterialLabel" disabled />
        </el-form-item>
        <el-form-item :label="t('materialManagement.fieldQuantity')" required>
          <el-input-number
            v-model="purchaseForm.quantity"
            :min="1"
            :max="100000"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item :label="t('materialManagement.fieldSupplier')">
          <el-input
            v-model="purchaseForm.supplier"
            :placeholder="t('materialManagement.placeholderSupplier')"
            maxlength="128"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="purchaseDialogVisible = false">
          {{ t('materialManagement.btnCancel') }}
        </el-button>
        <el-button type="primary" :loading="purchaseSubmitting" @click="submitPurchase">
          {{ t('materialManagement.btnSubmit') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 物料详情弹窗 -->
    <el-dialog
      v-model="detailDialogVisible"
      :title="t('materialManagement.dialogDetailTitle')"
      width="520px"
    >
      <div v-loading="detailLoading" style="min-height: 200px">
        <template v-if="detailData">
          <el-descriptions :column="1" border>
            <el-descriptions-item :label="t('materialManagement.colMaterialCode')">
              {{ detailData.code }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('materialManagement.colMaterialName')">
              {{ detailData.name }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('materialManagement.fieldSpec')">
              {{ detailData.spec || '—' }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('materialManagement.colCategory')">
              {{ detailData.category }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('materialManagement.colQuantity')">
              {{ detailData.quantity }} {{ detailData.unit || '' }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('materialManagement.fieldSafeQuantity')">
              {{ detailData.safe_quantity }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('materialManagement.colStatus')">
              <el-tag :type="stockStatusTagType(detailData.status)" size="small" effect="light">
                {{ detailData.status }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item :label="t('materialManagement.fieldLocation')">
              {{ detailData.location || '—' }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('materialManagement.fieldSupplier')">
              {{ detailData.supplier || '—' }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('materialManagement.fieldUpdatedAt')">
              {{ detailData.updated_at }}
            </el-descriptions-item>
          </el-descriptions>
        </template>
      </div>
      <template #footer>
        <el-button @click="detailDialogVisible = false">
          {{ t('materialManagement.btnCancel') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, type Component } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Plus, Box, Warning, CircleClose, ShoppingCart } from '@element-plus/icons-vue'
import http from '@/utils/http'
import { API_CONFIG } from '@/config/api'

const { t } = useI18n()

// ========================= 类型定义 =========================
interface Material {
  id: number
  code: string
  name: string
  spec: string
  category: string
  quantity: number
  safe_quantity: number
  status: string
  location: string
  unit: string
  supplier: string
  created_at: string
  updated_at: string
}

interface StatsSummary {
  total: number
  low_stock: number
  out_of_stock: number
}

interface StatsCard {
  label: string
  value: number
  icon: Component
  type: string
}

// ========================= 状态 =========================
const loading = ref(false)
const loadError = ref(false)
const searchKeyword = ref('')
const statusFilter = ref('all')
const categoryFilter = ref('all')

const materials = ref<Material[]>([])
const statsSummary = ref<StatsSummary>({ total: 0, low_stock: 0, out_of_stock: 0 })

// ========================= 计算属性 =========================
const statsCards = computed<StatsCard[]>(() => {
  return [
    { label: t('materialManagement.statTotal'), value: statsSummary.value.total, icon: Box, type: 'default' },
    { label: t('materialManagement.statLowStock'), value: statsSummary.value.low_stock, icon: Warning, type: 'warning' },
    { label: t('materialManagement.statOutOfStock'), value: statsSummary.value.out_of_stock, icon: CircleClose, type: 'danger' },
    { label: t('materialManagement.statPurchasing'), value: Math.min(statsSummary.value.out_of_stock + statsSummary.value.low_stock, 8), icon: ShoppingCart, type: 'info' },
  ]
})

// ========================= 方法 =========================
function stockStatusTagType(status: string): 'success' | 'warning' | 'danger' {
  const map: Record<string, 'success' | 'warning' | 'danger'> = {
    [t('materialManagement.labelStatusNormal')]: 'success',
    [t('materialManagement.labelStatusLow')]: 'warning',
    [t('materialManagement.labelStatusOut')]: 'danger',
  }
  return map[status] || 'info'
}

async function fetchMaterials() {
  loading.value = true
  loadError.value = false
  try {
    const params: Record<string, string> = {}
    if (statusFilter.value !== 'all') params.status = statusFilter.value
    if (categoryFilter.value !== 'all') params.category = categoryFilter.value
    const keyword = searchKeyword.value.trim()
    if (keyword) params.keyword = keyword

    const [materialsRes, statsRes] = await Promise.all([
      http.get(API_CONFIG.MATERIALS + '/', { params }),
      http.get(API_CONFIG.MATERIALS + '/stats/summary'),
    ])

    // 后端列表返回 { items, total, page, page_size, total_pages }
    materials.value = materialsRes.data?.data?.items || []
    statsSummary.value = statsRes.data?.data || { total: 0, low_stock: 0, out_of_stock: 0 }
  } catch {
    loadError.value = true
    materials.value = []
    statsSummary.value = { total: 0, low_stock: 0, out_of_stock: 0 }
  } finally {
    loading.value = false
  }
}

// ========================= 入库登记弹窗 =========================
const stockInDialogVisible = ref(false)
const stockInSubmitting = ref(false)
const stockInForm = ref({
  material_id: '' as number | '',
  quantity: 1 as number,
  remark: '',
})

/** 打开入库登记弹窗（顶部按钮不传物料，行内按钮预选物料）。 */
function handleStockIn(row?: Material | MouseEvent) {
  if (row && typeof row === 'object' && 'id' in row) {
    stockInForm.value = { material_id: row.id, quantity: 1, remark: '' }
  } else {
    stockInForm.value = { material_id: '', quantity: 1, remark: '' }
  }
  stockInDialogVisible.value = true
}

/** 提交入库登记。 */
async function submitStockIn() {
  if (!stockInForm.value.material_id) {
    ElMessage.warning(t('materialManagement.msgMaterialRequired'))
    return
  }
  if (!stockInForm.value.quantity || stockInForm.value.quantity <= 0) {
    ElMessage.warning(t('materialManagement.msgQuantityInvalid'))
    return
  }
  stockInSubmitting.value = true
  try {
    const res = await http.post(
      API_CONFIG.MATERIALS + `/${stockInForm.value.material_id}/stock-in`,
      {
        quantity: stockInForm.value.quantity,
        remark: stockInForm.value.remark.trim() || null,
      },
    )
    if (res.data.code === 0) {
      ElMessage.success(t('materialManagement.msgStockInSuccess'))
      stockInDialogVisible.value = false
      fetchMaterials()
    } else {
      ElMessage.error(res.data.message || t('materialManagement.msgOperationFailed'))
    }
  } catch (e: unknown) {
    console.warn('[MaterialManagement] stock-in failed:', e)
    ElMessage.error(t('materialManagement.msgOperationFailed'))
  } finally {
    stockInSubmitting.value = false
  }
}

// ========================= 采购申请弹窗 =========================
const purchaseDialogVisible = ref(false)
const purchaseSubmitting = ref(false)
const purchaseForm = ref({
  material_id: '' as number | '',
  quantity: 1 as number,
  supplier: '',
})

/** 打开采购申请弹窗。 */
function handlePurchase(row: Material) {
  purchaseForm.value = {
    material_id: row.id,
    quantity: 1,
    supplier: row.supplier || '',
  }
  purchaseDialogVisible.value = true
}

/** 提交采购申请。 */
async function submitPurchase() {
  if (!purchaseForm.value.material_id) {
    ElMessage.warning(t('materialManagement.msgMaterialRequired'))
    return
  }
  if (!purchaseForm.value.quantity || purchaseForm.value.quantity <= 0) {
    ElMessage.warning(t('materialManagement.msgQuantityInvalid'))
    return
  }
  purchaseSubmitting.value = true
  try {
    const res = await http.post(
      API_CONFIG.MATERIALS + `/${purchaseForm.value.material_id}/purchase`,
      {
        quantity: purchaseForm.value.quantity,
        supplier: purchaseForm.value.supplier.trim() || null,
      },
    )
    if (res.data.code === 0) {
      ElMessage.success(t('materialManagement.msgPurchaseSuccess'))
      purchaseDialogVisible.value = false
      fetchMaterials()
    } else {
      ElMessage.error(res.data.message || t('materialManagement.msgOperationFailed'))
    }
  } catch (e: unknown) {
    console.warn('[MaterialManagement] purchase failed:', e)
    ElMessage.error(t('materialManagement.msgOperationFailed'))
  } finally {
    purchaseSubmitting.value = false
  }
}

// ========================= 详情弹窗 =========================
const detailDialogVisible = ref(false)
const detailLoading = ref(false)
const detailData = ref<Material | null>(null)

/** 查看物料详情（GET /api/v1/materials/{id}）。 */
async function handleViewDetail(row: Material) {
  detailDialogVisible.value = true
  detailLoading.value = true
  detailData.value = null
  try {
    const res = await http.get(API_CONFIG.MATERIALS + `/${row.id}`)
    if (res.data.code === 0 && res.data.data) {
      detailData.value = res.data.data
    } else {
      ElMessage.error(res.data.message || t('materialManagement.msgOperationFailed'))
    }
  } catch (e: unknown) {
    console.warn('[MaterialManagement] fetch detail failed:', e)
    ElMessage.error(t('materialManagement.msgOperationFailed'))
  } finally {
    detailLoading.value = false
  }
}

/** 采购弹窗中当前选中物料的展示标签。 */
const purchaseMaterialLabel = computed(() => {
  const m = materials.value.find((x) => x.id === purchaseForm.value.material_id)
  return m ? `${m.code} - ${m.name}` : ''
})

// ========================= 生命周期 =========================
onMounted(() => {
  fetchMaterials()
})
</script>

<style scoped>
.material-management-page {
  padding: var(--page-padding);
  max-width: var(--content-max-width);
  margin: 0 auto;
}

/* 统计卡片图标颜色 */
.stat-card--warning .stat-card__icon {
  background: var(--warning-bg);
  color: var(--warning);
}

.stat-card--danger .stat-card__icon {
  background: var(--error-bg);
  color: var(--error);
}

.stat-card--info .stat-card__icon {
  background: var(--info-bg);
  color: var(--info);
}

/* 页面特有样式 */
.category-text {
  color: var(--text-secondary);
}

.text-danger {
  color: var(--error);
  font-weight: 600;
}

.text-warning {
  color: var(--warning);
  font-weight: 600;
}
</style>
