<template>
  <div class="settings-page">
    <el-card>
      <template #header>系统设置</template>
      <el-form :model="store.settings" label-width="140px">
        <el-form-item label="AI服务模式">
          <el-radio-group v-model="store.settings.aiMode">
            <el-radio value="local">本地</el-radio>
            <el-radio value="cloud">云端</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="本地模型">
          <el-select v-model="store.settings.localModel">
            <el-option label="qwen2.5:7b" value="qwen2.5:7b" />
            <el-option label="qwen2.5:14b" value="qwen2.5:14b" />
          </el-select>
        </el-form-item>
        <el-form-item label="计算设备">
          <el-select v-model="store.settings.device">
            <el-option label="CPU" value="cpu" />
            <el-option label="GPU (CUDA)" value="cuda" />
          </el-select>
        </el-form-item>
        <el-form-item label="离线模式">
          <el-switch v-model="store.settings.offlineMode" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="store.saveSettings()">保存设置</el-button>
          <el-button @click="store.resetSettings()">恢复默认</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { useSettingsStore } from '@/stores/settings'

const store = useSettingsStore()
</script>

<style scoped>
.settings-page {
  max-width: 600px;
  margin: 0 auto;
}
</style>