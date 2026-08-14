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
import { ref, onMounted, onUnmounted } from 'vue'
import {
  useAnimationExport,
  useCollisionHandling,
  useFemSolver,
  useSimulationHistory,
  useSimulationRunner,
} from '@/composables/simulation'
import SimulationPageHeader from '@/components/simulation/SimulationPageHeader.vue'
import SimulationStatsRow from '@/components/simulation/SimulationStatsRow.vue'
import SimulationTabSwitcher from '@/components/simulation/SimulationTabSwitcher.vue'
import SimulationNcTab from '@/components/simulation/SimulationNcTab.vue'
import SimulationFemTab from '@/components/simulation/SimulationFemTab.vue'
import SimulationExportTab from '@/components/simulation/SimulationExportTab.vue'
import CollisionAlertModal from '@/components/simulation/CollisionAlertModal.vue'

const ncTabRef = ref<InstanceType<typeof SimulationNcTab> | null>(null)
const activeTab = ref<string>('simulation')

// 历史与统计
const {
  historyItems,
  historyLoading,
  fetchHistory,
  passCount,
  failCount,
  avgDuration,
} = useSimulationHistory()

// 仿真运行核心
const {
  gcode,
  simParams,
  simState,
  currentTaskId,
  simResult,
  showCollisionDetail,
  handleRunSimulation,
  stopPolling,
  resetRun,
} = useSimulationRunner({
  onTaskCompleted: () => {
    void fetchHistory()
  },
  getViewer: () => ncTabRef.value?.viewerRef ?? null,
})

// 碰撞处理
const {
  collisionList,
  handleLocateCollision,
  handleDismissCollision,
  handleDismissAllCollisions,
} = useCollisionHandling(simResult)

// FEM 求解
const {
  femParams,
  femResult,
  femSolving,
  resetFemParams,
  handleStartSolve,
} = useFemSolver()

// 动画导出与 STL 下载
const {
  gifExport,
  mp4Export,
  exportLoading,
  handleExportGif,
  handleExportMp4,
  handleDownloadStl,
} = useAnimationExport({ gcode, simParams, simResult })

function handleNewSimulation() {
  resetRun()
  activeTab.value = 'simulation'
}

onMounted(() => {
  void fetchHistory()
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
