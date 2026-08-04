<template>
  <div class="simulation-page">
    <!-- 页面头部 -->
    <SimulationPageHeader
      :history-loading="historyLoading"
      @refresh="fetchHistory"
      @new-simulation="handleNewSimulation"
    />

    <!-- 统计概览 -->
    <SimulationStatsRow
      :total-count="historyItems.length"
      :pass-count="passCount"
      :fail-count="failCount"
      :avg-duration="avgDuration"
    />

    <!-- Tab 切换 -->
    <SimulationTabSwitcher v-model="activeTab" />

    <!-- Tab 1: NC Code Simulation -->
    <SimulationNcTab
      v-show="activeTab === 'simulation'"
      ref="ncTabRef"
      :gcode="gcode"
      :sim-params="simParams"
      :sim-state="simState"
      :sim-result="simResult"
      :history-items="historyItems"
      :history-loading="historyLoading"
      :current-task-id="currentTaskId"
      @update:gcode="gcode = $event"
      @update:sim-params="simParams = $event"
      @run="handleRunSimulation"
      @download-stl="handleDownloadStl"
      @update:show-collision-detail="showCollisionDetail = $event"
    />

    <!-- Tab 2: FEM Analysis -->
    <SimulationFemTab
      v-show="activeTab === 'fem'"
      :fem-params="femParams"
      :fem-result="femResult"
      :fem-solving="femSolving"
      @update:fem-params="femParams = $event"
      @solve="handleStartSolve"
      @reset="resetFemParams"
    />

    <!-- Tab 3: Export Management -->
    <SimulationExportTab
      v-show="activeTab === 'export'"
      :gif-export="gifExport"
      :mp4-export="mp4Export"
      :export-loading="exportLoading"
      @update:gif-export="gifExport = $event"
      @update:mp4-export="mp4Export = $event"
      @export-gif="handleExportGif"
      @export-mp4="handleExportMp4"
    />

    <!-- Collision Detail Modal -->
    <CollisionAlertModal
      v-model:visible="showCollisionDetail"
      :collisions="collisionList"
      @locate="handleLocateCollision"
      @dismiss="handleDismissCollision"
      @dismiss-all="handleDismissAllCollisions"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import http from '@/utils/http'
import { API_CONFIG, buildApiPath } from '@/config/api'
import { useProjectStore } from '@/stores/project'
import { useI18n } from 'vue-i18n'
import SimulationPageHeader from '@/components/simulation/SimulationPageHeader.vue'
import SimulationStatsRow from '@/components/simulation/SimulationStatsRow.vue'
import SimulationTabSwitcher from '@/components/simulation/SimulationTabSwitcher.vue'
import SimulationNcTab from '@/components/simulation/SimulationNcTab.vue'
import SimulationFemTab from '@/components/simulation/SimulationFemTab.vue'
import SimulationExportTab from '@/components/simulation/SimulationExportTab.vue'
import CollisionAlertModal from '@/components/simulation/CollisionAlertModal.vue'
const projectStore = useProjectStore()
const { t } = useI18n()
// ─── Types ─────────────────────────
interface CollisionInfo {
  position: [number, number, number]
  severity: 'warning' | 'critical'
  toolSegment: number
  description: string
}

interface SimResultData {
  task_id: string
  collision_detected: boolean
  collision_details: {
    timestamp: string
    positions: number[][]
    segment_indices: number[]
    severity: string
    count: number
  } | null
  duration_seconds: number
  voxel_count: number
  removed_voxel_count: number
  voxel_size: number
  toolpath_segment_count: number
  simulation_result: {
    workpiece_stl_path: string
    voxel_count: number
    removed_voxel_count: number
    voxel_size: number
    original_bbox: Record<string, number> | null
  } | null
}

interface HistoryItem {
  task_id: string
  project_id: string
  duration_seconds: number
  collision_collided: boolean
  voxel_size: number
  segment_count: number
}

// ─── Tabs ─────────────────────────
const activeTab = ref<string>('simulation')

// ─── Stats ─────────────────────────
const passCount = computed(() => historyItems.value.filter((h) => !h.collision_collided).length)
const failCount = computed(() => historyItems.value.filter((h) => h.collision_collided).length)
const avgDuration = computed(() => {
  const items = historyItems.value
  if (items.length === 0) return '--'
  const total = items.reduce((sum, h) => sum + (h.duration_seconds ?? 0), 0)
  return (total / items.length).toFixed(1) + 's'
})

// ─── NC Code ─────────────────────
const gcode = ref('')
const ncTabRef = ref<InstanceType<typeof SimulationNcTab> | null>(null)

function handleNewSimulation() {
  gcode.value = ''
  simResult.value = null
  simState.value = 'idle'
  currentTaskId.value = ''
  showCollisionDetail.value = false
  activeTab.value = 'simulation'
}

// ─── Sim Params ──────────────────
const simParams = ref({
  voxelSize: 1.0,
  toolType: 'flat',
  toolDiameter: 10.0,
  toolLength: 50.0,
  toolCornerRadius: 0.0,
  safeZ: 30.0,
  stockStlPath: '',
})

// ─── Sim State ────────────────────
type SimState = 'idle' | 'running' | 'completed' | 'failed'
const simState = ref<SimState>('idle')
const currentTaskId = ref('')
const simResult = ref<SimResultData | null>(null)
const showCollisionDetail = ref(false)
// 已忽略的碰撞索引集合
const dismissedCollisions = ref<Set<number>>(new Set())

const collisionList = computed<CollisionInfo[]>(() => {
  if (!simResult.value?.collision_detected || !simResult.value.collision_details) return []
  const details = simResult.value.collision_details
  return details.positions
    .map((pos, idx) => ({
      position: pos as [number, number, number],
      severity: (details.severity === 'critical' ? 'critical' : 'warning') as CollisionInfo['severity'],
      toolSegment: details.segment_indices[idx] ?? idx,
      description: t('simulationPage.msgCollisionDesc', { idx: idx + 1, severity: details.severity }),
    }))
    .filter((_, idx) => !dismissedCollisions.value.has(idx))
})

let pollTimer: ReturnType<typeof setInterval> | null = null

async function handleRunSimulation() {
  if (!gcode.value.trim()) {
    ElMessage.warning(t('simulationPage.msgNoGcode'))
    return
  }

  simState.value = 'running'
  simResult.value = null
  showCollisionDetail.value = false

  try {
    // Submit async simulation
    const res = await http.post(buildApiPath(API_CONFIG.SIMULATION, '/run/async'), {
      project_id: projectStore.projectId || 'default',
      voxel_size: simParams.value.voxelSize,
      tool_diameter: simParams.value.toolDiameter,
      tool_length: simParams.value.toolLength,
      tool_type: simParams.value.toolType,
      tool_corner_radius: simParams.value.toolCornerRadius,
      gcode: gcode.value,
      safe_z_height: simParams.value.safeZ,
      stock_stl_path: simParams.value.stockStlPath || undefined,
    })

    const responseData = res.data?.data ?? res.data
    const taskId = responseData?.task_id
    if (!taskId) {
      throw new Error(t('simulationPage.msgNoTaskId'))
    }

    currentTaskId.value = taskId
    ElMessage.info(t('simulationPage.msgTaskSubmitted', { taskId }))

    // Start polling
    startPolling(taskId)
  } catch (err: unknown) {
    simState.value = 'failed'
    const msg = err instanceof Error ? err.message : t('simulationPage.msgSubmitFailed')
    ElMessage.error(msg)
  }
}

function startPolling(taskId: string) {
  stopPolling()
  pollTimer = setInterval(async () => {
    try {
      const res = await http.get(buildApiPath(API_CONFIG.SIMULATION, `/status/${taskId}`))
      const responseData = res.data?.data ?? res.data
      const status = responseData?.status

      if (status === 'completed') {
        stopPolling()
        simState.value = 'completed'
        simResult.value = responseData?.result ?? null

        if (simResult.value?.collision_detected) {
          ElMessage.warning(t('simulationPage.msgCollisionDetected'))
        } else {
          ElMessage.success(t('simulationPage.msgSimPassed'))
        }

        // Try to load STL into the 3D viewer (via NC tab ref)
        if (simResult.value?.simulation_result?.workpiece_stl_path && ncTabRef.value?.viewerRef) {
          ncTabRef.value.viewerRef.loadVoxelData(simResult.value.simulation_result)
        }

        // Refresh history
        fetchHistory()
      } else if (status === 'not_found') {
        stopPolling()
        simState.value = 'failed'
        ElMessage.error(t('simulationPage.msgTaskNotFound'))
      }
      // status === 'running' or 'pending' → continue polling
    } catch {
      // Network error, continue polling
    }
  }, 2000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

// ─── Collision ────────────────────
function handleLocateCollision(index: number) {
  const collision = collisionList.value[index]
  if (collision) {
    // Future: highlight collision point in 3D viewer
    ElMessage.info(t('simulationPage.msgLocateCollision', { index: index + 1, pos: collision.position.map((v) => v.toFixed(2)).join(', ') }))
  }
}

function handleDismissCollision(index?: number) {
  // 从碰撞列表中移除指定索引（真实状态变更）
  if (index === undefined) return
  dismissedCollisions.value = new Set(dismissedCollisions.value).add(index)
  if (collisionList.value.length === 0) {
    ElMessage.success(t('simulationPage.msgAllCollisionsDismissed'))
  }
}

function handleDismissAllCollisions() {
  // 忽略全部碰撞
  const details = simResult.value?.collision_details
  if (details) {
    details.positions.forEach((_, idx) => {
      dismissedCollisions.value = new Set(dismissedCollisions.value).add(idx)
    })
  }
  ElMessage.success(t('simulationPage.msgAllCollisionsDismissed'))
}

// ─── Download STL ────────────────
function handleDownloadStl() {
  const stlPath = simResult.value?.simulation_result?.workpiece_stl_path
  if (!stlPath) {
    ElMessage.warning(t('simulationPage.msgNoStl'))
    return
  }
  // Extract filename from path
  const filename = stlPath.split('/').pop() || stlPath.split('\\').pop() || 'result.stl'
  const url = `/simulation/output/${filename}`
  // Create download link
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
}

// ─── History ──────────────────────
const historyItems = ref<HistoryItem[]>([])
const historyLoading = ref(false)

async function fetchHistory() {
  historyLoading.value = true
  try {
    const res = await http.get(buildApiPath(API_CONFIG.SIMULATION, '/history'), {
      params: { limit: 20 },
    })
    const data = res.data?.data ?? res.data
    historyItems.value = data?.items ?? []
  } catch {
    historyItems.value = []
  } finally {
    historyLoading.value = false
  }
}

// ─── FEM ──────────────────────────
const femParams = ref({
  material: 'steel45',
  elasticModulus: 210.0,
  poissonRatio: 0.300,
  density: 7850.0,
  yieldStrength: 355.0,
  thermalConductivity: 50.0,
  meshType: 'tetrahedral',
  elementSize: 2.0,
  adaptiveRefinement: true,
})

function resetFemParams() {
  femParams.value = {
    material: 'steel45',
    elasticModulus: 210.0,
    poissonRatio: 0.300,
    density: 7850.0,
    yieldStrength: 355.0,
    thermalConductivity: 50.0,
    meshType: 'tetrahedral',
    elementSize: 2.0,
    adaptiveRefinement: true,
  }
}

// FEM 求解结果
interface FEMResult {
  material: string
  max_stress: number
  max_deflection: number
  yield_strength: number
  safety_factor: number
  nodes: number
  status: string
  warning?: string
  stress_distribution?: Array<{ x: number; stress: number }>
}

const femResult = ref<FEMResult | null>(null)
const femSolving = ref(false)

async function handleStartSolve() {
  femSolving.value = true
  femResult.value = null
  try {
    const res = await http.post(buildApiPath(API_CONFIG.SIMULATION, '/fem/solve'), {
      material: femParams.value.material,
      elastic_modulus: femParams.value.elasticModulus,
      poisson_ratio: femParams.value.poissonRatio,
      density: femParams.value.density,
      yield_strength: femParams.value.yieldStrength,
      mesh_type: femParams.value.meshType,
      element_size: femParams.value.elementSize,
      adaptive_refinement: femParams.value.adaptiveRefinement,
      beam_length: 100.0,
      beam_width: 20.0,
      beam_height: 20.0,
      load_force: 5000.0,
    })
    if (res.data.code === 0 && res.data.data) {
      femResult.value = res.data.data
      ElMessage.success(t('simulationPage.msgFemDone'))
    } else {
      ElMessage.error(res.data.message || t('simulationPage.msgFemFailed'))
    }
  } catch (e: unknown) {
    console.warn('[Simulation] FEM solve failed:', e)
    ElMessage.error(t('simulationPage.msgFemFailed'))
  } finally {
    femSolving.value = false
  }
}

// ─── Export ───────────────────────
const gifExport = ref({
  resolution: '1280x720',
  framerate: 15,
  quality: 'medium',
})

const mp4Export = ref({
  resolution: '1920x1080',
  framerate: 30,
  codec: 'h264',
  bitrate: '10',
})

const exportLoading = ref<'gif' | 'mp4' | null>(null)

/** 导出仿真动画（真实调用 POST /api/simulation/export-animation，blob 下载）。 */
async function exportAnimation(format: 'gif' | 'mp4') {
  if (!gcode.value.trim()) {
    ElMessage.warning(t('simulationPage.msgNoGcode'))
    return
  }
  exportLoading.value = format
  try {
    const res = await http.post(
      buildApiPath(API_CONFIG.SIMULATION, '/export-animation'),
      {
        nc_code: gcode.value,
        format,
        voxel_size: simParams.value.voxelSize,
        tool_diameter: simParams.value.toolDiameter,
        tool_length: simParams.value.toolLength,
        tool_type: simParams.value.toolType,
      },
      { responseType: 'blob' },
    )
    // 后端返回文件流，触发浏览器下载
    const blob = res.data as Blob
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    const ts = new Date().toISOString().replace(/[:.]/g, '-')
    a.href = url
    a.download = `simulation_${format}_${ts}.${format}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    ElMessage.success(t('simulationPage.msgExportSuccess', { format: format.toUpperCase() }))
  } catch (e: unknown) {
    console.warn('[Simulation] export animation failed:', e)
    ElMessage.error(t('simulationPage.msgExportFailed'))
  } finally {
    exportLoading.value = null
  }
}

function handleExportGif() {
  void exportAnimation('gif')
}

function handleExportMp4() {
  void exportAnimation('mp4')
}

// ─── Lifecycle ────────────────────
onMounted(() => {
  fetchHistory()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.simulation-page {
  padding: var(--page-padding);
  max-width: var(--content-max-width);
  margin: 0 auto;
}
</style>