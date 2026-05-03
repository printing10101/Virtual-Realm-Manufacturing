<template>
  <div class="experience-view">
    <h1 class="page-title">
      <el-icon><Collection /></el-icon>
      经验回放知识库
    </h1>

    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #409EFF">
              <el-icon><Document /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.total_experiences || 0 }}</div>
              <div class="stat-label">经验总数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #67C23A">
              <el-icon><CircleCheck /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ ((stats.success_rate || 0) * 100).toFixed(1) }}%</div>
              <div class="stat-label">成功率</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #E6A23C">
              <el-icon><Lightbulb /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.total_rules || 0 }}</div>
              <div class="stat-label">规则总数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #F56C6C">
              <el-icon><Warning /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.failure_count || 0 }}</div>
              <div class="stat-label">失败经验</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-tabs v-model="activeTab" type="border-card">
      <el-tab-pane label="经验列表" name="experiences">
        <div class="filter-bar">
          <el-input
            v-model="filterMaterial"
            placeholder="过滤材料"
            style="width: 200px; margin-right: 10px"
            clearable
          />
          <el-select
            v-model="filterStatus"
            placeholder="过滤状态"
            style="width: 150px; margin-right: 10px"
            clearable
          >
            <el-option label="成功" value="success" />
            <el-option label="失败" value="failure" />
            <el-option label="部分成功" value="partial" />
          </el-select>
          <el-button type="primary" @click="loadExperiences">查询</el-button>
        </div>

        <el-table :data="experiences" style="width: 100%" stripe>
          <el-table-column prop="material" label="材料" width="120" />
          <el-table-column prop="tool" label="刀具" width="120" />
          <el-table-column prop="operation" label="工序" width="100" />
          <el-table-column prop="similarity_key" label="工况描述" min-width="200" show-overflow-tooltip />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="getStatusType(row.status)">
                {{ getStatusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="规则数" width="80">
            <template #default="{ row }">
              {{ row.extracted_rules?.length || 0 }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button type="danger" size="small" @click="deleteExperience(row.experience_id)">
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="规则库" name="rules">
        <div v-for="(ruleList, scenario) in allRules" :key="scenario" class="rule-group">
          <h3 class="rule-group-title">{{ scenario || "默认场景" }}</h3>
          <el-table :data="ruleList" style="width: 100%" stripe>
            <el-table-column label="启用" width="80">
              <template #default="{ row, $index }">
                <el-switch
                  v-model="row.enabled"
                  @change="toggleRule(scenario, $index)"
                />
              </template>
            </el-table-column>
            <el-table-column prop="rule" label="规则内容" min-width="400" />
            <el-table-column label="来源" width="120">
              <template #default="{ row }">
                <el-tag size="small" :type="row.status === 'success' ? 'success' : 'danger'">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <el-empty v-if="Object.keys(allRules).length === 0" description="暂无规则" />
      </el-tab-pane>

      <el-tab-pane label="相似检索" name="search">
        <el-form :inline="true" class="search-form">
          <el-form-item label="材料">
            <el-input v-model="searchForm.material" placeholder="如: 45钢" />
          </el-form-item>
          <el-form-item label="刀具">
            <el-input v-model="searchForm.tool" placeholder="如: 硬质合金" />
          </el-form-item>
          <el-form-item label="工序">
            <el-select v-model="searchForm.operation" placeholder="选择工序">
              <el-option label="车削" value="车削" />
              <el-option label="铣削" value="铣削" />
              <el-option label="钻削" value="钻削" />
              <el-option label="磨削" value="磨削" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="searchSimilar">检索</el-button>
          </el-form-item>
        </el-form>

        <el-row v-if="searchResults.success.length > 0 || searchResults.failure.length > 0" :gutter="20" style="margin-top: 20px">
          <el-col :span="12">
            <h3 style="color: #67C23A">成功经验</h3>
            <el-card
              v-for="exp in searchResults.success"
              :key="exp.experience_id"
              shadow="hover"
              class="result-card"
            >
              <div class="result-item">
                <div class="result-header">
                  <el-tag type="success">成功</el-tag>
                  <span class="result-key">{{ exp.similarity_key }}</span>
                </div>
                <div class="result-params">
                  <span>材料: {{ exp.material }}</span>
                  <span>刀具: {{ exp.tool }}</span>
                  <span>工序: {{ exp.operation }}</span>
                </div>
                <div v-if="exp.extracted_rules.length > 0" class="result-rules">
                  <div v-for="(rule, idx) in exp.extracted_rules" :key="idx" class="rule-text">
                    <el-icon><Lightbulb /></el-icon> {{ rule }}
                  </div>
                </div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="12">
            <h3 style="color: #F56C6C">失败经验（需避免）</h3>
            <el-card
              v-for="exp in searchResults.failure"
              :key="exp.experience_id"
              shadow="hover"
              class="result-card"
            >
              <div class="result-item">
                <div class="result-header">
                  <el-tag type="danger">{{ exp.status === 'failure' ? '失败' : '部分成功' }}</el-tag>
                  <span class="result-key">{{ exp.similarity_key }}</span>
                </div>
                <div class="result-params">
                  <span>材料: {{ exp.material }}</span>
                  <span>刀具: {{ exp.tool }}</span>
                  <span>工序: {{ exp.operation }}</span>
                </div>
                <div v-if="exp.extracted_rules.length > 0" class="result-rules">
                  <div v-for="(rule, idx) in exp.extracted_rules" :key="idx" class="rule-text">
                    <el-icon><Warning /></el-icon> {{ rule }}
                  </div>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>
        <el-empty v-else description="输入条件进行检索" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Collection,
  Document,
  CircleCheck,
  Lightbulb,
  Warning
} from '@element-plus/icons-vue'

const activeTab = ref('experiences')
const stats = reactive({
  total_experiences: 0,
  success_count: 0,
  failure_count: 0,
  partial_count: 0,
  success_rate: 0,
  total_rules: 0,
  scenario_distribution: {}
})

const filterMaterial = ref('')
const filterStatus = ref('')
const experiences = ref<any[]>([])
const allRules = ref<Record<string, any[]>>({})

const searchForm = reactive({
  material: '',
  tool: '',
  operation: ''
})

const searchResults = reactive({
  success: [] as any[],
  failure: [] as any[]
})

async function loadStats() {
  try {
    const response = await fetch('/api/v1/experiences/stats')
    const result = await response.json()
    if (result.code === 0) {
      Object.assign(stats, result.data)
    }
  } catch (e) {
    console.error('加载统计信息失败:', e)
  }
}

async function loadExperiences() {
  try {
    const params = new URLSearchParams()
    if (filterMaterial.value) params.append('material', filterMaterial.value)
    if (filterStatus.value) params.append('status', filterStatus.value)

    const response = await fetch(`/api/v1/experiences?${params}`)
    const result = await response.json()
    if (result.code === 0) {
      experiences.value = result.data.experiences
    }
  } catch (e) {
    console.error('加载经验列表失败:', e)
  }
}

async function loadRules() {
  try {
    const response = await fetch('/api/v1/experiences/rules')
    const result = await response.json()
    if (result.code === 0) {
      allRules.value = result.data.rules
    }
  } catch (e) {
    console.error('加载规则失败:', e)
  }
}

async function deleteExperience(id: string) {
  try {
    await ElMessageBox.confirm('确定要删除这条经验吗?', '确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    const response = await fetch(`/api/v1/experiences/${id}`, {
      method: 'DELETE'
    })
    const result = await response.json()
    if (result.code === 0) {
      ElMessage.success('删除成功')
      loadExperiences()
      loadStats()
    } else {
      ElMessage.error(result.message || '删除失败')
    }
  } catch (e) {
    if (e !== 'cancel') {
      console.error('删除经验失败:', e)
    }
  }
}

async function toggleRule(scenario: string, index: number) {
  try {
    const response = await fetch(`/api/v1/experiences/rules/${scenario}/${index}/toggle`, {
      method: 'POST'
    })
    const result = await response.json()
    if (result.code === 0) {
      ElMessage.success('规则已更新')
    }
  } catch (e) {
    console.error('切换规则失败:', e)
  }
}

async function searchSimilar() {
  try {
    const response = await fetch('/api/v1/experiences')
    const result = await response.json()
    if (result.code === 0) {
      const all = result.data.experiences
      searchResults.success = all.filter((e: any) =>
        e.status === 'success' &&
        (!searchForm.material || e.material.includes(searchForm.material)) &&
        (!searchForm.tool || e.tool.includes(searchForm.tool)) &&
        (!searchForm.operation || e.operation === searchForm.operation)
      )
      searchResults.failure = all.filter((e: any) =>
        e.status !== 'success' &&
        (!searchForm.material || e.material.includes(searchForm.material)) &&
        (!searchForm.tool || e.tool.includes(searchForm.tool)) &&
        (!searchForm.operation || e.operation === searchForm.operation)
      )
    }
  } catch (e) {
    console.error('检索失败:', e)
  }
}

function getStatusType(status: string) {
  const map: Record<string, any> = { success: 'success', failure: 'danger', partial: 'warning' }
  return map[status] || 'info'
}

function getStatusLabel(status: string) {
  const map: Record<string, string> = { success: '成功', failure: '失败', partial: '部分成功' }
  return map[status] || status
}

onMounted(() => {
  loadStats()
  loadExperiences()
  loadRules()
})
</script>

<style scoped lang="scss">
.experience-view {
  padding: 20px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  .stat-content {
    display: flex;
    align-items: center;
    gap: 15px;
  }

  .stat-icon {
    width: 50px;
    height: 50px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    font-size: 24px;
  }

  .stat-info {
    .stat-value {
      font-size: 24px;
      font-weight: bold;
      color: #303133;
    }

    .stat-label {
      font-size: 12px;
      color: #909399;
      margin-top: 5px;
    }
  }
}

.filter-bar {
  margin-bottom: 20px;
  display: flex;
  align-items: center;
}

.rule-group {
  margin-bottom: 20px;

  .rule-group-title {
    font-size: 16px;
    font-weight: bold;
    margin-bottom: 10px;
    color: #303133;
  }
}

.search-form {
  margin-bottom: 20px;
}

.result-card {
  margin-bottom: 15px;

  .result-item {
    .result-header {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 10px;

      .result-key {
        font-size: 14px;
        font-weight: bold;
      }
    }

    .result-params {
      display: flex;
      gap: 20px;
      margin-bottom: 10px;
      font-size: 13px;
      color: #606266;
    }

    .result-rules {
      .rule-text {
        display: flex;
        align-items: center;
        gap: 5px;
        font-size: 13px;
        color: #E6A23C;
        margin-bottom: 5px;
      }
    }
  }
}
</style>
