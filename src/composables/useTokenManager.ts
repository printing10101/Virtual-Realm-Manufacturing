import { ref, reactive, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'

interface NewTokenForm {
  scopes: string[]
  expires_in: number | null
  no_expiry: boolean
  paper_only: boolean
}

export function useTokenManager() {
  const agentTokens = ref<any[]>([])
  const loadingTokens = ref(false)
  const creatingToken = ref(false)
  const revokingT = ref(false)
  const showCreateTokenDialog = ref(false)
  const showCreatedTokenDialog = ref(false)
  const createdToken = ref<any>(null)
  const tokenDetailVisible = ref(false)
  const selectedToken = ref<any>(null)

  const newTokenForm = reactive<NewTokenForm>({
    scopes: ['R'],
    expires_in: null,
    no_expiry: true,
    paper_only: true,
  })

  function handleNoExpiryChange(val: boolean) {
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
      ElMessage.warning('请至少选择一个权限范围')
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
      ElMessage.success('Token 创建成功，请务必保存')
      loadAgentTokens()
    } catch (e: any) {
      ElMessage.error(e.response?.data?.message || '创建Token失败')
    } finally {
      creatingToken.value = false
    }
  }

  async function revokeToken(agentId: string) {
    try {
      await ElMessageBox.confirm('确定要撤销此 Token 吗？撤销后不可恢复。', '警告', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      })

      await axios.delete(`/api/agent/v1/tokens/${agentId}`)
      ElMessage.success('Token 已撤销')
      loadAgentTokens()
    } catch (e: any) {
      if (e !== 'cancel') {
        ElMessage.error('撤销Token失败')
      }
    }
  }

  async function revokeAllTTokens() {
    try {
      await ElMessageBox.confirm(
        '确定要撤销所有包含 T 类权限的 Token 吗？此操作为紧急停止，将立即中止所有 T 类 Token 的访问权限。',
        '紧急停止确认',
        {
          confirmButtonText: '确定撤销',
          cancelButtonText: '取消',
          type: 'error',
        }
      )

      revokingT.value = true
      const res = await axios.post('/api/agent/v1/tokens/revoke-t-all')
      ElMessage.success(`已撤销 ${res.data.data.revoked_count} 个 T 类 Token`)
      loadAgentTokens()
    } catch (e: any) {
      if (e !== 'cancel') {
        ElMessage.error('撤销T类Token失败')
      }
    } finally {
      revokingT.value = false
    }
  }

  function viewTokenDetail(row: any) {
    selectedToken.value = row
    tokenDetailVisible.value = true
  }

  function getScopeType(scope: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
    const types: Record<string, 'success' | 'warning' | 'danger' | 'info' | 'primary'> = {
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
    const names: Record<string, string> = {
      R: '读取',
      W: '写入',
      B: '训练',
      N: '通知',
      C: '管理',
      T: '执行',
    }
    return names[scope] || scope
  }

  function copyTokenToClipboard(token: string) {
    if (token && navigator.clipboard) {
      navigator.clipboard.writeText(token).then(() => {
        ElMessage.success('Token 已复制到剪贴板')
      }).catch(() => {
        ElMessage.error('复制失败，请手动复制')
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
