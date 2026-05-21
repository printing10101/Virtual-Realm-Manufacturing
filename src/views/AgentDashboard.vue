<template>
  <div class="agent-dashboard">
    <div class="dashboard-header">
      <h2>代理状态监控</h2>
      <div class="dashboard-actions">
        <el-select
          v-model="agentStore.statusFilter"
          placeholder="状态筛选"
          clearable
          style="width: 140px; margin-right: 12px"
          @change="agentStore.fetchAgents()"
        >
          <el-option
            label="全部"
            value=""
          />
          <el-option
            label="空闲"
            value="idle"
          />
          <el-option
            label="忙碌"
            value="busy"
          />
          <el-option
            label="暂停"
            value="paused"
          />
          <el-option
            label="恢复中"
            value="recovering"
          />
          <el-option
            label="错误"
            value="error"
          />
          <el-option
            label="已停止"
            value="stopped"
          />
        </el-select>
        <el-button
          :icon="Refresh"
          :loading="agentStore.loading"
          @click="agentStore.fetchAgents()"
        >
          刷新
        </el-button>
      </div>
    </div>

    <el-row
      :gutter="16"
      class="stats-row"
    >
      <el-col :span="6">
        <el-card
          shadow="hover"
          class="stat-card stat-total"
        >
          <div class="stat-value">
            {{ agentStore.statusStats.total }}
          </div>
          <div class="stat-label">
            代理总数
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card
          shadow="hover"
          class="stat-card stat-active"
        >
          <div class="stat-value">
            {{ agentStore.statusStats.active }}
          </div>
          <div class="stat-label">
            活跃代理
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card
          shadow="hover"
          class="stat-card stat-idle"
        >
          <div class="stat-value">
            {{ agentStore.statusStats.idle }}
          </div>
          <div class="stat-label">
            空闲代理
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card
          shadow="hover"
          class="stat-card stat-error"
        >
          <div class="stat-value">
            {{ agentStore.statusStats.error }}
          </div>
          <div class="stat-label">
            异常代理
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card
      v-loading="agentStore.loading"
      class="agent-table-card"
    >
      <template #header>
        <span>代理列表</span>
      </template>
      <el-table
        :data="agentStore.agents"
        stripe
        style="width: 100%"
      >
        <el-table-column
          prop="agent_id"
          label="代理ID"
          min-width="180"
        >
          <template #default="{ row }">
            <el-link
              type="primary"
              @click="viewDetail(row.agent_id)"
            >
              {{ row.agent_id }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column
          prop="status"
          label="状态"
          width="100"
        >
          <template #default="{ row }">
            <el-tag
              :type="agentStore.statusTagType(row.status)"
              size="small"
            >
              {{ agentStore.statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          prop="current_task_id"
          label="当前任务"
          min-width="160"
        >
          <template #default="{ row }">
            <span v-if="row.current_task_id">{{ row.current_task_id }}</span>
            <span
              v-else
              class="text-muted"
            >-</span>
          </template>
        </el-table-column>
        <el-table-column
          label="最后心跳"
          width="180"
        >
          <template #default="{ row }">
            {{ agentStore.formatTime(row.last_heartbeat) }}
          </template>
        </el-table-column>
        <el-table-column
          label="更新时间"
          width="180"
        >
          <template #default="{ row }">
            {{ agentStore.formatTime(row.updated_at) }}
          </template>
        </el-table-column>
        <el-table-column
          label="操作"
          width="280"
          fixed="right"
        >
          <template #default="{ row }">
            <el-button-group>
              <el-button
                size="small"
                type="primary"
                @click="viewDetail(row.agent_id)"
              >
                详情
              </el-button>
              <el-button
                size="small"
                type="success"
                :disabled="row.status !== 'idle' && row.status !== 'error'"
                @click="handleResume(row.agent_id)"
              >
                恢复
              </el-button>
              <el-button
                size="small"
                :type="row.status === 'busy' ? 'warning' : 'info'"
                @click="toggleHeartbeat(row)"
              >
                {{ row.status === 'busy' ? '停心跳' : '启心跳' }}
              </el-button>
              <el-popconfirm
                title="确定要删除该代理状态吗？"
                @confirm="handleDelete(row.agent_id)"
              >
                <template #reference>
                  <el-button
                    size="small"
                    type="danger"
                  >
                    删除
                  </el-button>
                </template>
              </el-popconfirm>
            </el-button-group>
          </template>
        </el-table-column>
      </el-table>
      <el-empty
        v-if="agentStore.agents.length === 0 && !agentStore.loading"
        description="暂无代理数据"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'
import { useAgentStore } from '@/stores/agents'

const agentStore = useAgentStore()
const router = useRouter()

onMounted(() => {
  agentStore.fetchAgents()
})

function viewDetail(agentId: string) {
  router.push({ name: 'agent-detail', params: { agentId } })
}

async function handleResume(agentId: string) {
  try {
    const result = await agentStore.resumeAgent(agentId)
    ElMessage.success(`代理 ${agentId} 恢复成功 (${result.action})`)
    agentStore.fetchAgents()
  } catch (e: any) {
    ElMessage.error(`恢复失败: ${e.message}`)
  }
}

async function toggleHeartbeat(row: any) {
  try {
    if (row.status === 'busy') {
      await agentStore.stopHeartbeat(row.agent_id)
      ElMessage.success(`已停止 ${row.agent_id} 心跳`)
    } else {
      await agentStore.startHeartbeat(row.agent_id)
      ElMessage.success(`已启动 ${row.agent_id} 心跳`)
    }
    agentStore.fetchAgents()
  } catch (e: any) {
    ElMessage.error(`操作失败: ${e.message}`)
  }
}

async function handleDelete(agentId: string) {
  try {
    await agentStore.deleteAgent(agentId)
    ElMessage.success(`已删除代理 ${agentId}`)
  } catch (e: any) {
    ElMessage.error(`删除失败: ${e.message}`)
  }
}
</script>

<style scoped>
.agent-dashboard {
  max-width: 1400px;
  margin: 0 auto;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.dashboard-header h2 {
  margin: 0;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  text-align: center;
  border-radius: 8px;
}

.stat-value {
  font-size: 2rem;
  font-weight: 700;
  line-height: 1.2;
}

.stat-label {
  margin-top: 4px;
  font-size: 0.85rem;
  color: #909399;
}

.stat-total .stat-value { color: #409eff; }
.stat-active .stat-value { color: #67c23a; }
.stat-idle .stat-value { color: #909399; }
.stat-error .stat-value { color: #f56c6c; }

.text-muted {
  color: #c0c4cc;
}
</style>
