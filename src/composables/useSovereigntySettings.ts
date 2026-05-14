import { reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

interface SovereigntySettings {
  ai_autonomy_level: number
  require_confirmation_for_predict: boolean
  require_confirmation_for_train: boolean
  show_confidence_indicator: boolean
  show_alternatives: boolean
  show_reasoning: boolean
}

export function useSovereigntySettings() {
  const sovereigntySettings = reactive<SovereigntySettings>({
    ai_autonomy_level: 2,
    require_confirmation_for_predict: false,
    require_confirmation_for_train: true,
    show_confidence_indicator: true,
    show_alternatives: true,
    show_reasoning: true,
  })

  const autonomyMarks = {
    0: '0',
    1: '1',
    2: '2',
    3: '3',
    4: '4',
  }

  const autonomyLabels = [
    '完全手动',
    '建议需确认',
    '推荐模式',
    '半自动',
    '全自动',
  ]

  function formatAutonomyLevel(val: number): string {
    return `${val} - ${autonomyLabels[val]}`
  }

  const currentAutonomyDescription = computed(() => {
    const level = sovereigntySettings.ai_autonomy_level
    const descriptions = [
      '完全手动模式：所有AI建议均需用户明确确认后方可执行，系统不进行任何自动决策。',
      '建议需确认模式：AI提供建议，用户在审阅确认后执行。',
      '推荐模式（默认）：AI提供推荐方案，用户可选择接受、修改或拒绝。',
      '半自动模式：高置信度（≥80%）AI建议自动执行，低置信度需用户确认。',
      '全自动模式：AI可直接执行推荐操作，但保留完整操作日志供事后审查和追溯。',
    ]
    return descriptions[level]
  })

  function getAutonomyAlertType(level: number): 'success' | 'warning' | 'info' | 'error' {
    if (level <= 1) return 'info'
    if (level === 2) return 'success'
    if (level === 3) return 'warning'
    return 'error'
  }

  function handleAutonomyChange(val: number) {
    if (val >= 3) {
      sovereigntySettings.require_confirmation_for_predict = false
    }
    if (val >= 4) {
      sovereigntySettings.require_confirmation_for_train = false
    }
  }

  async function saveSovereigntySettings() {
    try {
      localStorage.setItem('ai_sovereignty_settings', JSON.stringify(sovereigntySettings))
      ElMessage.success('AI主权设置已保存')
    } catch (e) {
      ElMessage.error('保存设置失败')
    }
  }

  function resetSovereigntySettings() {
    sovereigntySettings.ai_autonomy_level = 2
    sovereigntySettings.require_confirmation_for_predict = false
    sovereigntySettings.require_confirmation_for_train = true
    sovereigntySettings.show_confidence_indicator = true
    sovereigntySettings.show_alternatives = true
    sovereigntySettings.show_reasoning = true
    ElMessage.info('已恢复默认AI主权设置')
  }

  onMounted(() => {
    const saved = localStorage.getItem('ai_sovereignty_settings')
    if (saved) {
      try {
        const parsed = JSON.parse(saved)
        Object.assign(sovereigntySettings, parsed)
      } catch {
        // ignore parse errors
      }
    }
  })

  return {
    sovereigntySettings,
    autonomyMarks,
    autonomyLabels,
    formatAutonomyLevel,
    currentAutonomyDescription,
    getAutonomyAlertType,
    handleAutonomyChange,
    saveSovereigntySettings,
    resetSovereigntySettings,
  }
}
