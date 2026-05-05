<template>
  <div class="route-tester">
    <el-form
      :model="testForm"
      label-width="120px"
    >
      <el-form-item :label="t('modelManagement.material')">
        <el-input
          v-model="testForm.material"
          :placeholder="t('modelManagement.materialPlaceholder')"
        />
      </el-form-item>

      <el-form-item :label="t('modelManagement.tool')">
        <el-input
          v-model="testForm.tool"
          :placeholder="t('modelManagement.toolPlaceholder')"
        />
      </el-form-item>

      <el-form-item :label="t('modelManagement.constraints')">
        <el-input
          v-model="testForm.constraintsText"
          type="textarea"
          :placeholder="t('modelManagement.constraintsPlaceholder')"
          :rows="3"
        />
      </el-form-item>

      <el-form-item :label="t('modelManagement.geometryComplexity')">
        <el-select
          v-model="testForm.geometryLevel"
          style="width: 100%;"
        >
          <el-option
            label="简单"
            value="simple"
          />
          <el-option
            label="中等"
            value="medium"
          />
          <el-option
            label="复杂"
            value="complex"
          />
        </el-select>
      </el-form-item>

      <el-form-item>
        <el-button
          type="primary"
          :loading="testing"
          @click="testRoute"
        >
          {{ t('modelManagement.testRoute') }}
        </el-button>
        <el-button @click="resetForm">
          {{ t('common.reset') }}
        </el-button>
      </el-form-item>
    </el-form>

    <el-card
      v-if="testResult"
      shadow="hover"
      style="margin-top: 20px;"
    >
      <template #header>
        <h3>{{ t('modelManagement.testResult') }}</h3>
      </template>

      <el-descriptions
        :column="2"
        border
      >
        <el-descriptions-item :label="t('modelManagement.routeDecision')">
          <el-tag :type="getRouteTagType(testResult.route_decision)">
            {{ getRouteLabel(testResult.route_decision) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item :label="t('modelManagement.complexityScore')">
          {{ testResult.complexity_score }}
        </el-descriptions-item>
      </el-descriptions>

      <div style="margin-top: 16px;">
        <h4>{{ t('modelManagement.scoreBreakdown') }}</h4>
        <el-table
          :data="breakdownData"
          style="width: 100%;"
          border
        >
          <el-table-column
            prop="dimension"
            :label="t('modelManagement.dimension')"
          />
          <el-table-column
            prop="score"
            :label="t('modelManagement.score')"
          />
          <el-table-column :label="t('modelManagement.level')">
            <template #default="{ row }">
              <el-progress
                :percentage="row.score * 10"
                :format="() => getLevelText(row.score)"
              />
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div
        v-if="testResult.reasons?.length"
        style="margin-top: 16px;"
      >
        <h4>{{ t('modelDecision.reasons') }}</h4>
        <ul>
          <li
            v-for="(reason, index) in testResult.reasons"
            :key="index"
          >
            {{ reason }}
          </li>
        </ul>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'

const { t } = useI18n()
const testing = ref(false)
const testResult = ref<any>(null)

const testForm = ref({
  material: '',
  tool: '',
  constraintsText: '',
  geometryLevel: 'simple'
})

const breakdownData = computed(() => {
  if (!testResult.value?.breakdown) return []
  return [
    { dimension: '材料', score: testResult.value.breakdown.material },
    { dimension: '刀具', score: testResult.value.breakdown.tool },
    { dimension: '约束', score: testResult.value.breakdown.constraints },
    { dimension: '几何', score: testResult.value.breakdown.geometry },
    { dimension: '历史', score: testResult.value.breakdown.history }
  ]
})

function resetForm() {
  testForm.value = {
    material: '',
    tool: '',
    constraintsText: '',
    geometryLevel: 'simple'
  }
  testResult.value = null
}

async function testRoute() {
  testing.value = true
  try {
    const constraints = testForm.value.constraintsText
      ? testForm.value.constraintsText.split('\n').filter(c => c.trim())
      : []

    const geometry = {
      complexity: testForm.value.geometryLevel,
      features: testForm.value.geometryLevel === 'complex' ? ['hole', 'pocket', 'contour', 'thread'] :
                testForm.value.geometryLevel === 'medium' ? ['hole', 'pocket'] : ['hole']
    }

    const response = await fetch('/api/v1/models/route', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        material: testForm.value.material,
        tool: testForm.value.tool,
        constraints,
        geometry,
        history: []
      })
    })

    const result = await response.json()
    if (result.code === 200) {
      testResult.value = result.data
    } else {
      ElMessage.error(result.message || '路由测试失败')
    }
  } catch (error) {
    ElMessage.error('路由测试失败')
  } finally {
    testing.value = false
  }
}

function getRouteTagType(decision: string) {
  switch (decision) {
    case 'local': return 'success'
    case 'local_with_fallback': return 'warning'
    case 'cloud': return 'danger'
    default: return 'info'
  }
}

function getRouteLabel(decision: string) {
  switch (decision) {
    case 'local': return '本地模型'
    case 'local_with_fallback': return '本地 + Fallback'
    case 'cloud': return '云端模型'
    default: return decision
  }
}

function getLevelText(score: number) {
  if (score === 0) return '简单'
  if (score <= 2) return '低'
  if (score <= 4) return '中'
  return '高'
}
</script>

<style scoped lang="scss">
.route-tester {
  h4 {
    margin: 12px 0 8px;
    font-size: 14px;
    color: #303133;
  }

  ul {
    margin: 8px 0;
    padding-left: 20px;

    li {
      margin: 4px 0;
      color: #606266;
    }
  }
}
</style>
