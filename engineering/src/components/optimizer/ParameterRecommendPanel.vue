<!-- 参数推荐面板（Phase D 前端：飞轮闭环 UI） -->
<template>
  <div class="parameter-recommend">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>切削参数推荐</span>
          <el-tag size="small" :type="strategyTagType">{{ strategyLabel }}</el-tag>
        </div>
      </template>

      <el-form label-width="90px" size="default">
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="材料" required>
              <el-input
                v-model="material"
                placeholder="如 AL6061 / SS304"
                data-test="material-input"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="加工类型">
              <el-select v-model="machiningType" style="width: 100%">
                <el-option label="铣削" value="milling" />
                <el-option label="车削" value="turning" />
                <el-option label="钻孔" value="drilling" />
                <el-option label="攻丝" value="tapping" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="优化目标">
              <el-select v-model="target" style="width: 100%">
                <el-option label="均衡" value="balanced" />
                <el-option label="节拍优先" value="cycle_time" />
                <el-option label="寿命优先" value="tool_life" />
                <el-option label="表面质量" value="surface" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <div class="action-row">
          <el-button
            type="primary"
            :loading="loading"
            data-test="recommend-btn"
            @click="handleRecommend"
          >
            获取推荐
          </el-button>
          <el-button @click="handleClear">清空</el-button>
        </div>
      </el-form>

      <el-divider v-if="recommendation" />

      <div v-if="recommendation" class="result" data-test="recommend-result">
        <el-row :gutter="16">
          <el-col :span="6">
            <el-statistic title="切深 (mm)" :value="recommendation.depth_of_cut_mm" :precision="2" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="进给 (mm/rev)" :value="recommendation.feed_mm_per_rev" :precision="3" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="转速 (RPM)" :value="recommendation.spindle_rpm" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="切削速度 (m/min)" :value="recommendation.cutting_speed_m_min" :precision="1" />
          </el-col>
        </el-row>

        <div class="meta">
          <el-tag v-if="recommendation.clamped" type="warning" size="small">
            已物理安全钳制
          </el-tag>
          <span class="confidence">置信度 {{ (recommendation.confidence * 100).toFixed(0) }}%</span>
        </div>
      </div>

      <el-alert
        v-if="errorMessage"
        :title="errorMessage"
        type="error"
        show-icon
        closable
        @close="errorMessage = ''"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { recommendParameters, type OptimizationTarget, type Recommendation } from '@/api/parameterOptimizer'

const material = ref('')
const machiningType = ref('milling')
const target = ref<OptimizationTarget>('balanced')

const recommendation = ref<Recommendation | null>(null)
const loading = ref(false)
const errorMessage = ref('')

const strategyLabel = computed(() => {
  if (!recommendation.value) return '未推荐'
  const map: Record<string, string> = {
    L0_baseline: '经验基线 (L0)',
    L1_statistical: '统计推荐 (L1)',
    L2_model: '模型推荐 (L2)',
    L3_bayesian: '贝叶斯 (L3)',
  }
  return map[recommendation.value.strategy] ?? recommendation.value.strategy
})

const strategyTagType = computed(() => {
  if (!recommendation.value) return 'info'
  return recommendation.value.strategy === 'L0_baseline' ? 'warning' : 'success'
})

async function handleRecommend(): Promise<void> {
  if (!material.value.trim()) {
    errorMessage.value = '请输入材料名称（如 AL6061、SS304）'
    return
  }
  loading.value = true
  errorMessage.value = ''
  try {
    recommendation.value = await recommendParameters({
      material: material.value.trim(),
      machining_type: machiningType.value,
      target: target.value,
    })
  } catch (e) {
    errorMessage.value = e instanceof Error ? e.message : String(e)
    recommendation.value = null
  } finally {
    loading.value = false
  }
}

function handleClear(): void {
  material.value = ''
  recommendation.value = null
  errorMessage.value = ''
}
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.action-row {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}
.meta {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-top: 12px;
}
.confidence {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
