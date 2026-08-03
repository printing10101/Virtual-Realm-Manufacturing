/** Features barrel export — 功能模块 API 服务层统一入口。

V3.0 Feature-Sliced Design: 所有视图组件通过此入口导入 API 函数，
替代直接使用 http 客户端。

使用: import { predictLNN, fetchGoals } from '@/features'
*/

// Workspace
export {
  predictLNN, trainDryRun, startTraining, cancelJob,
  recordAuditLog, listModels,
} from './workspace/api'
export type { LNNPredictRequest, LNNPredictResponse, LNNTrainingConfig } from './workspace/api'

// Equipment Monitor
export { fetchEquipment, fetchStats, fetchAlarms } from './equipment-monitor/api'

// Material Management
export { fetchMaterials, fetchMaterialStats } from './material-management/api'

// Quality Inspection
export { fetchQualityStats, fetchInspections } from './quality-inspection/api'

// Production Report
export { fetchDashboard, fetchStats as fetchProductionStats, fetchRecords } from './production-report/api'

// Update Center
export { fetchUpdates, applyUpdate, dismissUpdate } from './update-center/api'

// Approval Dashboard
export { fetchDashboard as fetchApprovalDashboard, fetchRequests, decideRequest } from './approval-dashboard/api'

// Goals
export { fetchGoals, createGoal, updateGoalProgress, deleteGoal } from './goals/api'

// Home
export { fetchSystemStatus, fetchActivityBrief } from './home/api'

// Plugin Logs
export { fetchPluginLogs } from './plugin-logs/api'

// Template Market
export { fetchTemplates, fetchTemplate, installTemplate, previewTemplate } from './template-market/api'

// Simulation
export { submitSimulation, getSimulationStatus, getHistory } from './simulation/api'

// Cost Dashboard
export { fetchPolicies, fetchSummary } from './cost-dashboard/api'

// Branch Manager
export { fetchBranches, createBranch, mergeBranch } from './branch-manager/api'

// Task History
export { fetchJobs, resubmitTraining, resubmitInference } from './task-history/api'
