import { ref, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import axios from 'axios'
import { invoke } from '@tauri-apps/api/core'
import { setLocale, type SupportedLocale } from '@/i18n'

export function useSettings() {
  const { t } = useI18n()

  const currentLocale = ref<SupportedLocale>(
    (localStorage.getItem('app_locale') as SupportedLocale) || 'zh-CN'
  )

  function handleLocaleChange(locale: string) {
    const setter = (window as any).__setLocale
    if (setter) {
      setter(locale as SupportedLocale)
    } else {
      setLocale(locale as SupportedLocale)
    }
    currentLocale.value = locale as SupportedLocale
  }

  function formatTimestamp(ts: number): string {
    const locale = currentLocale.value === 'en' ? 'en-US' : 'zh-CN'
    return new Date(ts).toLocaleString(locale)
  }

  const exportingLogs = ref(false)
  const exportProgress = ref(0)
  const exportResult = ref<any>(null)

  async function exportSystemLogs(exportDays: number) {
    exportingLogs.value = true
    exportProgress.value = 0
    exportResult.value = null

    const progressTimer = setInterval(() => {
      if (exportProgress.value < 90) {
        exportProgress.value += Math.floor(Math.random() * 15) + 5
        if (exportProgress.value > 90) exportProgress.value = 90
      }
    }, 400)

    try {
      const result = await invoke<any>('export_logs_cmd', {
        days: exportDays,
      })
      exportProgress.value = 100
      exportResult.value = {
        success: result.success,
        message: result.message,
        outputPath: result.output_path,
        file_count: result.file_count,
        total_size_bytes: result.total_size_bytes,
      }

      if (result.success && result.output_path) {
        ElMessage.success(t('settings.exportSuccess'))
      } else if (result.file_count === 0) {
        ElMessage.info(t('settings.noLogsToExport'))
      }
    } catch (e: any) {
      exportResult.value = {
        success: false,
        message: typeof e === 'string' ? e : (e.message || t('settings.exportFailed')),
        outputPath: null,
      }
      ElMessage.error(t('settings.exportFailed'))
    } finally {
      clearInterval(progressTimer)
      exportProgress.value = 100
      setTimeout(() => {
        exportingLogs.value = false
      }, 500)
    }
  }

  const agentTokens = ref<any[]>([])
  const loadingTokens = ref(false)
  const creatingToken = ref(false)
  const revokingT = ref(false)
  const showCreateTokenDialog = ref(false)
  const showCreatedTokenDialog = ref(false)
  const createdToken = ref<any>(null)
  const tokenDetailVisible = ref(false)
  const selectedToken = ref<any>(null)

  const newTokenForm = reactive({
    scopes: ['R'] as string[],
    expires_in: null as number | null,
    no_expiry: true,
    paper_only: true,
  })

  function handleNoExpiryChange(val: string | number | boolean) {
    if (val) {
      newTokenForm.expires_in = null
    } else {
      newTokenForm.expires_in = 86400
    }
  }

  async function loadAgentTokens() {
    loadingTokens.value = true
    try {
      const res = await axios.get('/api/agent/v1/tokens')
      agentTokens.value = res.data.data.tokens
    } catch (e) {
      console.warn('Failed to load agent tokens:', e)
    } finally {
      loadingTokens.value = false
    }
  }

  async function createAgentToken() {
    if (newTokenForm.scopes.length === 0) {
      ElMessage.warning(t('settings.selectScopeHint'))
      return
    }

    creatingToken.value = true
    try {
      const payload: any = {
        scopes: newTokenForm.scopes,
        paper_only: newTokenForm.paper_only,
      }
      if (!newTokenForm.no_expiry && newTokenForm.expires_in) {
        payload.expires_in = newTokenForm.expires_in
      }

      const res = await axios.post('/api/agent/v1/tokens', payload)
      createdToken.value = res.data.data
      showCreatedTokenDialog.value = true
      showCreateTokenDialog.value = false
      ElMessage.success(t('settings.tokenCreatedSuccess'))
      loadAgentTokens()
    } catch (e: any) {
      ElMessage.error(e.response?.data?.message || t('settings.saveFailed'))
    } finally {
      creatingToken.value = false
    }
  }

  async function revokeToken(agentId: string) {
    try {
      await ElMessageBox.confirm(
        t('settings.revokeConfirmMsg'),
        t('settings.revokeConfirmTitle'),
        {
          confirmButtonText: t('common.confirm'),
          cancelButtonText: t('common.cancel'),
          type: 'warning',
        }
      )

      await axios.delete(`/api/agent/v1/tokens/${agentId}`)
      ElMessage.success(t('settings.revokeSuccess'))
      loadAgentTokens()
    } catch (e: any) {
      if (e !== 'cancel') {
        ElMessage.error(t('settings.revokeFailed'))
      }
    }
  }

  async function revokeAllTTokens() {
    try {
      await ElMessageBox.confirm(
        t('settings.emergencyStopMsg'),
        t('settings.emergencyStopTitle'),
        {
          confirmButtonText: t('settings.emergencyStopConfirm'),
          cancelButtonText: t('common.cancel'),
          type: 'error',
        }
      )

      revokingT.value = true
      const res = await axios.post('/api/agent/v1/tokens/revoke-t-all')
      ElMessage.success(
        t('settings.revokeSuccessCount', { count: res.data.data.revoked_count })
      )
      loadAgentTokens()
    } catch (e: any) {
      if (e !== 'cancel') {
        ElMessage.error(t('settings.revokeTFailed'))
      }
    } finally {
      revokingT.value = false
    }
  }

  function viewTokenDetail(row: any) {
    selectedToken.value = row
    tokenDetailVisible.value = true
  }

  function getScopeType(
    scope: string
  ): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
    const types: Record<
      string,
      'success' | 'warning' | 'danger' | 'info' | 'primary'
    > = {
      R: 'success',
      W: 'primary',
      B: 'warning',
      N: 'info',
      C: 'danger',
      T: 'danger',
    }
    return types[scope] || 'info'
  }

  function getScopeName(scope: string): string {
    const key = `settings.getScopeName_${scope}` as const
    return t(key as any) || scope
  }

  function copyTokenToClipboard(token: string) {
    if (token && navigator.clipboard) {
      navigator.clipboard.writeText(token).then(() => {
        ElMessage.success(t('settings.copySuccess'))
      }).catch(() => {
        ElMessage.error(t('settings.copyFailed'))
      })
    }
  }

  return {
    currentLocale,
    handleLocaleChange,
    formatTimestamp,
    exportingLogs,
    exportProgress,
    exportResult,
    exportSystemLogs,
    agentTokens,
    loadingTokens,
    creatingToken,
    revokingT,
    showCreateTokenDialog,
    showCreatedTokenDialog,
    createdToken,
    tokenDetailVisible,
    selectedToken,
    newTokenForm,
    handleNoExpiryChange,
    loadAgentTokens,
    createAgentToken,
    revokeToken,
    revokeAllTTokens,
    viewTokenDetail,
    getScopeType,
    getScopeName,
    copyTokenToClipboard,
  }
}