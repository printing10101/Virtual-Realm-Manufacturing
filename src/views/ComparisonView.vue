<template>
  <div class="comparison-view">
    <el-card class="view-card">
      <template #header>
        <div class="card-header">
          <h2>{{ t('comparison.title') }}</h2>
          <el-button
            size="small"
            @click="resetForm"
          >
            <el-icon><RefreshLeft /></el-icon>
            {{ t('comparison.reset') }}
          </el-button>
        </div>
      </template>

      <!-- 零件信息输入区 -->
      <el-form
        :model="form"
        label-width="120px"
        class="part-form"
      >
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item :label="t('comparison.material')">
              <el-select
                v-model="form.material"
                :placeholder="t('comparison.materialPlaceholder')"
              >
                <el-option
                  label="45钢"
                  value="steel_45"
                />
                <el-option
                  label="铝合金6061"
                  value="aluminum_6061"
                />
                <el-option
                  label="不锈钢304"
                  value="stainless_304"
                />
                <el-option
                  label="钛合金TC4"
                  value="titanium_tc4"
                />
                <el-option
                  label="铜"
                  value="copper"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="t('comparison.partType')">
              <el-select
                v-model="form.partType"
                :placeholder="t('comparison.partTypePlaceholder')"
              >
                <el-option
                  :label="t('comparison.partTypes.shaft')"
                  value="shaft"
                />
                <el-option
                  :label="t('comparison.partTypes.gear')"
                  value="gear"
                />
                <el-option
                  :label="t('comparison.partTypes.housing')"
                  value="housing"
                />
                <el-option
                  :label="t('comparison.partTypes.plate')"
                  value="plate"
                />
                <el-option
                  :label="t('comparison.partTypes.flange')"
                  value="flange"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <!-- 策略选择区 -->
      <div class="strategy-section">
        <h3>{{ t('comparison.selectStrategy') }}</h3>
        <el-row
          :gutter="16"
          class="strategy-cards"
        >
          <el-col
            v-for="strategy in strategies"
            :key="strategy.id"
            :span="6"
          >
            <el-card
              :class="['strategy-card', { active: selectedStrategies.includes(strategy.id) }]"
              shadow="hover"
              @click="toggleStrategy(strategy.id)"
            >
              <div class="strategy-content">
                <el-icon
                  class="strategy-icon"
                  :size="32"
                >
                  <component :is="strategy.icon" />
                </el-icon>
                <h4>{{ strategy.name }}</h4>
                <p>{{ strategy.description }}</p>
              </div>
            </el-card>
          </el-col>
        </el-row>
        <el-button
          type="primary"
          :loading="isGenerating"
          :disabled="selectedStrategies.length === 0 || isGenerating"
          class="generate-btn"
          @click="handleGenerate"
        >
          {{ isGenerating ? t('comparison.generating') : t('comparison.generateBtn') }}
        </el-button>
      </div>

      <!-- 加载状态 -->
      <div
        v-if="isGenerating"
        class="loading-section"
      >
        <el-skeleton
          :rows="5"
          animated
        />
      </div>

      <!-- 对比结果区 -->
      <div
        v-if="comparisonResult && !isGenerating"
        class="result-section"
      >
        <!-- 雷达图对比区 -->
        <el-card
          class="radar-card"
          shadow="never"
        >
          <template #header>
            <h3>{{ t('comparison.radarChart') }}</h3>
          </template>
          <div
            ref="radarChartRef"
            class="radar-chart"
          />
        </el-card>

        <!-- 权重调节区 -->
        <el-card
          class="weights-card"
          shadow="never"
        >
          <template #header>
            <div class="weights-header">
              <h3>{{ t('comparison.weightAdjust') }}</h3>
              <el-button
                size="small"
                :loading="isCustomGenerating"
                @click="handleGenerateCustom"
              >
                {{ t('comparison.generateCustom') }}
              </el-button>
            </div>
          </template>
          <el-row :gutter="20">
            <el-col
              v-for="weight in weightConfig"
              :key="weight.key"
              :span="6"
            >
              <div class="weight-item">
                <label>{{ weight.label }}</label>
                <el-slider
                  v-model="customWeights[weight.key]"
                  :min="0"
                  :max="100"
                  :step="1"
                  show-input
                  :input-size="'small'"
                  @change="onWeightChange"
                />
                <span class="weight-value">{{ customWeights[weight.key] }}%</span>
              </div>
            </el-col>
          </el-row>
        </el-card>

        <!-- 详细数据表格 -->
        <el-card
          class="table-card"
          shadow="never"
        >
          <template #header>
            <h3>{{ t('comparison.detailTable') }}</h3>
          </template>
          <el-table
            :data="tableData"
            stripe
            border
            style="width: 100%"
          >
            <el-table-column
              prop="strategy_name"
              :label="t('comparison.colStrategy')"
              width="120"
              fixed
            />
            <el-table-column
              :label="t('comparison.colNormalized')"
              min-width="300"
            >
              <template #default="scope">
                <div class="score-bars">
                  <div
                    v-for="dim in dimensions"
                    :key="dim.key"
                    class="score-bar"
                  >
                    <span class="dim-label">{{ dim.label }}</span>
                    <el-progress
                      :percentage="Math.round(scope.row.scores[dim.key] || 0)"
                      :stroke-width="12"
                      :show-text="true"
                      :color="dim.color"
                    />
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column
              prop="weighted_score"
              :label="t('comparison.colTotalScore')"
              width="120"
            >
              <template #default="scope">
                <el-tag
                  :type="getScoreType(scope.row.weighted_score)"
                  size="large"
                >
                  {{ scope.row.weighted_score?.toFixed(1) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column
              prop="advantage_analysis"
              :label="t('comparison.colAdvantage')"
              min-width="200"
            />
            <el-table-column
              prop="recommendation"
              :label="t('comparison.colRecommendation')"
              min-width="200"
            />
            <el-table-column
              :label="t('comparison.colAction')"
              width="200"
              fixed="right"
            >
              <template #default="scope">
                <el-button
                  type="primary"
                  size="small"
                  :disabled="scope.row.selected"
                  @click="handleSelectPlan(scope.row)"
                >
                  {{ scope.row.selected ? t('comparison.selected') : t('comparison.selectBtn') }}
                </el-button>
                <el-button
                  type="success"
                  size="small"
                  @click="handleGenerateDocument(scope.row)"
                >
                  {{ t('comparison.generateDocument') }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <!-- 详细参数对比 -->
        <el-card
          class="params-card"
          shadow="never"
        >
          <template #header>
            <h3>{{ t('comparison.paramsComparison') }}</h3>
          </template>
          <el-table
            :data="plansData"
            stripe
            border
          >
            <el-table-column
              prop="strategy_name"
              :label="t('comparison.colStrategy')"
              width="120"
            />
            <el-table-column
              prop="cutting_speed"
              :label="t('comparison.colCuttingSpeed')"
              width="120"
            >
              <template #default="scope">
                {{ scope.row.cutting_speed?.toFixed(1) }} m/min
              </template>
            </el-table-column>
            <el-table-column
              prop="feed_rate"
              :label="t('comparison.colFeedRate')"
              width="120"
            >
              <template #default="scope">
                {{ scope.row.feed_rate?.toFixed(3) }} mm/rev
              </template>
            </el-table-column>
            <el-table-column
              prop="depth_of_cut"
              :label="t('comparison.colDepthOfCut')"
              width="120"
            >
              <template #default="scope">
                {{ scope.row.depth_of_cut?.toFixed(2) }} mm
              </template>
            </el-table-column>
            <el-table-column
              prop="surface_roughness"
              :label="t('comparison.colRoughness')"
              width="120"
            >
              <template #default="scope">
                {{ scope.row.surface_roughness?.toFixed(3) }} Ra
              </template>
            </el-table-column>
            <el-table-column
              prop="cost"
              :label="t('comparison.colCost')"
              width="100"
            >
              <template #default="scope">
                ¥{{ scope.row.cost?.toFixed(2) }}
              </template>
            </el-table-column>
            <el-table-column
              prop="processing_time"
              :label="t('comparison.colTime')"
              width="100"
            >
              <template #default="scope">
                {{ scope.row.processing_time?.toFixed(1) }} min
              </template>
            </el-table-column>
            <el-table-column
              prop="tool_life"
              :label="t('comparison.colToolLife')"
              width="110"
            >
              <template #default="scope">
                {{ scope.row.tool_life?.toFixed(0) }} min
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </div>

      <!-- 空状态 -->
      <div
        v-if="!comparisonResult && !isGenerating"
        class="empty-result"
      >
        <el-empty :description="t('comparison.emptyResult')" />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { RefreshLeft, Trophy, Money, Timer, Star } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import * as echarts from 'echarts/core'
import { RadarChart } from 'echarts/charts'
import {
  TooltipComponent,
  LegendComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsType } from 'echarts/core'
import { buildApiUrl } from '@/utils/api'
import { useSettingsStore } from '@/stores/settingsStore'
import axios from 'axios'

echarts.use([
  RadarChart,
  TooltipComponent,
  LegendComponent,
  CanvasRenderer
])

const { t } = useI18n()
const router = useRouter()
const settingsStore = useSettingsStore()

interface ComparisonForm {
  material: string
  partType: string
}

interface PlanData {
  plan_id: string
  strategy_id: string
  strategy_name: string
  cutting_speed: number
  feed_rate: number
  depth_of_cut: number
  surface_roughness: number
  cost: number
  processing_time: number
  tool_life: number
  selected?: boolean
}

interface ScoreData {
  plan_id: string
  strategy_id: string
  strategy_name: string
  scores: {
    quality: number
    cost: number
    efficiency: number
    tool_life: number
  }
  weighted_score: number
  advantage_analysis: string
  recommendation: string
  selected?: boolean
}

const form = reactive<ComparisonForm>({
  material: 'steel_45',
  partType: 'shaft'
})

const strategies = computed(() => [
  { id: 'quality_first', name: t('comparison.strategies.quality'), description: t('comparison.strategies.qualityDesc'), icon: Trophy },
  { id: 'cost_first', name: t('comparison.strategies.cost'), description: t('comparison.strategies.costDesc'), icon: Money },
  { id: 'efficiency_first', name: t('comparison.strategies.efficiency'), description: t('comparison.strategies.efficiencyDesc'), icon: Timer },
  { id: 'balanced', name: t('comparison.strategies.balanced'), description: t('comparison.strategies.balancedDesc'), icon: Star }
])

const selectedStrategies = ref<string[]>(['quality_first', 'cost_first', 'efficiency_first', 'balanced'])

const isGenerating = ref(false)
const isCustomGenerating = ref(false)
const comparisonResult = ref<any>(null)
const taskId = ref<string>('')
const radarChartRef = ref<HTMLElement>()
let radarChart: EChartsType | null = null
let resizeHandler: (() => void) | null = null

const customWeights = reactive({
  quality: 25,
  cost: 25,
  efficiency: 25,
  tool_life: 25
})

const weightConfig: Array<{ key: keyof typeof customWeights; label: string }> = [
  { key: 'quality', label: t('comparison.weights.quality') },
  { key: 'cost', label: t('comparison.weights.cost') },
  { key: 'efficiency', label: t('comparison.weights.efficiency') },
  { key: 'tool_life', label: t('comparison.weights.toolLife') }
]

const dimensions = [
  { key: 'quality', label: t('comparison.dimensions.quality'), color: '#67C23A' },
  { key: 'cost', label: t('comparison.dimensions.cost'), color: '#E6A23C' },
  { key: 'efficiency', label: t('comparison.dimensions.efficiency'), color: '#409EFF' },
  { key: 'tool_life', label: t('comparison.dimensions.toolLife'), color: '#F56C6C' }
]

const plansData = ref<PlanData[]>([])
const scoresData = ref<ScoreData[]>([])

const tableData = computed(() => scoresData.value)

const toggleStrategy = (strategyId: string) => {
  const index = selectedStrategies.value.indexOf(strategyId)
  if (index > -1) {
    selectedStrategies.value.splice(index, 1)
  } else {
    selectedStrategies.value.push(strategyId)
  }
}

const handleGenerate = async () => {
  if (selectedStrategies.value.length === 0) {
    ElMessage.warning(t('comparison.selectAtLeastOne'))
    return
  }

  isGenerating.value = true
  comparisonResult.value = null

  try {
    const pythonBackendUrl = settingsStore.pythonBackendUrl || 'http://localhost:8765'
    const response = await axios.post(buildApiUrl('/api/v1/comparisons/generate', pythonBackendUrl), {
      material: form.material,
      part_type: form.partType,
      constraints: {}
    })

    if (response.data.code === 0) {
      taskId.value = response.data.data.task_id
      await fetchComparisonResult(taskId.value)
    } else {
      ElMessage.error(response.data.message || t('comparison.generateFailed'))
    }
  } catch (error) {
    ElMessage.error(t('comparison.generateError'))
    console.error(error)
  } finally {
    isGenerating.value = false
  }
}

const handleGenerateCustom = async () => {
  const totalWeight = customWeights.quality + customWeights.cost + customWeights.efficiency + customWeights.tool_life
  if (totalWeight !== 100) {
    ElMessage.warning(t('comparison.weightsMustSum100'))
    return
  }

  isCustomGenerating.value = true

  try {
    const pythonBackendUrl = settingsStore.pythonBackendUrl || 'http://localhost:8765'
    const response = await axios.post(buildApiUrl('/api/v1/comparisons/custom', pythonBackendUrl), {
      material: form.material,
      part_type: form.partType,
      constraints: {},
      weights: {
        quality: customWeights.quality / 100,
        cost: customWeights.cost / 100,
        efficiency: customWeights.efficiency / 100,
        tool_life: customWeights.tool_life / 100
      }
    })

    if (response.data.code === 0) {
      taskId.value = response.data.data.task_id
      await fetchComparisonResult(taskId.value)
      ElMessage.success(t('comparison.customGenerateSuccess'))
    } else {
      ElMessage.error(response.data.message || t('comparison.generateFailed'))
    }
  } catch (error) {
    ElMessage.error(t('comparison.generateError'))
    console.error(error)
  } finally {
    isCustomGenerating.value = false
  }
}

const fetchComparisonResult = async (tid: string) => {
  try {
    const pythonBackendUrl = settingsStore.pythonBackendUrl || 'http://localhost:8765'
    const response = await axios.get(buildApiUrl(`/api/v1/comparisons/${tid}`, pythonBackendUrl))

    if (response.data.code === 0) {
      comparisonResult.value = response.data.data
      plansData.value = response.data.data.plans || []
      
      const rawScores = response.data.data.scores || []
      scoresData.value = rawScores.map((score: any) => ({
        plan_id: score.plan_id,
        strategy_id: score.strategy_id,
        strategy_name: score.strategy_name,
        scores: score.normalized_scores || {},
        weighted_score: score.weighted_score || 0,
        advantage_analysis: score.advantage_analysis || '',
        recommendation: score.recommendation || '',
        selected: false
      }))
      
      initRadarChart()
    }
  } catch (error) {
    console.error('Failed to fetch comparison result:', error)
  }
}

const handleSelectPlan = async (row: ScoreData) => {
  try {
    const pythonBackendUrl = settingsStore.pythonBackendUrl || 'http://localhost:8765'
    await axios.post(buildApiUrl(`/api/v1/comparisons/${taskId.value}/select`, pythonBackendUrl), {
      selected_plan_id: row.plan_id,
      selected_strategy_id: row.strategy_id,
      reason: row.recommendation
    })

    scoresData.value.forEach(s => s.selected = false)
    row.selected = true
    
    plansData.value.forEach(p => {
      p.selected = p.plan_id === row.plan_id
    })

    ElMessage.success(t('comparison.selectSuccess'))
  } catch (error) {
    ElMessage.error(t('comparison.selectFailed'))
    console.error(error)
  }
}

const handleGenerateDocument = (row: ScoreData) => {
  router.push({
    path: '/documents',
    query: {
      process_plan_id: taskId.value,
      selected_plan_id: row.plan_id,
      template_id: 'process_card'
    }
  })
}

const initRadarChart = () => {
  if (!radarChartRef.value) return

  if (radarChart) {
    radarChart.dispose()
  }

  radarChart = echarts.init(radarChartRef.value)

  const indicatorNames = dimensions.map(d => d.label)
  const indicatorMax = 100

  const series = scoresData.value.map((score, index) => ({
    name: score.strategy_name,
    type: 'radar',
    data: [{
      value: [
        score.scores.quality,
        score.scores.cost,
        score.scores.efficiency,
        score.scores.tool_life
      ],
      name: score.strategy_name
    }],
    itemStyle: {
      color: ['#67C23A', '#E6A23C', '#409EFF', '#F56C6C'][index % 4]
    },
    lineStyle: {
      width: 2
    },
    areaStyle: {
      opacity: 0.2
    }
  }))

  const option = {
    tooltip: {
      trigger: 'item'
    },
    legend: {
      data: scoresData.value.map(s => s.strategy_name),
      bottom: 10
    },
    radar: {
      indicator: indicatorNames.map(name => ({ name, max: indicatorMax })),
      shape: 'polygon',
      splitNumber: 5,
      axisName: {
        color: '#333',
        fontSize: 12
      },
      splitLine: {
        lineStyle: {
          color: ['#eee', '#ddd', '#ccc', '#bbb', '#aaa']
        }
      },
      splitArea: {
        show: true,
        areaStyle: {
          color: ['rgba(255,255,255,0.1)', 'rgba(255,255,255,0.2)']
        }
      }
    },
    series
  }

  radarChart?.setOption(option)
}

const onWeightChange = () => {
  // 实时验证权重总和
}

const getScoreType = (score: number) => {
  if (score >= 80) return 'success'
  if (score >= 60) return 'primary'
  if (score >= 40) return 'warning'
  return 'danger'
}

const resetForm = () => {
  form.material = 'steel_45'
  form.partType = 'shaft'
  selectedStrategies.value = ['quality_first', 'cost_first', 'efficiency_first', 'balanced']
  comparisonResult.value = null
  taskId.value = ''
  plansData.value = []
  scoresData.value = []
  customWeights.quality = 25
  customWeights.cost = 25
  customWeights.efficiency = 25
  customWeights.tool_life = 25
  if (radarChart) {
    radarChart.dispose()
    radarChart = null
  }
}

onMounted(() => {
  resizeHandler = () => {
    radarChart?.resize()
  }
  window.addEventListener('resize', resizeHandler)
})

onUnmounted(() => {
  if (resizeHandler) {
    window.removeEventListener('resize', resizeHandler)
    resizeHandler = null
  }
  if (radarChart) {
    radarChart.dispose()
    radarChart = null
  }
})
</script>

<style scoped lang="scss">
.comparison-view {
  .view-card {
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;

      h2 {
        margin: 0;
        font-size: 20px;
        color: #303133;
      }
    }

    .part-form {
      margin-bottom: 24px;
      padding: 16px;
      background: #f5f7fa;
      border-radius: 8px;
    }

    .strategy-section {
      margin-bottom: 24px;

      h3 {
        margin-bottom: 16px;
        font-size: 16px;
        color: #303133;
      }

      .strategy-cards {
        margin-bottom: 16px;
      }

      .strategy-card {
        cursor: pointer;
        transition: all 0.3s;
        border: 2px solid transparent;

        &:hover {
          transform: translateY(-4px);
        }

        &.active {
          border-color: #409EFF;
          background: #ecf5ff;
        }

        .strategy-content {
          text-align: center;
          padding: 12px;

          .strategy-icon {
            margin-bottom: 8px;
            color: #409EFF;
          }

          h4 {
            margin: 8px 0;
            font-size: 16px;
            color: #303133;
          }

          p {
            margin: 0;
            font-size: 12px;
            color: #909399;
          }
        }
      }

      .generate-btn {
        width: 100%;
        height: 44px;
        font-size: 16px;
      }
    }

    .loading-section {
      padding: 20px;
    }

    .result-section {
      .radar-card,
      .weights-card,
      .table-card,
      .params-card {
        margin-bottom: 20px;
      }

      .radar-chart {
        width: 100%;
        height: 450px;
      }

      .weights-header {
        display: flex;
        justify-content: space-between;
        align-items: center;

        h3 {
          margin: 0;
          font-size: 16px;
          color: #303133;
        }
      }

      .weight-item {
        padding: 16px;
        background: #f5f7fa;
        border-radius: 8px;

        label {
          display: block;
          margin-bottom: 12px;
          font-size: 14px;
          color: #303133;
          font-weight: 500;
        }

        .weight-value {
          display: block;
          text-align: right;
          margin-top: 8px;
          font-size: 14px;
          color: #409EFF;
          font-weight: bold;
        }
      }

      .score-bars {
        .score-bar {
          margin-bottom: 8px;

          .dim-label {
            display: inline-block;
            width: 60px;
            font-size: 12px;
            color: #606266;
          }
        }
      }
    }

    .empty-result {
      margin-top: 40px;
      min-height: 300px;
    }
  }
}

@media (max-width: 768px) {
  .comparison-view {
    .view-card {
      .card-header {
        flex-direction: column;
        align-items: flex-start;
        gap: 12px;
      }

      .strategy-section {
        .strategy-cards {
          .el-col {
            margin-bottom: 12px;
          }
        }
      }

      .result-section {
        .weight-item {
          margin-bottom: 12px;
        }
      }
    }
  }
}
</style>
