/**
 * Agent Token管理
 * 处理Token的创建、吊销、查看等完整生命周期
 */

import { ref, reactive, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import http from '@/utils/http'

export interface AgentToken {
  agent_id: string
  token_prefix: string
  scopes: string[]
  paper_only: boolean
  is_active: boolean
  created_at: number
  expires_at: number | null
}

export interface CreatedTokenData {
  agent_id: string
  token: string
  scopes: string[]
  paper_only: boolean
  expires_at: number | null
}

export interface NewTokenForm {
  scopes: string[]
  expires_in: number | null
  no_expiry: boolean
  paper_only: boolean
}

export type ScopeTagType = 'success' | 'warning' | 'danger' | 'info' | 'primary'

export interface TokenManagerReturn {
  agentTokens: ReturnType<typeof ref<AgentToken[]>>
  loadingTokens: ReturnType<typeof ref<boolean>>
  creatingToken: ReturnType<typeof ref<boolean>>
  revokingT: ReturnType<typeof ref<boolean>>
  showCreateTokenDialog: ReturnType<typeof ref<boolean>>
  showCreatedTokenDialog: ReturnType<typeof ref<boolean>>
  createdToken: ReturnType<typeof ref<CreatedTokenData | null>>
  tokenDetailVisible: ReturnType<typeof ref<boolean>>
  selectedToken: ReturnType<typeof ref<AgentToken | null>>
  newTokenForm: NewTokenForm
  handleNoExpiryChange: (val: boolean | string | number) => void
  loadAgentTokens: () => Promise<void>
  createAgentToken: () => Promise<void>
  revokeToken: (agentId: string) => Promise<void>
  revokeAllTTokens: () => Promise<void>
  viewTokenDetail: (row: AgentToken) => void
  getScopeType: (scope: string) => ScopeTagType
  getScopeName: (scope: string) => string
  copyTokenToClipboard: (token: string | undefined) => void
}

const SCOPE_TYPES: Record<string, ScopeTagType> = {
  R: 'success',
  W: 'primary',
  B: 'warning',
  N: 'info',
  C: 'danger',
  T: 'danger',
}

/** i18n scope名称的键名映射 */
const SCOPE_I18N_KEYS: Record<string, string> = {
  R: 'settings.getScopeName_R',
  W: 'settings.getScopeName_W',
  B: 'settings.getScopeName_B',
  N: 'settings.getScopeName_N',
  C: 'settings.getScopeName_C',
  T: 'settings.getScopeName_T',
}

export function useTokenManager(): TokenManagerReturn {
  const { t } = useI18n()

  const agentTokens = ref<AgentToken[]>([])
  const loadingTokens = ref(false)
  const creatingToken = ref(false)
  const revokingT = ref(false)
  const showCreateTokenDialog = ref(false)
  const showCreatedTokenDialog = ref(false)
  const createdToken = ref<CreatedTokenData | null>(null)
  const tokenDetailVisible = ref(false)
  const selectedToken = ref<AgentToken | null>(null)

  const newTokenForm = reactive<NewTokenForm>({
    scopes: ['R'],
    expires_in: null,
    no_expiry: true,
    paper_only: true,
  })

  /**
   * 处理无过期时间选项变更
   * @param val - 开关状态值
   */
  function handleNoExpiryChange(val: boolean | string | number) {
    if (val === true) {
      newTokenForm.expires_in = null
    } else {
      newTokenForm.expires_in = 86400
    }
  }

  async function loadAgentTokens() {
    loadingTokens.value = true
    try {
      const res = await http.get('/api/agent/v1/tokens')
      agentTokens.value = res.data.data.tokens
    } catch (e: unknown) {
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
      const payload: Record<string, unknown> = {
        scopes: newTokenForm.scopes,
        paper_only: newTokenForm.paper_only,
      }
      if (!newTokenForm.no_expiry && newTokenForm.expires_in) {
        payload.expires_in = newTokenForm.expires_in
      }

      const res = await http.post('/api/agent/v1/tokens', payload)
      createdToken.value = res.data.data
      showCreatedTokenDialog.value = true
      showCreateTokenDialog.value = false
      ElMessage.success(t('settings.tokenCreatedSuccess'))
      loadAgentTokens()
    } catch (e: unknown) {
      const response = (e as { response?: { data?: { message?: string } } })?.response
      const msg = response?.data?.message || t('settings.saveFailed')
      ElMessage.error(msg)
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

      await http.delete(`/api/agent/v1/tokens/${agentId}`)
      ElMessage.success(t('settings.revokeSuccess'))
      loadAgentTokens()
    } catch (e: unknown) {
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
      const res = await http.post('/api/agent/v1/tokens/revoke-t-all')
      ElMessage.success(
        t('settings.revokeSuccessCount', { count: res.data.data.revoked_count })
      )
      loadAgentTokens()
    } catch (e: unknown) {
      if (e !== 'cancel') {
        ElMessage.error(t('settings.revokeTFailed'))
      }
    } finally {
      revokingT.value = false
    }
  }

  /**
   * 查看Token详细信息
   * @param row - Token行数据
   */
  function viewTokenDetail(row: AgentToken) {
    selectedToken.value = row
    tokenDetailVisible.value = true
  }

  /**
   * 获取Scope对应的标签颜色类型
   * @param scope - Scope代码
   * @returns 标签颜色类型
   */
  function getScopeType(scope: string): ScopeTagType {
    return SCOPE_TYPES[scope] || 'info'
  }

  /**
   * 获取Scope的国际化显示名称
   * @param scope - Scope代码
   * @returns 翻译后的名称或原始代码
   */
  function getScopeName(scope: string): string {
    const key = SCOPE_I18N_KEYS[scope] || `settings.getScopeName_${scope}`
    return t(key) || scope
  }

  /**
   * 复制Token到剪贴板
   * @param token - 要复制的Token字符串
   */
  function copyTokenToClipboard(token: string | undefined) {
    if (token && navigator.clipboard) {
      navigator.clipboard.writeText(token).then(() => {
        ElMessage.success(t('settings.copySuccess'))
      }).catch(() => {
        ElMessage.error(t('settings.copyFailed'))
      })
    }
  }

  onMounted(() => {
    loadAgentTokens()
  })

  return {
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
