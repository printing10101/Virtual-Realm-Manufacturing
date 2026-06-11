<template>
  <div class="home-page">
    <el-row :gutter="24">
      <el-col :span="16">
        <el-card class="welcome-card">
          <h2>{{ $t('home.welcome') }}</h2>
          <p>{{ $t('home.welcomeDesc') }}</p>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <template #header>
            {{ $t('home.systemStatus') }}
          </template>
          <div class="status-item">
            <span>{{ $t('home.aiService') }}</span>
            <el-tag v-if="loading" type="info" class="status-loading">
              <el-icon class="is-loading"><Loading /></el-icon>
              <span class="status-loading-text">{{ $t('common.loading') }}</span>
            </el-tag>
            <el-tag v-else-if="loadFailed" type="danger">
              {{ $t('home.fetchFailed') }}
            </el-tag>
            <el-tag v-else-if="aiServiceStatus === 'running'" type="success">
              {{ $t('home.running') }}
            </el-tag>
            <el-tag v-else type="warning">
              {{ $t('home.stopped') }}
            </el-tag>
          </div>
          <div class="status-item">
            <span>{{ $t('home.registeredModels') }}</span>
            <span v-if="loading" class="stat-value status-loading">
              <el-icon class="is-loading"><Loading /></el-icon>
            </span>
            <span v-else-if="loadFailed" class="stat-value stat-failed">
              {{ $t('home.fetchFailed') }}
            </span>
            <span v-else class="stat-value">{{ modelCount }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import http from '@/utils/http'

const REQUEST_TIMEOUT = 10000

const aiServiceStatus = ref<'running' | 'stopped' | 'unknown'>('unknown')
const modelCount = ref<number>(0)
const loading = ref<boolean>(true)
const loadFailed = ref<boolean>(false)

async function loadHealth(): Promise<boolean> {
  try {
    const res = await http.get('/api/health', { timeout: REQUEST_TIMEOUT })
    const data = res.data?.data ?? res.data ?? {}
    const rawStatus = (data.status ?? data.ai_service ?? data.aiService ?? '')
      .toString()
      .toLowerCase()
    if (rawStatus === 'running' || rawStatus === 'ok' || rawStatus === 'healthy' || rawStatus === 'up') {
      aiServiceStatus.value = 'running'
    } else if (rawStatus === 'stopped' || rawStatus === 'down' || rawStatus === 'unhealthy') {
      aiServiceStatus.value = 'stopped'
    } else {
      aiServiceStatus.value = 'running'
    }
    return true
  } catch (e) {
    console.warn('Failed to load /api/health:', e)
    return false
  }
}

async function loadModelCount(): Promise<boolean> {
  try {
    const res = await http.get('/api/v1/lnn/models', { timeout: REQUEST_TIMEOUT })
    const data = res.data?.data ?? res.data ?? {}
    const total = data.total ?? data.count ?? data.model_count
    if (typeof total === 'number') {
      modelCount.value = total
    } else if (Array.isArray(data.models)) {
      modelCount.value = data.models.length
    } else {
      modelCount.value = 0
    }
    return true
  } catch (e) {
    console.warn('Failed to load /api/v1/lnn/models:', e)
    return false
  }
}

onMounted(async () => {
  loading.value = true
  loadFailed.value = false
  try {
    const results = await Promise.all([loadHealth(), loadModelCount()])
    if (results.some((ok) => !ok)) {
      loadFailed.value = true
    }
  } catch (e) {
    console.warn('Home status loading error:', e)
    loadFailed.value = true
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.home-page {
  max-width: 1200px;
  margin: 0 auto;
}

.welcome-card h2 {
  margin: 0 0 12px;
}

.status-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.stat-value {
  font-weight: bold;
  color: #409eff;
}

.stat-failed {
  color: #f56c6c;
  font-weight: normal;
  font-size: 13px;
}

.status-loading {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.status-loading-text {
  margin-left: 2px;
}
</style>
