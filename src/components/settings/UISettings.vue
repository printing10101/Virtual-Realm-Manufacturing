<template>
  <div>
    <el-card class="agent-token-card">
      <template #header>
        <div class="card-header">
          <span>{{ $t('settings.agentTokenManage') }}</span>
          <div class="header-actions">
            <el-button
              size="small"
              type="danger"
              :loading="revokingT"
              @click="revokeAllTTokens"
            >
              {{ $t('settings.revokeAllT') }}
            </el-button>
            <el-button
              size="small"
              type="primary"
              @click="showCreateTokenDialog = true"
            >
              {{ $t('settings.createToken') }}
            </el-button>
          </div>
        </div>
      </template>

      <el-alert
        :title="$t('settings.agentTokenInfo')"
        type="info"
        :closable="true"
        show-icon
        style="margin-bottom: 16px;"
      >
        <div>
          <p>{{ $t('settings.agentTokenDesc1') }}</p>
          <p>{{ $t('settings.agentTokenDesc2') }}</p>
          <p><strong>{{ $t('settings.db') }}</strong>{{ $t('settings.agentTokenDesc3') }}</p>
        </div>
      </el-alert>

      <el-table
        v-loading="loadingTokens"
        :data="agentTokens"
        style="width: 100%;"
      >
        <el-table-column
          prop="agent_id"
          label="Agent ID"
          width="280"
        >
          <template #default="{ row }">
            <span class="mono-text">{{ row.agent_id.slice(0, 8) }}...</span>
          </template>
        </el-table-column>
        <el-table-column
          prop="token_prefix"
          label="Token"
          width="160"
        >
          <template #default="{ row }">
            <el-tag
              size="small"
              type="info"
            >
              {{ row.token_prefix.slice(0, 16) }}...
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          :label="$t('settings.scopePermission')"
          width="180"
        >
          <template #default="{ row }">
            <el-tag
              v-for="scope in row.scopes"
              :key="scope"
              size="small"
              :type="getScopeType(scope)"
              style="margin-right: 4px;"
            >
              {{ getScopeName(scope) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          prop="paper_only"
          :label="$t('settings.paperOnly')"
          width="110"
        >
          <template #default="{ row }">
            <el-tag
              :type="row.paper_only ? 'warning' : 'success'"
              size="small"
            >
              {{ row.paper_only ? $t('settings.simulateMode') : $t('settings.realExecute') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          prop="is_active"
          :label="$t('common.status')"
          width="90"
        >
          <template #default="{ row }">
            <el-tag
              :type="row.is_active ? 'success' : 'info'"
              size="small"
            >
              {{ row.is_active ? $t('common.active') : $t('common.revoked') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          :label="$t('common.operation')"
          width="120"
        >
          <template #default="{ row }">
            <el-button
              type="danger"
              link
              size="small"
              :disabled="!row.is_active"
              @click="revokeToken(row.agent_id)"
            >
              {{ $t('settings.revoke') }}
            </el-button>
            <el-button
              type="primary"
              link
              size="small"
              @click="viewTokenDetail(row as AgentToken)"
            >
              {{ $t('common.detail') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="showCreateTokenDialog"
      :title="$t('settings.createTokenTitle')"
      width="500px"
    >
      <el-form
        :model="newTokenForm"
        label-width="120px"
      >
        <el-form-item :label="$t('settings.scopePermission')">
          <el-checkbox-group v-model="newTokenForm.scopes">
            <el-checkbox value="R">
              R - {{ $t('settings.getScopeName_R') }}
            </el-checkbox>
            <el-checkbox value="W">
              W - {{ $t('settings.getScopeName_W') }}
            </el-checkbox>
            <el-checkbox value="B">
              B - {{ $t('settings.getScopeName_B') }}
            </el-checkbox>
            <el-checkbox value="N">
              N - {{ $t('settings.getScopeName_N') }}
            </el-checkbox>
            <el-checkbox value="C">
              C - {{ $t('settings.getScopeName_C') }}
            </el-checkbox>
            <el-checkbox value="T">
              T - {{ $t('settings.getScopeName_T') }}
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item :label="$t('settings.validitySeconds')">
          <el-input-number
            v-model="newTokenForm.expires_in"
            :min="3600"
            :max="31536000"
            :step="3600"
          />
          <el-checkbox
            v-model="newTokenForm.no_expiry"
            style="margin-left: 12px;"
            @change="handleNoExpiryChange"
          >
            {{ $t('settings.noExpiry') }}
          </el-checkbox>
        </el-form-item>
        <el-form-item label="Paper-Only">
          <el-switch v-model="newTokenForm.paper_only" />
          <span style="margin-left: 8px; font-size: 12px; color: var(--text-secondary);">
            {{ newTokenForm.paper_only ? $t('settings.paperOnlyHint') : $t('settings.realExecuteHint') }}
          </span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateTokenDialog = false">
          {{ $t('common.cancel') }}
        </el-button>
        <el-button
          type="primary"
          :loading="creatingToken"
          @click="createAgentToken"
        >
          {{ $t('settings.createToken') }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="showCreatedTokenDialog"
      :title="$t('settings.importantNotice')"
      width="600px"
    >
      <el-alert
        :title="$t('settings.importantNotice')"
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom: 16px;"
      >
        <p>{{ $t('settings.importantNoticeMsg') }}</p>
      </el-alert>

      <el-descriptions
        :column="1"
        border
      >
        <el-descriptions-item label="Agent ID">
          {{ createdToken?.agent_id }}
        </el-descriptions-item>
        <el-descriptions-item label="Token">
          <div style="display: flex; align-items: center; gap: 8px;">
            <code style="word-break: break-all; font-size: 12px;">{{ createdToken?.token }}</code>
            <el-button
              size="small"
              @click="copyTokenToClipboard(createdToken?.token)"
            >
              {{ $t('common.export') }}
            </el-button>
          </div>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('settings.scopePermission')">
          <el-tag
            v-for="scope in createdToken?.scopes"
            :key="scope"
            size="small"
            :type="getScopeType(scope)"
            style="margin-right: 4px;"
          >
            {{ getScopeName(scope) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('settings.paperOnly')">
          <el-tag :type="createdToken?.paper_only ? 'warning' : 'success'">
            {{ createdToken?.paper_only ? $t('settings.simulateMode') : $t('settings.realExecute') }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('settings.expireTime')">
          {{ createdToken?.expires_at ? formatTimestamp(createdToken.expires_at * 1000) : $t('settings.noExpiry') }}
        </el-descriptions-item>
      </el-descriptions>

      <template #footer>
        <el-button
          type="primary"
          @click="showCreatedTokenDialog = false"
        >
          {{ $t('settings.iHaveSaved') }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="tokenDetailVisible"
      :title="$t('settings.tokenDetail')"
      width="50%"
    >
      <el-descriptions
        v-if="selectedToken"
        :column="1"
        border
      >
        <el-descriptions-item label="Agent ID">
          {{ selectedToken.agent_id }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('settings.tokenPrefix')">
          {{ selectedToken.token_prefix }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('settings.scopePermission')">
          <el-tag
            v-for="scope in selectedToken.scopes"
            :key="scope"
            size="small"
            :type="getScopeType(scope)"
            style="margin-right: 4px;"
          >
            {{ getScopeName(scope) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('settings.createTime')">
          {{ formatTimestamp(selectedToken.created_at * 1000) }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('settings.expireTime')">
          {{ selectedToken.expires_at ? formatTimestamp(selectedToken.expires_at * 1000) : $t('settings.noExpiry') }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('settings.paperOnly')">
          <el-tag :type="selectedToken.paper_only ? 'warning' : 'success'">
            {{ selectedToken.paper_only ? $t('settings.simulateMode') : $t('settings.realExecute') }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('common.status')">
          <el-tag :type="selectedToken.is_active ? 'success' : 'info'">
            {{ selectedToken.is_active ? $t('common.active') : $t('common.revoked') }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useSettings } from '@/composables/useSettings'
import { useTokenManager, type AgentToken } from '@/composables/useTokenManager'

const { formatTimestamp } = useSettings()

const {
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
} = useTokenManager()

onMounted(() => {
  loadAgentTokens()
})
</script>

<style scoped>
.agent-token-card {
  margin-bottom: 24px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.mono-text {
  font-family: monospace;
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
