import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import type { WorkflowSpec } from '@/contracts/task'

interface UseWorkflowSubmitOptions {
  currentRunId: () => string | null
  workflows: { value: Array<{ id: string; spec?: WorkflowSpec; owner_id?: string }> }
  builtinTemplates: { value: Array<{ name: string; spec: WorkflowSpec }> }
  submitWorkflow: (params: { spec: WorkflowSpec; owner_id?: string }) => Promise<string>
  resumeCurrentWorkflow: (runId: string, params: { spec: WorkflowSpec; owner_id?: string }) => Promise<string>
  validate: (spec: WorkflowSpec) => Promise<{ valid: boolean; node_count?: number; edge_count?: number }>
  onSuccess: () => Promise<void>
}

export function useWorkflowSubmit(opts: UseWorkflowSubmitOptions) {
  const { t } = useI18n()

  const dialogVisible = ref(false)
  const mode = ref<'submit' | 'resume'>('submit')
  const form = ref({ templateName: '', specYaml: '', ownerId: '' })
  const validating = ref(false)
  const submitting = ref(false)

  const title = computed(() => mode.value === 'submit' ? t('workflowPanel.dialogSubmitTitle') : t('workflowPanel.dialogResumeTitle'))
  const confirmText = computed(() => mode.value === 'submit' ? t('workflowPanel.btnSubmitConfirm') : t('workflowPanel.btnResumeConfirm'))

  function openSubmit() {
    mode.value = 'submit'
    form.value = { templateName: '', specYaml: '', ownerId: '' }
    dialogVisible.value = true
  }

  function openResume() {
    const runId = opts.currentRunId()
    if (!runId) return
    mode.value = 'resume'
    const wf = opts.workflows.value.find(w => w.id === runId)
    form.value = wf?.spec
      ? { templateName: '', specYaml: JSON.stringify(wf.spec, null, 2), ownerId: wf.owner_id ?? '' }
      : { templateName: '', specYaml: '', ownerId: '' }
    dialogVisible.value = true
  }

  function selectTemplate(name: string) {
    if (!name) return
    const tpl = opts.builtinTemplates.value.find(t => t.name === name)
    if (tpl) form.value.specYaml = JSON.stringify(tpl.spec, null, 2)
  }

  function parseSpec(): WorkflowSpec | null {
    const text = form.value.specYaml.trim()
    if (!text) { ElMessage.warning(t('workflowPanel.msgSpecEmpty')); return null }
    try {
      const obj = JSON.parse(text) as WorkflowSpec
      if (!obj.name || !obj.nodes || !obj.edges) { ElMessage.error(t('workflowPanel.msgSpecInvalid')); return null }
      return obj
    } catch { ElMessage.error(t('workflowPanel.msgSpecParseError')); return null }
  }

  async function doValidate() {
    const spec = parseSpec()
    if (!spec) return
    validating.value = true
    try {
      const r = await opts.validate(spec)
      if (r.valid) ElMessage.success(t('workflowPanel.msgValidateSuccess').replace('{nodes}', String(r.node_count)).replace('{edges}', String(r.edge_count)))
      else ElMessage.warning(t('workflowPanel.msgValidateFailed'))
    } catch (e) {
      console.warn('[WorkflowPanel] validate failed:', e)
      ElMessage.error('Validation failed — check console for details')
    } finally { validating.value = false }
  }

  async function doSubmit() {
    const spec = parseSpec()
    if (!spec) return
    submitting.value = true
    try {
      if (mode.value === 'submit') {
        const runId = await opts.submitWorkflow({ spec, owner_id: form.value.ownerId || undefined })
        ElMessage.success(t('workflowPanel.msgSubmitSuccess').replace('{id}', runId.slice(0, 12)))
      } else {
        const runId = opts.currentRunId()
        if (!runId) { ElMessage.warning(t('workflowPanel.msgNoCurrentRun')); return }
        const newId = await opts.resumeCurrentWorkflow(runId, { spec, owner_id: form.value.ownerId || undefined })
        ElMessage.success(t('workflowPanel.msgResumeSuccess').replace('{id}', newId.slice(0, 12)))
      }
      dialogVisible.value = false
      await opts.onSuccess()
    } catch (e) {
      console.warn('[WorkflowPanel] submit failed:', e)
      ElMessage.error('Submit failed — check console for details')
    } finally { submitting.value = false }
  }

  return { dialogVisible, mode, form, validating, submitting, title, confirmText, openSubmit, openResume, selectTemplate, doValidate, doSubmit }
}
