import re, json

path = r"C:\Users\Lenovo\Desktop\灵境制造（上线版）\engineering\src\views\WorkflowPanel.vue"
src = open(path, 'r', encoding='utf-8').read()

# 1) Add imports
old_imp = "import { useWorkflow } from '@/composables/useWorkflow'\nimport type { WorkflowSpec, TaskStatus, WorkflowEvent } from '@/contracts/task'"
new_imp = old_imp + "\nimport { useDagLayout } from '@/composables/useDagLayout'\nimport { getTaskStatusTagType, getTaskStatusLabel } from '@/utils/statusHelpers'"
src = src.replace(old_imp, new_imp, 1)

# 2) Replace statusTagType/statusLabel with thin wrappers around utils
old = "function statusTagType(s?: string | null) {\n  switch (s) {\n    case 'completed': return 'success'\n    case 'failed': return 'danger'\n    case 'cancelled': return 'info'\n    case 'running': return 'primary'\n    case 'queued':\n    case 'pending': return 'warning'\n    case 'skipped': return 'info'\n    default: return 'info'\n  }\n}\n\nfunction statusLabel(s?: string | null): string {\n  const map: Record<string, string> = {\n    pending: t('workflowPanel.statusPending'),\n    queued: t('workflowPanel.statusQueued'),\n    running: t('workflowPanel.statusRunning'),\n    completed: t('workflowPanel.statusCompleted'),\n    failed: t('workflowPanel.statusFailed'),\n    cancelled: t('workflowPanel.statusCancelled'),\n    skipped: t('workflowPanel.statusSkipped'),\n  }\n  return map[s || ''] ?? s ?? '-'\n}"
new = "function statusTagType(s?: string | null) { return getTaskStatusTagType(s) }\nfunction statusLabel(s?: string | null): string { return getTaskStatusLabel(s) ?? s ?? '-' }"
src = src.replace(old, new, 1)

# 3) Compact SAMPLE_TOOL_WEAR_SPEC JSON version
old_spec = '''const SAMPLE_TOOL_WEAR_SPEC: WorkflowSpec = {
  name: '刀具磨损预测流水线',
  version: '1.0.0',
  nodes: [
    { node_id: 'load_dataset', task_type: 'dataset_loader', params: { loader_type: 'phm2010' }, inputs: {}, retry: 0, timeout_seconds: 600 },
    { node_id: 'train_model', task_type: 'ltc_trainer', params: { model_type: 'ltc', epochs: 50 }, inputs: { train_split: '${load_dataset.train_split}' }, retry: 1, timeout_seconds: 7200 },
    { node_id: 'evaluate_model', task_type: 'model_evaluator', params: { metrics: ['mae', 'r2'] }, inputs: { test_split: '${load_dataset.test_split}', trained_model: '${train_model.model_artifact}' }, retry: 0, timeout_seconds: 1800 },
    { node_id: 'generate_report', task_type: 'report_generator', params: { template: 'tool_wear_evaluation.md' }, inputs: { metrics: '${evaluate_model.metrics_artifact}' }, retry: 0, timeout_seconds: 600 },
  ],
  edges: [
    { upstream: 'load_dataset', downstream: 'train_model' },
    { upstream: 'train_model', downstream: 'evaluate_model' },
    { upstream: 'evaluate_model', downstream: 'generate_report' },
  ],
  inputs: {},
  outputs: { wear_report: '${generate_report.report_artifact}' },
  metadata: { max_concurrent: 2, tags: ['tool_wear', 'ltc'] },
}'''
new_spec = "const SAMPLE_TOOL_WEAR_SPEC: WorkflowSpec = JSON.parse('" + json.dumps({"name":"刀具磨损预测流水线","version":"1.0.0","nodes":[{"node_id":"load_dataset","task_type":"dataset_loader","params":{"loader_type":"phm2010"},"inputs":{},"retry":0,"timeout_seconds":600},{"node_id":"train_model","task_type":"ltc_trainer","params":{"model_type":"ltc","epochs":50},"inputs":{"train_split":"${load_dataset.train_split}"},"retry":1,"timeout_seconds":7200},{"node_id":"evaluate_model","task_type":"model_evaluator","params":{"metrics":["mae","r2"]},"inputs":{"test_split":"${load_dataset.test_split}","trained_model":"${train_model.model_artifact}"},"retry":0,"timeout_seconds":1800},{"node_id":"generate_report","task_type":"report_generator","params":{"template":"tool_wear_evaluation.md"},"inputs":{"metrics":"${evaluate_model.metrics_artifact}"},"retry":0,"timeout_seconds":600}],"edges":[{"upstream":"load_dataset","downstream":"train_model"},{"upstream":"train_model","downstream":"evaluate_model"},{"upstream":"evaluate_model","downstream":"generate_report"}],"inputs":{},"outputs":{"wear_report":"${generate_report.report_artifact}"},"metadata":{"max_concurrent":2,"tags":["tool_wear","ltc"]}}, ensure_ascii=False) + "')"
src = src.replace(old_spec, new_spec, 1)

# 4) Replace dagLayout computed block (the large Kahn algorithm) with composable call
old_dag_start = "const dagLayout = computed(() => {\n  const spec = currentSpec.value\n  if (!spec || spec.nodes.length === 0) {\n    return { nodes: [] as LayoutNode[], edges: [] as LayoutEdge[], width: 0, height: 0 }\n  }\n\n  // 构建邻接表 + 入度"
old_dag_end = "function isEdgeActive(edge: LayoutEdge): boolean {\n  // 当 upstream 节点 completed 且 downstream 节点已启动时高亮\n  const u = getNodeStatus(edge.upstream)\n  const d = getNodeStatus(edge.downstream)\n  return u === 'completed' && d !== 'pending'\n}"

idx_start = src.index(old_dag_start)
idx_end = src.index(old_dag_end) + len(old_dag_end)

new_dag = "const dagLayout = useDagLayout(() => currentSpec.value)\n\nfunction isEdgeActiveLocal(edge: ReturnType<typeof dagLayout>['value']['edges'][0]): boolean {\n  const u = getNodeStatus(edge.upstream)\n  const d = getNodeStatus(edge.downstream)\n  return u === 'completed' && d !== 'pending'\n}"
src = src[:idx_start] + new_dag + src[idx_end:]

# 5) Remove LayoutNode/LayoutEdge interfaces (now in composable)
old_iface = "interface LayoutNode {\n  node_id: string\n  task_type: string\n  x: number\n  y: number\n  layer: number\n}\n\ninterface LayoutEdge {\n  path: string\n  upstream: string\n  downstream: string\n}\n\n"
src = src.replace(old_iface, "", 1)

# 6) Rename template usage of isEdgeActive
src = src.replace(":class=\"['dag-edge', { active: isEdgeActive(edge) }]\"", ":class=\"['dag-edge', { active: isEdgeActiveLocal(edge) }]\"")

open(path, 'w', encoding='utf-8').write(src)
print("OK")
