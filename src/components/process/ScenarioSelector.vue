<template>
  <div class="scenario-selector">
    <h3 class="section-title">选择加工场景</h3>
    
    <div v-if="loading" class="loading-state">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>加载场景中...</span>
    </div>

    <div v-else-if="error" class="error-state">
      <el-alert :title="error" type="error" show-icon :closable="false" />
      <el-button type="primary" size="small" @click="loadScenarios" style="margin-top: 12px;">
        重新加载
      </el-button>
    </div>

    <div v-else class="scenario-grid">
      <div
        v-for="scenario in scenarios"
        :key="scenario.id"
        :class="['scenario-card', { 'is-selected': selectedScenarioId === scenario.id }]"
        @click="selectScenario(scenario.id)"
      >
        <div class="card-header">
          <span class="scenario-name">{{ scenario.name }}</span>
          <el-tag v-if="scenario.is_user_scenario" type="warning" size="small">自定义</el-tag>
          <el-tag v-else type="info" size="small">内置</el-tag>
        </div>
        
        <p class="scenario-description">{{ scenario.description }}</p>
        
        <div class="scenario-details">
          <div class="detail-section">
            <h4>支持材料</h4>
            <div class="tag-list">
              <el-tag
                v-for="material in scenario.supported_materials"
                :key="material"
                size="small"
                type="success"
                effect="plain"
              >
                {{ material }}
              </el-tag>
            </div>
          </div>
          
          <div class="detail-section">
            <h4>支持刀具</h4>
            <div class="tag-list">
              <el-tag
                v-for="tool in scenario.supported_tools"
                :key="tool"
                size="small"
                type="primary"
                effect="plain"
              >
                {{ tool }}
              </el-tag>
            </div>
          </div>
          
          <div class="detail-section">
            <h4>支持工序</h4>
            <div class="tag-list">
              <el-tag
                v-for="operation in scenario.supported_operations"
                :key="operation"
                size="small"
                effect="plain"
              >
                {{ getOperationName(operation) }}
              </el-tag>
            </div>
          </div>
        </div>
        
        <div class="card-footer">
          <span class="version">v{{ scenario.version }}</span>
          <el-button
            v-if="selectedScenarioId === scenario.id"
            type="primary"
            size="small"
          >
            已选择
          </el-button>
        </div>
      </div>
    </div>

    <div v-if="selectedScenarioId" class="selected-info">
      <el-divider />
      <el-alert
        :title="`已选择场景：${selectedScenarioName}`"
        type="success"
        :closable="false"
        show-icon
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import axios from 'axios'

interface Scenario {
  id: string
  name: string
  description: string
  supported_operations: string[]
  supported_materials: string[]
  supported_tools: string[]
  version: string
  is_user_scenario: boolean
}

const props = defineProps<{
  modelValue?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  'change': [scenarioId: string]
}>()

const scenarios = ref<Scenario[]>([])
const loading = ref(false)
const error = ref('')
const selectedScenarioId = ref(props.modelValue || '')

const selectedScenarioName = computed(() => {
  const selected = scenarios.value.find(s => s.id === selectedScenarioId.value)
  return selected ? selected.name : ''
})

const operationNames: Record<string, string> = {
  milling: '铣削',
  turning: '车削',
  drilling: '钻孔',
  boring: '镗孔',
  threading: '螺纹加工',
  engraving: '雕刻'
}

const getOperationName = (operation: string): string => {
  return operationNames[operation] || operation
}

const loadScenarios = async () => {
  loading.value = true
  error.value = ''
  
  try {
    const response = await axios.get('/api/v1/scenarios')
    if (response.data.code === 200) {
      scenarios.value = response.data.data.scenarios
    } else {
      error.value = response.data.message || '加载场景失败'
    }
  } catch (err: any) {
    error.value = err.message || '网络错误'
  } finally {
    loading.value = false
  }
}

const selectScenario = (scenarioId: string) => {
  selectedScenarioId.value = scenarioId
  emit('update:modelValue', scenarioId)
  emit('change', scenarioId)
}

onMounted(() => {
  loadScenarios()
})
</script>

<style scoped>
.scenario-selector {
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
}

.section-title {
  margin: 0 0 16px 0;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.loading-state,
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 0;
  gap: 12px;
}

.loading-state .el-icon {
  font-size: 32px;
  color: #409EFF;
}

.scenario-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.scenario-card {
  background: white;
  border: 2px solid #e4e7ed;
  border-radius: 8px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.scenario-card:hover {
  border-color: #409EFF;
  box-shadow: 0 2px 12px rgba(64, 158, 255, 0.15);
  transform: translateY(-2px);
}

.scenario-card.is-selected {
  border-color: #409EFF;
  background: linear-gradient(135deg, #ecf5ff 0%, #ffffff 100%);
  box-shadow: 0 4px 16px rgba(64, 158, 255, 0.2);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  gap: 8px;
}

.scenario-name {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.scenario-description {
  margin: 0 0 16px 0;
  font-size: 14px;
  color: #606266;
  line-height: 1.5;
}

.scenario-details {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.detail-section h4 {
  margin: 0 0 8px 0;
  font-size: 13px;
  font-weight: 600;
  color: #909399;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.card-footer {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid #ebeef5;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.version {
  font-size: 12px;
  color: #909399;
}

.selected-info {
  margin-top: 20px;
}
</style>
