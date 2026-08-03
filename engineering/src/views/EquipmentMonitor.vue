<template>
  <div class="equipment-monitor-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="page-header__title">
        <h1 class="page-title">
          {{ t('equipmentMonitor.pageTitle') }}
        </h1>
        <p class="page-subtitle">
          {{ t('equipmentMonitor.pageSubtitle') }}
        </p>
      </div>
      <div class="page-header__actions">
        <el-button
          size="small"
          :icon="Refresh"
          :loading="refreshing"
          @click="handleRefresh"
        >
          {{ t('equipmentMonitor.btnRefresh') }}
        </el-button>
        <el-button
          type="primary"
          size="small"
          :icon="Setting"
          @click="handleSettings"
        >
          {{ t('equipmentMonitor.btnSettings') }}
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

    <!-- 设备列表 -->
    <div class="content-card">
      <div class="content-card__header">
        <span class="content-card__title">{{ t('equipmentMonitor.sectionDeviceList') }}</span>
        <div class="filter-bar">
          <el-select
            v-model="statusFilter"
            :placeholder="t('equipmentMonitor.placeholderStatus')"
            size="small"
          >
            <el-option
              :label="t('equipmentMonitor.labelStatusAll')"
              value="all"
            />
            <el-option
              :label="t('equipmentMonitor.labelStatusRunning')"
              :value="t('equipmentMonitor.labelStatusRunning')"
            />
            <el-option
              :label="t('equipmentMonitor.labelStatusStandby')"
              :value="t('equipmentMonitor.labelStatusStandby')"
            />
            <el-option
              :label="t('equipmentMonitor.labelStatusFault')"
              :value="t('equipmentMonitor.labelStatusFault')"
            />
            <el-option
              :label="t('equipmentMonitor.labelStatusMaintenance')"
              :value="t('equipmentMonitor.labelStatusMaintenance')"
            />
          </el-select>
          <el-input
            v-model="searchKeyword"
            :placeholder="t('equipmentMonitor.placeholderSearch')"
            clearable
            size="small"
          />
        </div>
      </div>
      <div class="content-card__body">
        <el-table
          v-loading="loading"
          :data="filteredDevices"
          stripe
          style="width: 100%"
          :empty-text="t('equipmentMonitor.emptyData')"
        >
          <el-table-column
            prop="id"
            :label="t('equipmentMonitor.colDeviceId')"
            width="120"
          />
          <el-table-column
            prop="name"
            :label="t('equipmentMonitor.colDeviceName')"
            min-width="160"
          />
          <el-table-column
            prop="model"
            :label="t('equipmentMonitor.colDeviceModel')"
            min-width="180"
            show-overflow-tooltip
          />
          <el-table-column
            prop="location"
            :label="t('equipmentMonitor.colDeviceLocation')"
            min-width="140"
            show-overflow-tooltip
          />
          <el-table-column
            :label="t('equipmentMonitor.colStatus')"
            width="100"
          >
            <template #default="{ row }">
              <el-tag
                :type="statusTagType(row.status)"
                size="small"
                effect="light"
              >
                {{ row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            prop="temperature"
            :label="t('equipmentMonitor.colTemperature')"
            width="110"
          />
          <el-table-column
            prop="vibration"
            :label="t('equipmentMonitor.colVibration')"
            width="120"
          />
          <el-table-column
            prop="rpm"
            :label="t('equipmentMonitor.colRpm')"
            width="120"
          />
          <el-table-column
            prop="power"
            :label="t('equipmentMonitor.colPower')"
            width="110"
          />
          <el-table-column
            :label="t('equipmentMonitor.colActions')"
            width="180"
            fixed="right"
          >
            <template #default="{ row }">
              <el-button
                text
                type="primary"
                size="small"
                @click="handleViewDetail(row as Device)"
              >
                {{ t('equipmentMonitor.btnDetail') }}
              </el-button>
              <el-button
                v-if="row.status === t('equipmentMonitor.labelStatusRunning')"
                text
                type="warning"
                size="small"
                @click="handleStop(row as Device)"
              >
                {{ t('equipmentMonitor.btnStop') }}
              </el-button>
              <el-button
                v-if="row.status === t('equipmentMonitor.labelStatusFault')"
                text
                type="danger"
                size="small"
                @click="handleRepair(row as Device)"
              >
                {{ t('equipmentMonitor.btnRepair') }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- 设备参数设置弹窗 -->
    <el-dialog
      v-model="settingsDialogVisible"
      :title="t('equipmentMonitor.dialogSettingsTitle')"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-form label-width="110px" @submit.prevent>
        <el-form-item :label="t('equipmentMonitor.colDeviceName')">
          <el-input :model-value="settingsForm.name" disabled />
        </el-form-item>
        <el-form-item :label="t('equipmentMonitor.fieldStatus')">
          <el-select v-model="settingsForm.status" style="width: 100%">
            <el-option :label="t('equipmentMonitor.labelStatusRunning')" :value="t('equipmentMonitor.labelStatusRunning')" />
            <el-option :label="t('equipmentMonitor.labelStatusStandby')" :value="t('equipmentMonitor.labelStatusStandby')" />
            <el-option :label="t('equipmentMonitor.labelStatusMaintenance')" :value="t('equipmentMonitor.labelStatusMaintenance')" />
            <el-option :label="t('equipmentMonitor.labelStatusFault')" :value="t('equipmentMonitor.labelStatusFault')" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('equipmentMonitor.fieldTemperature')">
          <el-input-number v-model="settingsForm.temperature" :min="0" :max="500" :precision="1" style="width: 100%" />
        </el-form-item>
        <el-form-item :label="t('equipmentMonitor.fieldVibration')">
          <el-input-number v-model="settingsForm.vibration" :min="0" :max="50" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item :label="t('equipmentMonitor.fieldRpm')">
          <el-input-number v-model="settingsForm.rpm" :min="0" :max="50000" style="width: 100%" />
        </el-form-item>
        <el-form-item :label="t('equipmentMonitor.fieldPower')">
          <el-input-number v-model="settingsForm.power" :min="0" :max="1000" :precision="1" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="settingsDialogVisible = false">
          {{ t('equipmentMonitor.btnCancel') }}
        </el-button>
        <el-button type="primary" :loading="settingsSubmitting" @click="submitSettings">
          {{ t('equipmentMonitor.btnSubmit') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 设备详情弹窗 -->
    <el-dialog
      v-model="detailDialogVisible"
      :title="t('equipmentMonitor.dialogDetailTitle')"
      width="520px"
    >
      <div v-loading="detailLoading" style="min-height: 200px">
        <template v-if="detailData">
          <el-descriptions :column="1" border>
            <el-descriptions-item :label="t('equipmentMonitor.colDeviceId')">
              {{ detailData.id }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('equipmentMonitor.colDeviceName')">
              {{ detailData.name }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('equipmentMonitor.fieldModel')">
              {{ detailData.model || '—' }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('equipmentMonitor.fieldLocation')">
              {{ detailData.location || '—' }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('equipmentMonitor.colStatus')">
              <el-tag :type="statusTagType(detailData.status)" size="small" effect="light">
                {{ detailData.status }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item :label="t('equipmentMonitor.fieldTemperature')">
              {{ detailData.temperature ?? '—' }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('equipmentMonitor.fieldVibration')">
              {{ detailData.vibration ?? '—' }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('equipmentMonitor.fieldRpm')">
              {{ detailData.rpm ?? '—' }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('equipmentMonitor.fieldPower')">
              {{ detailData.power ?? '—' }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('equipmentMonitor.fieldUpdatedAt')">
              {{ detailData.updated_at }}
            </el-descriptions-item>
          </el-descriptions>
        </template>
      </div>
      <template #footer>
        <el-button @click="detailDialogVisible = false">
          {{ t('equipmentMonitor.btnCancel') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, type Component } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Setting, Monitor, VideoPlay, Clock, WarningFilled } from '@element-plus/icons-vue'
import http from '@/utils/http'
import { API_CONFIG } from '@/config/api'

const { t } = useI18n()

// ========================= 类型定义 =========================
interface Device {
  id: number
  name: string
  model: string
  location: string
  status: string
  temperature: number | null
  vibration: number | null
  rpm: number | null
  power: number | null
  created_at: string
  updated_at: string
}

interface EquipmentStats {
  total: number
  running: number
  standby: number
  maintenance: number
  fault: number
}

interface Alarm {
  id: number
  equipment_id: number
  alarm_type: string
  severity: string
  message: string
  status: string
  created_at: string
}

interface MaintenancePlan {
  id: number
  equipment_id: number
  title: string
  type: string
  frequency: string
  last_date: string
  next_date: string
  status: string
}

interface StatsCard {
  label: string
  value: number
  icon: Component
  type: string
}

// ========================= 状态 =========================
const loading = ref(false)
const refreshing = ref(false)
const searchKeyword = ref('')
const statusFilter = ref('all')

const devices = ref<Device[]>([])
const stats = ref<EquipmentStats>({ total: 0, running: 0, standby: 0, maintenance: 0, fault: 0 })
const alarms = ref<Alarm[]>([])
const maintenancePlans = ref<MaintenancePlan[]>([])

// ========================= 状态映射 =========================
// 后端状态中文值 → 前端过滤/标签类型映射
const STATUS_TO_TAG_TYPE: Record<string, 'success' | 'info' | 'danger' | 'warning'> = {
  [t('equipmentMonitor.labelStatusRunning')]: 'success',
  [t('equipmentMonitor.labelStatusStandby')]: 'info',
  [t('equipmentMonitor.labelStatusFault')]: 'danger',
  [t('equipmentMonitor.labelStatusMaintenance')]: 'warning',
}

// ========================= 计算属性 =========================
const statsCards = computed<StatsCard[]>(() => {
  const s = stats.value
  return [
    { label: t('equipmentMonitor.statTotal'), value: s.total, icon: Monitor, type: 'default' },
    { label: t('equipmentMonitor.statRunning'), value: s.running, icon: VideoPlay, type: 'success' },
    { label: t('equipmentMonitor.statStandby'), value: s.standby, icon: Clock, type: 'info' },
    { label: t('equipmentMonitor.statFault'), value: s.fault, icon: WarningFilled, type: 'danger' },
  ]
})

const filteredDevices = computed(() => {
  return devices.value.filter(d => {
    const keyword = searchKeyword.value.trim().toLowerCase()
    if (keyword && !String(d.id).includes(keyword) && !d.name.toLowerCase().includes(keyword)) {
      return false
    }
    if (statusFilter.value !== 'all' && d.status !== statusFilter.value) {
      return false
    }
    return true
  })
})

// ========================= 方法 =========================
function statusTagType(status: string): 'success' | 'info' | 'danger' | 'warning' {
  return STATUS_TO_TAG_TYPE[status] || 'info'
}

async function fetchDevices() {
  loading.value = true
  try {
    // 并行请求所有接口
    const [deviceRes, statsRes, alarmsRes, maintenanceRes] = await Promise.all([
      http.get(API_CONFIG.EQUIPMENT),
      http.get(API_CONFIG.EQUIPMENT + '/stats/'),
      http.get(API_CONFIG.EQUIPMENT + '/alarms/'),
      http.get(API_CONFIG.EQUIPMENT + '/maintenance/'),
    ])

    // 设备列表（后端返回 { items, total, page, ... }）
    if (deviceRes.data?.code === 0) {
      devices.value = deviceRes.data.data?.items || []
    } else {
      devices.value = []
    }

    // 设备统计
    if (statsRes.data?.code === 0) {
      stats.value = statsRes.data.data || { total: 0, running: 0, standby: 0, maintenance: 0, fault: 0 }
    }

    // 告警列表
    if (alarmsRes.data?.code === 0) {
      alarms.value = alarmsRes.data.data || []
    }

    // 维护计划
    if (maintenanceRes.data?.code === 0) {
      maintenancePlans.value = maintenanceRes.data.data || []
    }
  } catch {
    // API 调用失败时显示空状态
    devices.value = []
    stats.value = { total: 0, running: 0, standby: 0, maintenance: 0, fault: 0 }
    alarms.value = []
    maintenancePlans.value = []
    ElMessage.error(t('equipmentMonitor.msgLoadFailed'))
  } finally {
    loading.value = false
  }
}

async function handleRefresh() {
  refreshing.value = true
  await fetchDevices()
  refreshing.value = false
  ElMessage.success(t('equipmentMonitor.msgRefreshed'))
}

// ========================= 设备参数设置弹窗 =========================
const settingsDialogVisible = ref(false)
const settingsSubmitting = ref(false)
const settingsForm = ref({
  id: 0,
  name: '',
  status: '',
  temperature: null as number | null,
  vibration: null as number | null,
  rpm: null as number | null,
  power: null as number | null,
})

/** 打开设备参数设置弹窗。 */
function handleSettings(row?: Device | MouseEvent) {
  if (row && typeof row === 'object' && 'id' in row) {
    settingsForm.value = {
      id: row.id,
      name: row.name,
      status: row.status,
      temperature: row.temperature,
      vibration: row.vibration,
      rpm: row.rpm,
      power: row.power,
    }
  } else {
    // 顶部"监控配置"按钮：默认选中第一台设备
    const first = devices.value[0]
    if (!first) {
      ElMessage.warning(t('equipmentMonitor.emptyData'))
      return
    }
    settingsForm.value = {
      id: first.id,
      name: first.name,
      status: first.status,
      temperature: first.temperature,
      vibration: first.vibration,
      rpm: first.rpm,
      power: first.power,
    }
  }
  settingsDialogVisible.value = true
}

/** 保存设备参数（PUT /api/v1/equipment/{id}）。 */
async function submitSettings() {
  if (!settingsForm.value.id) return
  settingsSubmitting.value = true
  try {
    const res = await http.put(
      API_CONFIG.EQUIPMENT + `/${settingsForm.value.id}`,
      {
        status: settingsForm.value.status,
        temperature: settingsForm.value.temperature,
        vibration: settingsForm.value.vibration,
        rpm: settingsForm.value.rpm,
        power: settingsForm.value.power,
      },
    )
    if (res.data.code === 0) {
      ElMessage.success(t('equipmentMonitor.msgSettingsSaved'))
      settingsDialogVisible.value = false
      fetchDevices()
    } else {
      ElMessage.error(res.data.message || t('equipmentMonitor.msgSettingsFailed'))
    }
  } catch (e: unknown) {
    console.warn('[EquipmentMonitor] save settings failed:', e)
    ElMessage.error(t('equipmentMonitor.msgSettingsFailed'))
  } finally {
    settingsSubmitting.value = false
  }
}

// ========================= 设备详情弹窗 =========================
const detailDialogVisible = ref(false)
const detailLoading = ref(false)
const detailData = ref<Device | null>(null)

/** 查看设备详情（GET /api/v1/equipment/{id}）。 */
async function handleViewDetail(row: Device) {
  detailDialogVisible.value = true
  detailLoading.value = true
  detailData.value = null
  try {
    const res = await http.get(API_CONFIG.EQUIPMENT + `/${row.id}`)
    if (res.data.code === 0 && res.data.data) {
      detailData.value = res.data.data
    } else {
      ElMessage.error(res.data.message || t('equipmentMonitor.msgOpFailed'))
    }
  } catch (e: unknown) {
    console.warn('[EquipmentMonitor] fetch detail failed:', e)
    ElMessage.error(t('equipmentMonitor.msgOpFailed'))
  } finally {
    detailLoading.value = false
  }
}

// ========================= 停机 / 报修 =========================

/** 停机：将设备状态切换为「待机」。 */
async function handleStop(row: Device) {
  try {
    await ElMessageBox.confirm(
      t('equipmentMonitor.msgStopConfirm', { name: row.name }),
      t('equipmentMonitor.btnStop'),
      { type: 'warning', confirmButtonText: t('equipmentMonitor.btnSubmit'), cancelButtonText: t('equipmentMonitor.btnCancel') },
    )
  } catch {
    return // 用户取消
  }
  try {
    const res = await http.put(API_CONFIG.EQUIPMENT + `/${row.id}`, {
      status: t('equipmentMonitor.labelStatusStandby'),
    })
    if (res.data.code === 0) {
      ElMessage.success(t('equipmentMonitor.msgStopSuccess'))
      fetchDevices()
    } else {
      ElMessage.error(res.data.message || t('equipmentMonitor.msgOpFailed'))
    }
  } catch (e: unknown) {
    console.warn('[EquipmentMonitor] stop failed:', e)
    ElMessage.error(t('equipmentMonitor.msgOpFailed'))
  }
}

/** 报修：将设备状态切换为「维护中」。 */
async function handleRepair(row: Device) {
  try {
    await ElMessageBox.confirm(
      t('equipmentMonitor.msgRepairConfirm', { name: row.name }),
      t('equipmentMonitor.btnRepair'),
      { type: 'warning', confirmButtonText: t('equipmentMonitor.btnSubmit'), cancelButtonText: t('equipmentMonitor.btnCancel') },
    )
  } catch {
    return // 用户取消
  }
  try {
    const res = await http.put(API_CONFIG.EQUIPMENT + `/${row.id}`, {
      status: t('equipmentMonitor.labelStatusMaintenance'),
    })
    if (res.data.code === 0) {
      ElMessage.success(t('equipmentMonitor.msgRepairSuccess'))
      fetchDevices()
    } else {
      ElMessage.error(res.data.message || t('equipmentMonitor.msgOpFailed'))
    }
  } catch (e: unknown) {
    console.warn('[EquipmentMonitor] repair failed:', e)
    ElMessage.error(t('equipmentMonitor.msgOpFailed'))
  }
}

// ========================= 生命周期 =========================
onMounted(() => {
  fetchDevices()
})
</script>

<style scoped>
.equipment-monitor-page {
  padding: var(--page-padding);
  max-width: var(--content-max-width);
  margin: 0 auto;
}

/* 统计卡片图标颜色 */
.stat-card--success .stat-card__icon {
  background: var(--success-bg);
  color: var(--success);
}

.stat-card--info .stat-card__icon {
  background: var(--info-bg);
  color: var(--info);
}

.stat-card--danger .stat-card__icon {
  background: var(--error-bg);
  color: var(--error);
}

/* 页面特有样式 */
.runtime-text {
  font-variant-numeric: tabular-nums;
  color: var(--text-accent);
  font-weight: 500;
}
</style>
