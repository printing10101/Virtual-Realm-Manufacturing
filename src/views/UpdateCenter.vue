<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { formatSecondsTimestamp } from '@/utils/formatters'

const notifications = ref<any[]>([])
const loading = ref(false)
const statusFilter = ref('pending')
const previewDialog = ref(false)
const previewData = ref<any>(null)
const projectId = 'default'

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const filteredNotifications = computed(() => {
  if (statusFilter.value === 'all') return notifications.value
  return notifications.value.filter(n => n.status === statusFilter.value)
})

type TagType = 'success' | 'primary' | 'info' | 'warning' | 'danger'

function priorityTag(priority: string): { text: string; type: TagType } {
  const map: Record<string, { text: string; type: TagType }> = {
    optional: { text: '可选', type: 'info' },
    recommended: { text: '推荐', type: 'primary' },
    critical: { text: '关键', type: 'danger' },
  }
  return map[priority] || { text: priority, type: 'info' }
}

function statusTag(status: string): { text: string; type: TagType } {
  const map: Record<string, { text: string; type: TagType }> = {
    pending: { text: '待处理', type: 'warning' },
    applied: { text: '已应用', type: 'success' },
    dismissed: { text: '已忽略', type: 'info' },
  }
  return map[status] || { text: status, type: 'info' }
}

async function fetchNotifications() {
  loading.value = true
  try {
    const res = await fetch(`${API_BASE}/templates/updates/${projectId}?status=${statusFilter.value === 'all' ? '' : statusFilter.value}`)
    const data = await res.json()
    if (data.code === 'SUCCESS') notifications.value = data.data
  } catch { /* empty */ } finally {
    loading.value = false
  }
}

async function applyUpdate(id: string) {
  try {
    await fetch(`${API_BASE}/templates/updates/apply/${id}`, { method: 'POST' })
    fetchNotifications()
  } catch { /* empty */ }
}

async function dismissUpdate(id: string) {
  try {
    await fetch(`${API_BASE}/templates/updates/dismiss/${id}`, { method: 'POST' })
    fetchNotifications()
  } catch { /* empty */ }
}

async function showPreview(id: string) {
  try {
    const res = await fetch(`${API_BASE}/templates/updates/preview/${id}`)
    const data = await res.json()
    if (data.code === 'SUCCESS') {
      previewData.value = data.data
      previewDialog.value = true
    }
  } catch { /* empty */ }
}

onMounted(fetchNotifications)
</script>

<template>
  <div class="update-center-page">
    <el-card class="header-card">
      <div class="page-header">
        <h2>更新中心</h2>
        <el-button
          type="primary"
          @click="fetchNotifications"
        >
          刷新
        </el-button>
      </div>
    </el-card>

    <el-card class="filter-card">
      <el-radio-group
        v-model="statusFilter"
        @change="fetchNotifications"
      >
        <el-radio-button label="pending">
          待处理
        </el-radio-button>
        <el-radio-button label="applied">
          已应用
        </el-radio-button>
        <el-radio-button label="dismissed">
          已忽略
        </el-radio-button>
        <el-radio-button label="all">
          全部
        </el-radio-button>
      </el-radio-group>
    </el-card>

    <div
      v-if="loading"
      class="loading"
    >
      加载中...
    </div>

    <el-card
      v-for="notif in filteredNotifications"
      :key="notif.notification_id"
      class="notif-card"
      shadow="hover"
    >
      <template #header>
        <div class="notif-header">
          <span class="notif-title">{{ notif.title }}</span>
          <div class="notif-tags">
            <el-tag
              :type="priorityTag(notif.priority).type"
              size="small"
            >
              {{ priorityTag(notif.priority).text }}
            </el-tag>
            <el-tag
              :type="statusTag(notif.status).type"
              size="small"
            >
              {{ statusTag(notif.status).text }}
            </el-tag>
          </div>
        </div>
      </template>
      <div class="notif-body">
        <p>{{ notif.description }}</p>
        <div
          v-if="notif.expected_impact && Object.keys(notif.expected_impact).length > 0"
          class="impact-section"
        >
          <h4>预期影响</h4>
          <div
            v-for="(val, key) in notif.expected_impact"
            :key="key"
            class="impact-item"
          >
            <span class="impact-label">{{ key }}:</span>
            <span class="impact-value">{{ typeof val === 'number' ? (val * 100).toFixed(1) + '%' : val }}</span>
          </div>
        </div>
        <div class="notif-time">
          {{ formatSecondsTimestamp(notif.created_at) }}
        </div>
      </div>
      <template #footer>
        <div class="notif-actions">
          <el-button
            size="small"
            @click="showPreview(notif.notification_id)"
          >
            预览变更
          </el-button>
          <el-button
            v-if="notif.status === 'pending'"
            type="success"
            size="small"
            @click="applyUpdate(notif.notification_id)"
          >
            一键应用
          </el-button>
          <el-button
            v-if="notif.status === 'pending'"
            type="info"
            size="small"
            @click="dismissUpdate(notif.notification_id)"
          >
            忽略
          </el-button>
        </div>
      </template>
    </el-card>

    <el-empty
      v-if="!loading && filteredNotifications.length === 0"
      description="暂无更新通知"
    />

    <el-dialog
      v-model="previewDialog"
      title="变更预览"
      width="600px"
    >
      <div v-if="previewData">
        <h3>{{ previewData.title }}</h3>
        <p>{{ previewData.description }}</p>
        <h4>具体变更</h4>
        <pre class="change-preview">{{ JSON.stringify(previewData.change_preview, null, 2) }}</pre>
        <h4>预期效果</h4>
        <pre class="impact-preview">{{ JSON.stringify(previewData.expected_impact, null, 2) }}</pre>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.update-center-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; }
.page-header h2 { margin: 0; }
.filter-card { margin: 16px 0; }
.notif-card { margin-bottom: 12px; }
.notif-header { display: flex; justify-content: space-between; align-items: center; }
.notif-title { font-weight: 600; font-size: 15px; }
.notif-tags { display: flex; gap: 8px; }
.notif-body { font-size: 14px; color: #555; }
.impact-section { margin-top: 12px; padding: 8px 12px; background: #f5f7fa; border-radius: 4px; }
.impact-section h4 { margin: 0 0 8px; font-size: 13px; color: #666; }
.impact-item { display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 4px; }
.impact-label { color: #888; }
.impact-value { font-weight: 600; color: #409eff; }
.notif-time { margin-top: 8px; font-size: 12px; color: #999; }
.notif-actions { display: flex; gap: 8px; }
.loading { text-align: center; padding: 40px; color: #999; }
.change-preview, .impact-preview { background: #f5f7fa; padding: 12px; border-radius: 4px; font-size: 13px; max-height: 200px; overflow: auto; }
.header-card { margin-bottom: 16px; }
</style>
