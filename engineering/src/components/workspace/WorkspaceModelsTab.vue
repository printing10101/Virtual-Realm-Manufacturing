<template>
  <el-table :data="modelList" style="width: 100%" v-loading="loading">
    <el-table-column prop="name" :label="$t('workspace.modelListName')" />
    <el-table-column prop="model_type" :label="$t('workspace.modelListType')" />
    <el-table-column prop="version" :label="$t('workspace.modelListVersion')" />
    <el-table-column prop="input_features" :label="$t('workspace.modelListFeatures')">
      <template #default="{ row }">{{ row.input_features?.join(', ') }}</template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import http from '@/utils/http'
import { API_CONFIG, buildApiPath } from '@/config/api'

const loading = ref(false)

interface ModelInfo { name: string; model_type: string; version: string; input_features?: string[] }
const modelList = ref<ModelInfo[]>([])

async function fetchModels(): Promise<void> {
  loading.value = true
  try {
    const res = await http.get<ModelInfo[]>(buildApiPath(API_CONFIG.MODELS, ''))
    modelList.value = res.data
  } catch { /* silent */ } finally { loading.value = false }
}

onMounted(() => { void fetchModels() })
</script>
