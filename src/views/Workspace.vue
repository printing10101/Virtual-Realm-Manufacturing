<template>
  <div class="workspace-page">
    <el-card>
      <template #header>工作区 - LNN模型推理</template>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="预测推理" name="predict">
          <el-form :model="predictForm" label-width="120px">
            <el-form-item label="模型名称">
              <el-select v-model="predictForm.modelName" placeholder="选择模型">
                <el-option label="CFC-Fast" value="CFC-Fast" />
                <el-option label="LTC-TimeSeries" value="LTC-TimeSeries" />
                <el-option label="Hybrid-Multimodal" value="Hybrid-Multimodal" />
              </el-select>
            </el-form-item>
            <el-form-item label="输入数据">
              <el-input
                v-model="predictForm.inputData"
                type="textarea"
                :rows="4"
                placeholder="输入数值数据，逗号分隔"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handlePredict" :loading="predicting">
                开始推理
              </el-button>
            </el-form-item>
          </el-form>
          <el-divider />
          <div v-if="predictResult" class="result-section">
            <h4>推理结果</h4>
            <pre>{{ predictResult }}</pre>
          </div>
        </el-tab-pane>
        <el-tab-pane label="模型列表" name="models">
          <el-table :data="modelList" style="width: 100%">
            <el-table-column prop="name" label="名称" />
            <el-table-column prop="model_type" label="类型" />
            <el-table-column prop="version" label="版本" />
            <el-table-column prop="input_features" label="输入特征">
              <template #default="{ row }">
                {{ row.input_features?.join(', ') }}
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import axios from 'axios'

const activeTab = ref('predict')
const predicting = ref(false)

const predictForm = reactive({
  modelName: 'CFC-Fast',
  inputData: '',
})

const predictResult = ref<string | null>(null)
const modelList = ref<any[]>([])

async function handlePredict() {
  predicting.value = true
  predictResult.value = null
  try {
    const inputArray = predictForm.inputData
      .split(',')
      .map(val => val.trim())
      .filter(val => val !== '')
      .map(Number)
      .filter(num => !isNaN(num))

    if (inputArray.length === 0) {
      predictResult.value = JSON.stringify({ error: '请输入有效的数值数据' }, null, 2)
      predicting.value = false
      return
    }

    const res = await axios.post('/api/v1/lnn/predict', {
      model_name: predictForm.modelName,
      input_data: inputArray,
      return_confidence: true,
    })
    predictResult.value = JSON.stringify(res.data, null, 2)
  } catch (e: any) {
    const errorMsg = e?.response?.data?.detail || e?.message || '推理请求失败'
    console.error('Prediction failed:', e)
    predictResult.value = JSON.stringify({ error: errorMsg }, null, 2)
  } finally {
    predicting.value = false
  }
}

onMounted(async () => {
  try {
    const res = await axios.get('/api/v1/lnn/models')
    modelList.value = res.data?.data?.models || []
  } catch (e) {
    console.error('Failed to load model list:', e)
    modelList.value = []
  }
})
</script>

<style scoped>
.workspace-page {
  max-width: 1200px;
  margin: 0 auto;
}

.result-section {
  background: #f5f7fa;
  border-radius: 4px;
  padding: 16px;
}

.result-section pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
